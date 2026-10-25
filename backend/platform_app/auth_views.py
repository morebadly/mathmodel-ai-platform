import json
import hashlib
from django.conf import settings
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.cache import cache
from django.db import transaction,IntegrityError
from django.http import JsonResponse
from django.views.decorators.http import require_GET,require_POST
from django.views.decorators.csrf import ensure_csrf_cookie,csrf_protect
from django.utils.http import urlsafe_base64_decode
from allauth.account.models import EmailAddress,EmailConfirmationHMAC
from .models import User,Audit
from .domain import verified
from .access import ADMIN_LOGINS,ADMIN_EMAILS,fixed_admin,valid_mentor_key,reserved_email
from .mail import reserved_recipient
from .email_codes import issue_code,check_code,consume,CODE_TTL,RESEND_SECONDS

def identity(user):return {'id':str(user.id),'email':user.email if user.role!='admin' else '', 'emailVerified':verified(user) if user.role!='admin' else False,'accountVerified':verified(user),'adminLogin':user.admin_login or '', 'displayName':user.display_name,'role':user.role,'requestedRole':user.requested_role,'reminderConsent':user.reminder_consent,'trackUsage':user.track_usage,'cohort':user.cohort}
def error(message,status=400):return JsonResponse({'error':{'message':message}},status=status)
@require_GET
@ensure_csrf_cookie
def session(request):return JsonResponse({'user':identity(request.user) if request.user.is_authenticated and verified(request.user) else None})
@require_POST
@csrf_protect
def action(request,mode):
    try:body=json.loads(request.body or '{}')
    except (ValueError,UnicodeError):return error('请求格式无效。')
    if not isinstance(body,dict):return error('请求格式无效。')
    email=str(body.get('email','')).strip().lower()
    ip_key='auth-ip:'+hashlib.sha256(request.META.get('REMOTE_ADDR','').encode()).hexdigest()
    cache.add(ip_key,0,900)
    if cache.incr(ip_key)>100:return error('操作过于频繁，请稍后重试。',429)
    if 'password' in body and (not isinstance(body['password'],str) or len(body['password'])>200):return error('密码格式无效。')
    if mode not in ['logout','admin-login']:
        try:validate_email(email)
        except ValidationError:return error('请输入有效邮箱。')
        if mode in ['register','resend','forgot'] and settings.MAIL_TRANSPORT=='smtp' and reserved_recipient(email):
            return error('请输入可接收邮件的真实邮箱，测试占位地址不能接收验证或重置邮件。')
    account=str(body.get('account','')).strip().lower()
    key='auth:'+hashlib.sha256((mode+':'+request.META.get('REMOTE_ADDR','')+':'+(account if mode=='admin-login' else email)).encode()).hexdigest()
    cache.add(key,0,900)
    if cache.incr(key)>15:return error('操作过于频繁，请稍后重试。',429)
    if mode in ['register','resend']:
        if reserved_email(email):return error('此地址保留给固定管理员账号，不开放邮箱注册。')
        requested=body.get('requestedRole','student')
        if requested not in ['student','mentor']:return error('注册身份无效。')
        if requested=='mentor' and not valid_mentor_key(body.get('mentorKey')):return error('导师注册密钥无效，请向平台管理者获取。',403)
        name=str(body.get('displayName','')).strip()[:120]
        if mode=='register' and not name:return error('请填写显示名称。')
        with transaction.atomic():
            user=User.objects.select_for_update().filter(email__iexact=email).first()
            created=False
            if not user and mode=='register':
                try:
                    with transaction.atomic():
                        user=User.objects.create_user(email,None,display_name=name,requested_role=requested,reminder_consent=False)
                        EmailAddress.objects.create(user=user,email=email,primary=True,verified=False)
                    created=True
                except IntegrityError:
                    user=User.objects.select_for_update().get(email__iexact=email)
            if created:
                issue_code(user,'verify')
                Audit.objects.create(actor=user,action='register')
            elif user and user.is_active and not verified(user):
                user.requested_role=requested;user.save(update_fields=['requested_role'])
                address=EmailAddress.objects.filter(user=user,email__iexact=email,verified=False).first()
                if address:issue_code(user,'verify')
        return JsonResponse({'accepted':True,'verificationType':'code','codeLength':6,'expiresIn':CODE_TTL,'resendAfter':RESEND_SECONDS},status=202)
    if mode=='verify':
        if reserved_email(email):return error('管理员账号不使用邮箱验证注册。')
        requested=body.get('requestedRole','student')
        if requested not in ['student','mentor']:return error('验证身份无效。')
        if requested=='mentor' and not valid_mentor_key(body.get('mentorKey')):return error('导师注册密钥无效，未开通导师权限。',403)
        code=str(body.get('code','')).strip()
        if len(code)>256:return error('验证码无效或已过期，请重新获取。')
        with transaction.atomic():
            user=User.objects.select_for_update().filter(email__iexact=email,is_active=True).exclude(role='admin').first()
            if not user:return error('验证码无效或已过期，请重新获取。')
            address=EmailAddress.objects.select_for_update().filter(user=user,email__iexact=email,verified=False).first()
            if not address:return error('验证码无效或已使用，请重新获取。')
            challenge=None
            if ':' in code: # Previously sent signed links remain valid until their original expiry.
                confirmation=EmailConfirmationHMAC.from_key(code)
                if not confirmation or confirmation.email_address.pk!=address.pk:return error('验证链接无效或已过期。')
            else:
                challenge=check_code(user,'verify',code)
                if not challenge:return error('验证码错误、已过期或错误次数过多，请重新获取。')
                if challenge.requested_role!=requested:return error('请使用获取验证码时选择的身份，或重新获取验证码。')
                confirmation=EmailConfirmationHMAC(address)
            try:validate_password(body.get('password',''),user=user)
            except (ValidationError,TypeError):return error('请在验证邮箱时设置至少12位的非简单密码。')
            # Reuse allauth confirmation bookkeeping after validating our bounded code.
            confirmation.confirm(request)
            user.set_password(body['password']);user.role=requested;user.requested_role=requested;user.reminder_consent=body.get('reminderConsent') is True;user.save(update_fields=['password','reminder_consent','role','requested_role'])
            if challenge:consume(challenge)
        return JsonResponse({'verified':True})
    if mode=='login':
        user=authenticate(request,email=email,password=body.get('password',''))
        if not user or user.role=='admin' or not verified(user):return error('邮箱、密码或验证状态不正确。',401)
        login(request,user,backend='django.contrib.auth.backends.ModelBackend');Audit.objects.create(actor=user,action='login')
        return JsonResponse({'user':identity(user)})
    if mode=='admin-login':
        user=authenticate(request,email=ADMIN_EMAILS.get(account,''),password=body.get('password','')) if account in ADMIN_LOGINS else None
        if not user or user.admin_login!=account or not fixed_admin(user):return error('管理账号或密码不正确。',401)
        login(request,user,backend='django.contrib.auth.backends.ModelBackend');Audit.objects.create(actor=user,action='login')
        return JsonResponse({'user':identity(user)})
    if mode=='forgot':
        with transaction.atomic():
            user=User.objects.select_for_update().filter(email__iexact=email,is_active=True).exclude(role='admin').first()
            if user:issue_code(user,'reset')
        return JsonResponse({'accepted':True,'verificationType':'code','codeLength':6,'expiresIn':CODE_TTL,'resendAfter':RESEND_SECONDS},status=202)
    if mode=='reset':
        code=str(body.get('code','')).strip()
        if len(code)>256:return error('重置码无效或已过期。')
        with transaction.atomic():
            user=User.objects.select_for_update().filter(email__iexact=email,is_active=True).exclude(role='admin').first()
            if not user:return error('重置码无效或已过期。')
            challenge=None
            if ':' in code:
                try:uid,token=code.split(':',1);legacy_uid=urlsafe_base64_decode(uid).decode()
                except (ValueError,UnicodeError,ValidationError):return error('重置链接无效或已过期。')
                if str(user.pk)!=legacy_uid or not default_token_generator.check_token(user,token):return error('重置链接无效或已过期。')
            else:
                challenge=check_code(user,'reset',code)
                if not challenge:return error('验证码错误、已过期或错误次数过多，请重新获取。')
            try:validate_password(body.get('password',''),user=user)
            except (ValidationError,TypeError):return error('新密码不符合要求。')
            user.set_password(body['password']);user.save(update_fields=['password']);Audit.objects.create(actor=user,action='password-reset')
            if challenge:consume(challenge)
        return JsonResponse({'reset':True})
    if mode=='logout':logout(request);return JsonResponse({'loggedOut':True})
    return error('未知账号操作。',404)

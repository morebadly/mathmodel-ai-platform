"""Persistent six-digit email verification/reset codes for the existing auth API."""
import secrets
import uuid
from datetime import timedelta
from django.utils import timezone
from django.utils.crypto import constant_time_compare,salted_hmac
from .models import EmailCode,MailJob

CODE_TTL=600
RESEND_SECONDS=60
MAX_ATTEMPTS=5
MAX_SENDS_PER_HOUR=10

def digest(challenge,user,code):
    value=':'.join([str(user.pk),user.email,challenge.purpose,str(challenge.nonce),user.password,challenge.requested_role,code])
    return salted_hmac('mathmodel-email-code',value,algorithm='sha256').hexdigest()

def issue_code(user,purpose):
    """Caller holds the user row lock and an atomic transaction (also on resends)."""
    now=timezone.now()
    challenge=EmailCode.objects.select_for_update().filter(user=user,purpose=purpose).first()
    if challenge:
        if now-challenge.sent_at<timedelta(seconds=RESEND_SECONDS):return False
        if MailJob.objects.filter(email_code=challenge,created_at__gt=now-timedelta(hours=1)).count()>=MAX_SENDS_PER_HOUR:return False
    else:
        challenge=EmailCode(user=user,purpose=purpose)
    code=f'{secrets.randbelow(1000000):06d}'
    challenge.nonce=uuid.uuid4();challenge.requested_role=user.requested_role
    challenge.sent_at=now;challenge.expires_at=now+timedelta(seconds=CODE_TTL)
    challenge.attempts=0;challenge.used_at=None
    challenge.code_hash=digest(challenge,user,code);challenge.save()
    label='邮箱验证' if purpose=='verify' else '密码重置'
    MailJob.objects.create(recipient=user.email,recipient_user=user,email_code=challenge,email_code_nonce=challenge.nonce,
        subject=f'MathModel AI {label}验证码',body=f'你的{label}验证码是：{code}\n\n请回到 MathModel AI 页面填写这6位数字，10分钟内有效，只能使用一次。\n重新获取验证码后，请使用最新一封邮件中的验证码。\n请勿将验证码提供给其他人。如果不是你本人操作，请忽略此邮件。',
        dedup_key='email-code:'+str(challenge.nonce),planned_at=now)
    return True

def check_code(user,purpose,code):
    """Caller holds user lock. Wrong attempts commit even when the API returns 400."""
    challenge=EmailCode.objects.select_for_update().filter(user=user,purpose=purpose).first()
    if not challenge or challenge.used_at or challenge.expires_at<=timezone.now() or challenge.attempts>=MAX_ATTEMPTS:return None
    if len(code)!=6 or not code.isascii() or not code.isdigit() or not constant_time_compare(challenge.code_hash,digest(challenge,user,code)):
        challenge.attempts+=1;challenge.save(update_fields=['attempts']);return None
    return challenge

def consume(challenge):
    challenge.used_at=timezone.now();challenge.save(update_fields=['used_at'])

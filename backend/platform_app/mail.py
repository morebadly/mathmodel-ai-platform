import hashlib
import smtplib
import uuid
from datetime import timedelta
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from .smtp_backend import EmailBackend as SMTPBackend
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from django.core import signing
from allauth.account.models import EmailAddress
from .models import MailJob,User,Record,Usage,EmailCode
from .email_codes import MAX_ATTEMPTS

def reserved_recipient(address):
    """Never deliver historical fixture addresses through a real SMTP service."""
    domain=address.rsplit('@',1)[-1].lower().rstrip('.')
    return any(domain==suffix or domain.endswith('.'+suffix) for suffix in ['invalid','test','localhost','example'])

class QueueEmailBackend(BaseEmailBackend):
    def send_messages(self,email_messages):
        count=0
        for message in email_messages:
            for address in message.to:
                user=User.objects.filter(email__iexact=address).first()
                MailJob.objects.create(recipient=address,recipient_user=user,subject=message.subject[:240],body=message.body,dedup_key='auth:'+str(uuid.uuid4()),planned_at=timezone.now())
                count+=1
        return count

def learning_eligible(owner,user,context=None):
    from .domain import managed_users,verified
    if not owner or not owner.is_active or owner.role not in ['mentor','admin'] or not verified(owner):return False
    if not user or not user.is_active or not user.reminder_consent or not verified(user):return False
    if not managed_users(owner).filter(id=user.id,role='student').exists():return False
    if context and context.collection=='teams':
        from .models import Membership
        return Membership.objects.filter(team=context,user=user).exists()
    if context and context.collection in ['supervisionPlans','reminderDrafts']:
        return str(user.id) in context.payload.get('studentIds',context.payload.get('recipientIds',[]))
    return True

@transaction.atomic
def queue_learning(owner,user,subject,body,dedup,planned_at=None,context=None):
    # Consent/role updates must serialize, but foreign-key checks in a pending
    # submission or audit must not be blocked by an unnecessary key lock.
    user=User.objects.select_for_update(no_key=True).get(id=user.id)
    if not learning_eligible(owner,user,context):return None
    key=hashlib.sha256(dedup.encode()).hexdigest()
    existing=MailJob.objects.filter(dedup_key=key).first()
    if existing:return existing
    if MailJob.objects.filter(recipient_user=user,kind='learning',created_at__gte=timezone.now()-timedelta(days=1)).count()>=10:return None
    token=signing.dumps({'user':str(user.id)},salt='learning-unsubscribe')
    footer='\n\n管理学习提醒接收意愿：'+settings.SITE_URL+'/?unsubscribe='+token+'#login/student'
    job=MailJob.objects.create(dedup_key=key,owner=owner,recipient=user.email,recipient_user=user,kind='learning',subject=subject[:240],body=body+footer,planned_at=planned_at or timezone.now(),context=context)
    return job

def _send_claimed_mail(job):
    if settings.MAIL_TRANSPORT=='local':
        job.status='local';job.last_error='本地联调邮件，未向外部邮箱投递。'
    else:
        accepted=False;stage='connect'
        try:
            if not settings.EMAIL_HOST:raise RuntimeError('SMTP not configured')
            with SMTPBackend(host=settings.EMAIL_HOST,port=settings.EMAIL_PORT,username=settings.EMAIL_HOST_USER,password=settings.EMAIL_HOST_PASSWORD,use_tls=settings.EMAIL_USE_TLS,use_ssl=settings.EMAIL_USE_SSL,timeout=20) as backend:
                stage='submit'
                sent=backend.send_messages([EmailMessage(job.subject,job.body,settings.DEFAULT_FROM_EMAIL,[job.recipient])])
                if sent!=1:
                    stage='rejected';raise RuntimeError('SMTP not accepted')
                accepted=True
            job.status='accepted';job.last_error='邮件服务已受理，不能据此判定已读。'
        except Exception as exc:
            if accepted:
                # A failed QUIT cannot undo a confirmed DATA acceptance.
                job.status='accepted';job.last_error='邮件服务已受理，连接关闭异常；不能据此判定已读。'
            elif stage in ['connect','rejected'] or isinstance(exc,(smtplib.SMTPDataError,smtplib.SMTPRecipientsRefused,smtplib.SMTPSenderRefused,smtplib.SMTPHeloError,smtplib.SMTPNotSupportedError)):
                job.status='retry' if job.attempts<3 else 'failed';job.last_error='发信服务未能受理，请检查后台配置。';job.planned_at=timezone.now()+timedelta(minutes=2**job.attempts)
            else:
                job.status='uncertain';job.last_error='邮件提交时连接中断或结果不明；为避免重复投递，暂停自动重试，请人工核对。'
    job.save()

@transaction.atomic
def _send_code_mail(job):
    # Registration, resend, verify and reset all lock User before EmailCode.
    # Keep that per-account lock through SMTP (20s socket timeout), so a resend
    # cannot supersede a claimed code before its SMTP submission completes.
    user=User.objects.select_for_update().filter(pk=job.recipient_user_id).first()
    challenge=EmailCode.objects.select_for_update().filter(pk=job.email_code_id).first()
    if not user or not user.is_active or user.role=='admin' or user.email.lower()!=job.recipient.lower() or not challenge or challenge.nonce!=job.email_code_nonce or challenge.used_at or challenge.expires_at<=timezone.now() or challenge.attempts>=MAX_ATTEMPTS:
        job.status='cancelled';job.last_error='验证码或所属账号在投递前已变化。';job.save();return
    _send_claimed_mail(job)


def process_mail(limit=20):
    MailJob.objects.filter(status='sending',updated_at__lt=timezone.now()-timedelta(minutes=10)).update(status='uncertain',last_error='发送进程中断，投递状态不确定，需人工核对后重试。')
    for key in list(MailJob.objects.filter(status__in=['queued','retry'],planned_at__lte=timezone.now()).order_by('planned_at').values_list('id',flat=True)[:limit]):
        with transaction.atomic():
            job=MailJob.objects.select_for_update(of=('self',)).select_related('recipient_user','owner','context','email_code').get(id=key)
            if job.status not in ['queued','retry']:continue
            if job.email_code_nonce and not job.email_code:
                job.status='cancelled';job.last_error='验证码所属账号或验证记录已移除。';job.save();continue
            if job.email_code and (job.email_code_nonce!=job.email_code.nonce or job.email_code.used_at or job.email_code.expires_at<=timezone.now() or job.email_code.attempts>=MAX_ATTEMPTS):
                job.status='cancelled';job.last_error='验证码已使用、过期、被更新或错误次数过多。';job.save();continue
            if settings.MAIL_TRANSPORT=='smtp' and reserved_recipient(job.recipient):
                job.status='cancelled';job.last_error='示例或本地测试邮箱不支持真实投递，请使用有效收件邮箱。';job.save();continue
            if (job.kind=='learning' and (not learning_eligible(job.owner,job.recipient_user,job.context) or job.recipient_user.email.lower()!=job.recipient.lower())) or (job.recipient_user and not job.recipient_user.is_active) or (job.kind=='invite' and (not job.owner or not job.owner.is_active or job.owner.role not in ['mentor','admin'])):
                job.status='cancelled';job.last_error='账号、邮箱验证、负责关系或接收意愿已变化。';job.save();continue
            job.status='sending';job.attempts+=1;job.save()
        if job.email_code_nonce:_send_code_mail(job)
        else:_send_claimed_mail(job)

def evaluate_plans():
    today=timezone.localdate().isoformat();now=timezone.now()
    for plan in Record.objects.filter(collection='supervisionPlans').select_related('owner'):
        for uid in plan.payload.get('studentIds',[]):
            from .domain import managed_users
            user=managed_users(plan.owner).filter(id=uid,role='student').first()
            if not user or not user.track_usage:continue
            records=Usage.objects.filter(user=user)
            latest=records.order_by('-ended_at').first()
            if not latest:continue
            weekly=records.filter(day__gte=timezone.localdate()-timedelta(days=6)).count()
            p=plan.payload;reasons=[]
            if isinstance(p.get('maxInactiveDays'),int) and now-latest.ended_at>=timedelta(days=p['maxInactiveDays']):reasons.append('已达到导师设置的未活跃天数。')
            if isinstance(p.get('minWeeklySessions'),int) and weekly<p['minWeeklySessions']:reasons.append('近7天学习会话少于导师设置的目标。')
            if reasons:queue_learning(plan.owner,user,'学习与训练跟进提醒',f'{user.display_name or "同学"}，你好。'+''.join(reasons)+'请登录平台查看导师目标。','plan:'+plan.id+':'+uid+':'+today,context=plan)

"""Isolated numeric email-code integration tests; never contact real SMTP."""
import json
import re
from datetime import timedelta
from unittest.mock import patch
from unittest import skipUnless
from django.test import TestCase,TransactionTestCase,Client,override_settings
from django.db import connection,close_old_connections
from django.core.cache import cache
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from allauth.account.models import EmailAddress
from .models import User,EmailCode,MailJob,RegistrationPolicy
from .mail import process_mail
from .tests import PASSWORD,TEST_MENTOR_KEY,person

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],MAIL_TRANSPORT='local')
class EmailCodeTests(TestCase):
    def setUp(self):
        cache.clear();self.c=Client()
        RegistrationPolicy.objects.create(id='default',mentor_key_hash=make_password(TEST_MENTOR_KEY))
    def post(self,mode,body,**extra):return self.c.post('/api/auth/'+mode,json.dumps(body),content_type='application/json',**extra)
    def code(self,email,purpose=None):
        rows=MailJob.objects.filter(recipient=email)
        if purpose:rows=rows.filter(email_code__purpose=purpose)
        return re.search(r'验证码是：([0-9]{6})',rows.latest('created_at').body).group(1)
    def register(self,email='code-owner@example.invalid',role='student'):
        body={'email':email,'displayName':'验证码测试','requestedRole':role}
        if role=='mentor':body['mentorKey']=TEST_MENTOR_KEY
        self.assertEqual(self.post('register',body).status_code,202)
        return User.objects.get(email=email),self.code(email,'verify')
    def verify(self,user,code,**extra):return self.post('verify',{'email':user.email,'code':code,'password':PASSWORD,**extra})
    def test_six_digits_including_leading_zeros_and_no_link(self):
        with patch('platform_app.email_codes.secrets.randbelow',return_value=7):u,code=self.register()
        self.assertEqual(code,'000007');challenge=EmailCode.objects.get(user=u,purpose='verify')
        self.assertNotIn(code,challenge.code_hash);self.assertEqual(len(challenge.code_hash),64)
        job=MailJob.objects.get(email_code=challenge)
        self.assertNotIn('http',job.body);self.assertNotIn('?verify=',job.body)
        process_mail();job.refresh_from_db();self.assertEqual(job.status,'local')
        self.assertEqual(self.verify(u,code).status_code,200)
        self.assertEqual(self.post('login',{'email':u.email,'password':PASSWORD}).status_code,200)
        self.assertEqual(self.verify(u,code).status_code,400)
    def test_expired_and_wrong_email_codes_fail(self):
        with patch('platform_app.email_codes.secrets.randbelow',side_effect=[123456,654321]):
            u,code=self.register();other,other_code=self.register('different@example.invalid')
        self.assertEqual(self.verify(other,code).status_code,400)
        EmailCode.objects.filter(user=u).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.verify(u,code).status_code,400)
        self.assertFalse(EmailAddress.objects.get(user=u).verified)
    def test_five_wrong_attempts_lock_the_code_across_ip_addresses(self):
        u,code=self.register();wrong='000000' if code!='000000' else '999999'
        for i in range(5):
            self.assertEqual(self.post('verify',{'email':u.email,'code':wrong,'password':PASSWORD},REMOTE_ADDR='192.0.2.'+str(i+1)).status_code,400)
        self.assertEqual(EmailCode.objects.get(user=u).attempts,5)
        self.assertEqual(self.verify(u,code).status_code,400)
    def test_weak_password_does_not_consume_valid_code(self):
        u,code=self.register()
        self.assertEqual(self.verify(u,code,password='weak').status_code,400)
        self.assertIsNone(EmailCode.objects.get(user=u).used_at)
        self.assertEqual(self.verify(u,code).status_code,200)
    def test_resend_cooldown_is_shared_across_ips_and_old_pending_mail_cancelled(self):
        with patch('platform_app.email_codes.secrets.randbelow',side_effect=[123456,654321]):
            u,first=self.register()
            for i in range(3):self.assertEqual(self.post('resend',{'email':u.email},REMOTE_ADDR='198.51.100.'+str(i+1)).status_code,202)
            self.assertEqual(MailJob.objects.filter(recipient=u.email).count(),1)
            EmailCode.objects.filter(user=u).update(sent_at=timezone.now()-timedelta(seconds=61))
            self.assertEqual(self.post('resend',{'email':u.email}).status_code,202)
        second=self.code(u.email);self.assertNotEqual(first,second)
        process_mail()
        old,new=MailJob.objects.filter(recipient=u.email).order_by('created_at')
        self.assertEqual(old.status,'cancelled');self.assertEqual(old.attempts,0);self.assertEqual(new.status,'local')
        self.assertEqual(self.verify(u,first).status_code,400)
        self.assertEqual(self.verify(u,second).status_code,200)
    def test_hourly_send_limit_is_persistent(self):
        u,code=self.register()
        for i in range(12):
            EmailCode.objects.filter(user=u).update(sent_at=timezone.now()-timedelta(seconds=61))
            self.post('resend',{'email':u.email},REMOTE_ADDR='203.0.113.'+str(i+1))
        self.assertEqual(MailJob.objects.filter(recipient=u.email).count(),10)
    def test_send_limit_is_a_rolling_hour_at_the_window_boundary(self):
        u,code=self.register();first=MailJob.objects.get(recipient=u.email)
        MailJob.objects.filter(pk=first.pk).update(created_at=timezone.now()-timedelta(minutes=59))
        for i in range(9):
            EmailCode.objects.filter(user=u).update(sent_at=timezone.now()-timedelta(seconds=61));self.post('resend',{'email':u.email})
        EmailCode.objects.filter(user=u).update(sent_at=timezone.now()-timedelta(seconds=61))
        self.post('resend',{'email':u.email});self.assertEqual(MailJob.objects.filter(recipient=u.email).count(),10)
        MailJob.objects.filter(pk=first.pk).update(created_at=timezone.now()-timedelta(minutes=61))
        self.post('resend',{'email':u.email});self.assertEqual(MailJob.objects.filter(recipient=u.email).count(),11)
        EmailCode.objects.filter(user=u).update(sent_at=timezone.now()-timedelta(seconds=61))
        self.post('resend',{'email':u.email});self.assertEqual(MailJob.objects.filter(recipient=u.email,created_at__gt=timezone.now()-timedelta(hours=1)).count(),10)
    def test_replacement_after_claim_is_checked_again_before_delivery(self):
        from .mail import _send_code_mail
        u,code=self.register();old=MailJob.objects.get(recipient=u.email)
        def replaced_after_claim(job):
            EmailCode.objects.filter(user=u).update(sent_at=timezone.now()-timedelta(seconds=61))
            self.post('resend',{'email':u.email})
            return _send_code_mail(job)
        with patch('platform_app.mail._send_code_mail',side_effect=replaced_after_claim),patch('platform_app.mail._send_claimed_mail') as transport:
            process_mail()
        old.refresh_from_db();self.assertEqual(old.status,'cancelled');self.assertEqual(old.attempts,1);transport.assert_not_called()
    def test_unknown_resend_does_not_create_an_account_and_responses_are_generic(self):
        a=self.post('resend',{'email':'missing@example.invalid'})
        b=self.post('forgot',{'email':'missing@example.invalid'})
        self.assertEqual(a.status_code,202);self.assertEqual(a.json(),b.json())
        self.assertFalse(User.objects.filter(email='missing@example.invalid').exists());self.assertFalse(MailJob.objects.exists())
    def test_reset_code_is_one_use_and_registration_code_is_wrong_purpose(self):
        with patch('platform_app.email_codes.secrets.randbelow',side_effect=[123456,654321]):
            u,verify_code=self.register();self.assertEqual(self.verify(u,verify_code).status_code,200)
            self.assertEqual(self.post('forgot',{'email':u.email}).status_code,202)
        code=self.code(u.email,'reset');body={'email':u.email,'code':code,'password':'New-valid-password-987!'}
        self.assertEqual(self.post('reset',{**body,'code':verify_code}).status_code,400)
        self.assertEqual(self.post('reset',body).status_code,200)
        self.assertEqual(self.post('reset',body).status_code,400)
        self.assertEqual(self.post('login',{'email':u.email,'password':body['password']}).status_code,200)
    def test_password_change_invalidates_an_outstanding_reset_code(self):
        u=person('reset-owner');self.post('forgot',{'email':u.email});code=self.code(u.email,'reset')
        u.set_password('Different-valid-password-654!');u.save(update_fields=['password'])
        self.assertEqual(self.post('reset',{'email':u.email,'code':code,'password':PASSWORD}).status_code,400)
    def test_mentor_secret_and_requested_role_still_checked(self):
        self.assertEqual(self.post('register',{'email':'mentor-bad@example.invalid','displayName':'导师','requestedRole':'mentor','mentorKey':'wrong'}).status_code,403)
        u,code=self.register(role='mentor')
        self.assertEqual(self.verify(u,code,requestedRole='mentor',mentorKey='wrong').status_code,403)
        self.assertEqual(self.verify(u,code,requestedRole='student').status_code,400)
        self.assertEqual(self.verify(u,code,requestedRole='mentor',mentorKey=TEST_MENTOR_KEY).status_code,200)
        u.refresh_from_db();self.assertEqual(u.role,'mentor')
    def test_fixed_administrators_cannot_request_codes(self):
        u=person('admin','admin')
        self.assertEqual(self.post('resend',{'email':u.email}).status_code,400)
        self.assertEqual(self.post('forgot',{'email':u.email}).status_code,202)
        self.assertFalse(MailJob.objects.exists())
    def test_consumed_code_mail_is_not_sent_late(self):
        u,code=self.register();self.assertEqual(self.verify(u,code).status_code,200)
        process_mail();job=MailJob.objects.get(recipient=u.email)
        self.assertEqual(job.status,'cancelled');self.assertEqual(job.attempts,0)

@skipUnless(connection.vendor=='postgresql','Requires PostgreSQL row locks; SQLite is not equivalent')
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],MAIL_TRANSPORT='smtp',EMAIL_HOST='contract-only.example.org')
class EmailCodeConcurrencyTests(TransactionTestCase):
    def test_resend_waits_for_inflight_smtp_with_real_database_locks(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        import time
        cache.clear();c=Client();email='row-lock-contract@example.org'
        response=c.post('/api/auth/register',json.dumps({'email':email,'displayName':'锁竞争测试'}),content_type='application/json')
        self.assertEqual(response.status_code,202);u=User.objects.get(email=email)
        EmailCode.objects.filter(user=u).update(sent_at=timezone.now()-timedelta(seconds=61))
        initial=EmailCode.objects.get(user=u).nonce;entered=Event();release=Event();resend_started=Event()
        def smtp_submit(messages):
            entered.set()
            if not release.wait(8):raise AssertionError('Test release deadline exceeded')
            return 1
        def worker():
            close_old_connections()
            try:process_mail()
            finally:close_old_connections()
        def resend():
            close_old_connections();resend_started.set()
            try:return Client().post('/api/auth/resend',json.dumps({'email':email}),content_type='application/json').status_code
            finally:close_old_connections()
        with patch('platform_app.mail.SMTPBackend') as backend,ThreadPoolExecutor(max_workers=2) as pool:
            backend.return_value.__enter__.return_value.send_messages.side_effect=smtp_submit
            sending=pool.submit(worker)
            try:
                self.assertTrue(entered.wait(6));resending=pool.submit(resend);self.assertTrue(resend_started.wait(3))
                deadline=time.monotonic()+3;blocked=False
                while time.monotonic()<deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND wait_event_type='Lock' AND query LIKE '%%platform_app_user%%')")
                        blocked=cursor.fetchone()[0]
                    if blocked:break
                    time.sleep(.02)
                self.assertTrue(blocked,'Resend must wait on the same PostgreSQL user row');self.assertFalse(resending.done())
            finally:release.set()
            sending.result(timeout=10);self.assertEqual(resending.result(timeout=10),202)
        self.assertNotEqual(EmailCode.objects.get(user=u).nonce,initial)
        self.assertEqual(MailJob.objects.filter(recipient=email,status='accepted').count(),1)
        self.assertEqual(MailJob.objects.filter(recipient=email,status='queued').count(),1)

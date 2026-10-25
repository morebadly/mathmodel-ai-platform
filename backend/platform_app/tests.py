"""Isolated integration tests: no external email or model calls."""
import copy
import smtplib
import os
import subprocess
import sys
import hashlib
import json
import re
import tempfile
import sqlite3
import uuid
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch,Mock
from django.test import TestCase,Client as DjangoClient,override_settings
from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import signing
from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth.hashers import make_password
from io import StringIO
from django.utils import timezone
from allauth.account.models import EmailAddress,EmailConfirmationHMAC
from .models import User,Record,Membership,Usage,MailJob,Asset,Invitation,AIRun,RegistrationPolicy,Workspace
from .access import ADMIN_LOGINS,ADMIN_EMAILS
from .domain import save_workspace,workspace_json,can_read,editable,managed_users
from .mail import queue_learning,process_mail,evaluate_plans
from .parsing import parse_pending

PASSWORD='Local-test-Only-723!'
TEST_MENTOR_KEY='Only-test-Mentor-Invite-294!'
class Client(DjangoClient):
    def force_login(self,user,backend=None):
        super().force_login(user,backend=backend);self.defaults['HTTP_X_MM_ACCOUNT']=str(user.id)
def key():return str(uuid.uuid4())
def person(name,role='student',verified=True,consent=True):
    u=User.objects.create_user(ADMIN_EMAILS['admin01'] if role=='admin' else name+'@example.invalid',PASSWORD,display_name=name,role=role,reminder_consent=consent,**({'admin_login':'admin01','is_staff':True,'is_superuser':True} if role=='admin' else {}))
    if role!='admin':EmailAddress.objects.create(user=u,email=u.email,primary=True,verified=verified)
    return u
def record(owner,collection,**payload):
    rid=payload.pop('id',key());return Record.objects.create(id=rid,owner=owner,collection=collection,payload={'id':rid,**payload})
def project(owner,task):
    return record(owner,'projects',title='训练成果',description='',taskId=task.id,resourceIds=[],stages=[{'title':str(i),'content':'真实笔记','done':False} for i in range(8)],createdAt=timezone.now().isoformat(),updatedAt=timezone.now().isoformat())

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],EMAIL_BACKEND='platform_app.mail.QueueEmailBackend',MAIL_TRANSPORT='local',ALLOW_DEV_MAILBOX=True,AI_API_KEY='')
class PlatformTests(TestCase):
    client_class=Client
    def setUp(self):
        cache.clear();temp_root=settings.DATA_DIR/'test-media';temp_root.mkdir(exist_ok=True);self.temp=tempfile.TemporaryDirectory(dir=temp_root);self.media=override_settings(MEDIA_ROOT=self.temp.name);self.media.enable()
        self.addCleanup(self.temp.cleanup);self.addCleanup(self.media.disable)
        self.s=person('student');self.other=person('other');self.m=person('mentor','mentor');self.a=person('admin','admin')
        RegistrationPolicy.objects.create(id='default',mentor_key_hash=make_password(TEST_MENTOR_KEY))
        self.team=record(self.m,'teams',name='建模团队',description='',members=[],messages=[],fileIds=[])
        Membership.objects.create(team=self.team,user=self.s)
        self.client.force_login(self.s,backend='django.contrib.auth.backends.ModelBackend')
    def post(self,url,data,client=None):return (client or self.client).post(url,json.dumps(data),content_type='application/json')
    def patch(self,data):return self.client.patch('/api/workspace',json.dumps({'changes':data}),content_type='application/json')
    def test_registration_uses_email_and_cannot_grant_mentor(self):
        c=Client();r=self.post('/api/auth/register',{'email':'New@Example.invalid','password':PASSWORD,'displayName':'昵称','requestedRole':'mentor','mentorKey':TEST_MENTOR_KEY,'role':'admin'},c)
        self.assertEqual(r.status_code,202);u=User.objects.get(email='new@example.invalid');self.assertEqual(u.role,'student');self.assertEqual(u.requested_role,'mentor');self.assertFalse(u.is_staff)
        self.assertEqual(MailJob.objects.filter(recipient=u.email).count(),1);self.assertFalse(EmailAddress.objects.get(user=u).verified)
    def test_unverified_cannot_login_and_can_resend(self):
        u=person('unverified',verified=False);c=Client()
        self.assertEqual(self.post('/api/auth/login',{'email':u.email,'password':PASSWORD},c).status_code,401)
        data={'email':u.email,'password':PASSWORD,'displayName':'再试一次'}
        self.assertEqual(self.post('/api/auth/register',data,c).status_code,202);self.assertTrue(MailJob.objects.filter(recipient=u.email).exists())
    def test_allauth_verification_login_and_password_reset(self):
        u=person('verify',verified=False);c=Client();code=EmailConfirmationHMAC(EmailAddress.objects.get(user=u)).key
        self.assertEqual(self.post('/api/auth/verify',{'email':u.email,'code':code,'password':PASSWORD},c).status_code,200)
        self.assertEqual(self.post('/api/auth/login',{'email':u.email,'password':PASSWORD},c).json()['user']['role'],'student')
        self.post('/api/auth/forgot',{'email':u.email},c);job=MailJob.objects.filter(recipient=u.email).latest('created_at');token=re.search(r'验证码是：([0-9]{6})',job.body).group(1)
        data={'email':u.email,'code':token,'password':'Changed-test-password-28!'}
        self.assertEqual(self.post('/api/auth/reset',data,c).status_code,200);self.assertEqual(self.post('/api/auth/reset',data,c).status_code,400)
        u.refresh_from_db();self.assertTrue(u.check_password(data['password']))
    def test_auth_csrf_is_enforced(self):
        c=Client(enforce_csrf_checks=True);c.get('/api/auth/session')
        data={'email':self.s.email,'password':PASSWORD}
        self.assertEqual(self.post('/api/auth/login',data,c).status_code,403)
        self.assertEqual(c.post('/api/auth/login',json.dumps(data),content_type='application/json',HTTP_X_CSRFTOKEN=c.cookies['csrftoken'].value).status_code,200)
    def test_session_required_for_workspace(self):
        self.assertEqual(Client().get('/api/workspace').status_code,403)
    def test_last_conversation_persists_across_workspace_reads_and_relogin(self):
        conversation=record(self.s,'conversations',title='继续上次对话',messages=[])
        response=self.client.patch('/api/workspace',json.dumps({'preferences':{'lastConversationId':conversation.id}}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get('/api/workspace').json()['lastConversationId'],conversation.id)
        self.client.logout();self.client.force_login(self.s,backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.client.get('/api/workspace').json()['lastConversationId'],conversation.id)
    def test_last_conversation_cannot_select_other_account_or_other_collection(self):
        for row in [record(self.other,'conversations',title='他人私聊',messages=[]),record(self.s,'writingDrafts',title='文稿')]:
            response=self.client.patch('/api/workspace',json.dumps({'preferences':{'lastConversationId':row.id}}),content_type='application/json')
            self.assertEqual(response.status_code,403)
        self.assertEqual(self.client.get('/api/workspace').json()['lastConversationId'],'')
    def test_last_conversation_rejects_malformed_values_atomically(self):
        for value in [None,[],{},False,12,'','a'*101]:
            response=self.client.patch('/api/workspace',json.dumps({'preferences':{'lastConversationId':value,'integritySettings':{'competitionPeriod':True}}}),content_type='application/json')
            self.assertEqual(response.status_code,400)
        self.assertFalse(self.client.get('/api/workspace').json()['integritySettings']['competitionPeriod'])
    def test_last_conversation_survives_ordinary_saves_and_is_account_scoped(self):
        conversation=record(self.s,'conversations',title='我的对话',messages=[])
        save_workspace(self.s,{}, {'lastConversationId':conversation.id})
        save_workspace(self.s,{}, {'integritySettings':{'competitionPeriod':True}})
        self.assertEqual(workspace_json(self.s)['lastConversationId'],conversation.id)
        self.assertTrue(workspace_json(self.s)['integritySettings']['competitionPeriod'])
        self.assertEqual(workspace_json(self.other)['lastConversationId'],'')
    @override_settings(INSTANCE_KIND='test',INSTANCE_LABEL='功能验收环境',INSTANCE_PRIMARY_URL='http://127.0.0.1:8765')
    def test_test_instance_advertises_explicit_original_data_entry(self):
        data=Client().get('/api/capabilities').json()
        self.assertEqual(data['instance'],{'kind':'test','label':'功能验收环境','primaryUrl':'http://127.0.0.1:8765'})
        self.assertTrue(data['auth']);self.assertNotIn('E2B_API_KEY',str(data))
    def test_isolated_session_cookie_does_not_log_out_daily_account(self):
        from django.contrib.sessions.models import Session
        with override_settings(SESSION_COOKIE_NAME='sessionid'):
            daily=Client();daily.force_login(self.s,backend='django.contrib.auth.backends.ModelBackend');daily_key=daily.cookies['sessionid'].value
        isolated=Client();isolated.cookies['sessionid']=daily_key
        with override_settings(SESSION_COOKIE_NAME='mathmodel_isolated_session'):
            self.assertIsNone(isolated.get('/api/auth/session').json()['user'])
            self.assertEqual(self.post('/api/auth/login',{'email':self.s.email,'password':PASSWORD},isolated).status_code,200)
            self.assertIn('mathmodel_isolated_session',isolated.cookies)
            isolated.defaults['HTTP_X_MM_ACCOUNT']=str(self.s.id)
            self.assertEqual(self.post('/api/auth/logout',{},isolated).status_code,200)
        self.assertTrue(Session.objects.filter(session_key=daily_key).exists())
        with override_settings(SESSION_COOKIE_NAME='sessionid'):
            self.assertEqual(daily.get('/api/auth/session').json()['user']['id'],str(self.s.id))
    def test_test_instance_settings_require_isolated_data_and_cookie(self):
        env={**os.environ,'PYTHONUTF8':'1','MATHMODEL_DEBUG':'1','MATHMODEL_INSTANCE_KIND':'test','DJANGO_SECRET_KEY':'isolated-settings-test-only','MATHMODEL_PRIMARY_URL':''}
        env.pop('MATHMODEL_SESSION_COOKIE_NAME',None)
        command=[sys.executable,'-c','import config.settings as s; print(s.SESSION_COOKIE_NAME)']
        env['MATHMODEL_DATA_DIR']=str(settings.BASE_DIR/'.data')
        rejected=subprocess.run(command,cwd=settings.BASE_DIR/'backend',env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
        self.assertNotEqual(rejected.returncode,0)
        self.assertIn('验收环境必须使用独立的 MATHMODEL_DATA_DIR',rejected.stderr)
        env['MATHMODEL_DATA_DIR']=self.temp.name
        isolated=subprocess.run(command,cwd=settings.BASE_DIR/'backend',env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
        self.assertEqual(isolated.returncode,0,isolated.stderr)
        self.assertRegex(isolated.stdout.strip(),r'^mathmodel_session_[a-f0-9]{12}$')
        env['MATHMODEL_SESSION_COOKIE_NAME']='sessionid'
        rejected=subprocess.run(command,cwd=settings.BASE_DIR/'backend',env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
        self.assertNotEqual(rejected.returncode,0)
        self.assertIn('验收环境禁止共用日常账号',rejected.stderr)
    def test_forged_person_and_role_ignored_by_profile(self):
        r=self.client.patch('/api/profile',json.dumps({'role':'admin','email':'changed@example.invalid','displayName':'昵称','trackUsage':False}),content_type='application/json')
        self.assertEqual(r.status_code,200);self.s.refresh_from_db();self.assertEqual(self.s.role,'student');self.assertEqual(self.s.email,'student@example.invalid');self.assertFalse(self.s.track_usage)
    def test_student_cannot_create_school_task_or_supervise(self):
        task={'id':key(),'title':'学生练习','scope':'校内资料','attachmentIds':[]}
        self.assertEqual(self.patch({'tasks':[task]}).status_code,403)
        self.assertEqual(self.patch({'teams':[{'id':key(),'name':'冒充导师'}]}).status_code,403)
    def test_owner_and_revision_guards(self):
        row=record(self.other,'tasks',title='私有任务',attachmentIds=[])
        self.assertEqual(self.patch({'tasks':[{**row.payload,'title':'篡改','_revision':1}]}).status_code,403)
        own=record(self.s,'tasks',title='练习',attachmentIds=[])
        r=self.patch({'tasks':[{**own.payload,'title':'修改','_revision':1}]});self.assertEqual(r.status_code,200)
        self.assertEqual(self.patch({'tasks':[{**own.payload,'title':'旧页覆盖','_revision':1}]}).status_code,409)
    def test_team_member_cannot_read_drafts_or_other_members(self):
        self.team.payload.update(messages=[{'id':key(),'title':'导师草稿','body':'保密'}],members=[{'email':'private@example.invalid'}]);self.team.save()
        row=next(t for t in workspace_json(self.s)['teams'] if t['id']==self.team.id)
        self.assertEqual(row['messages'],[]);self.assertEqual(row['members'],[])
    def test_school_submission_does_not_expand_supervision(self):
        task=record(self.m,'tasks',title='全校任务',audience='school',attachmentIds=[]);task.scope='school';task.save()
        p=project(self.other,task);sid=key();save_workspace(self.other,{'taskSubmissions':[{'id':sid,'taskId':task.id,'projectId':p.id}]},{})
        self.assertFalse(managed_users(self.m).filter(id=self.other.id).exists());self.assertFalse(can_read(self.m,p))
        self.assertTrue(can_read(self.m,Record.objects.get(id=sid)))
    def test_submission_snapshot_immutable_and_only_task_mentor_reviews(self):
        task=record(self.m,'tasks',title='团队任务',attachmentIds=[]);task.team=self.team;task.save();p=project(self.s,task);sid=key()
        save_workspace(self.s,{'taskSubmissions':[{'id':sid,'taskId':task.id,'projectId':p.id,'personId':str(self.other.id),'snapshot':{'fake':True}}]},{})
        sub=Record.objects.get(id=sid);self.assertEqual(sub.payload['personId'],str(self.s.id));self.assertEqual(sub.payload['snapshot']['stages'][0]['content'],'真实笔记')
        data={**sub.payload,'feedback':'学生伪造反馈','_revision':1};self.assertEqual(self.patch({'taskSubmissions':[data]}).status_code,403)
        self.client.force_login(self.m,backend='django.contrib.auth.backends.ModelBackend');data.update(feedback='请补充验证',status='reviewed')
        self.assertEqual(self.patch({'taskSubmissions':[data]}).status_code,200)
        self.client.force_login(self.other,backend='django.contrib.auth.backends.ModelBackend');self.assertEqual(self.patch({'taskSubmissions':[data]}).status_code,403)
    def test_student_task_owner_cannot_review_others(self):
        task=record(self.other,'tasks',title='历史错误共享任务');sub=record(self.s,'taskSubmissions',taskId=task.id,feedback='',status='submitted')
        self.assertFalse(editable(self.other,sub));self.assertFalse(can_read(self.other,sub))
    def test_paper_review_access_is_fixed_to_submitted_paper_ids(self):
        task=record(self.m,'tasks',title='任务');task.team=self.team;task.save();p=project(self.s,task)
        f=record(self.s,'resources',name='论文.txt');paper=record(self.s,'papers',projectId=p.id,fileId=f.id,scores=[None]*7)
        sid=key();save_workspace(self.s,{'taskSubmissions':[{'id':sid,'taskId':task.id,'projectId':p.id}]},{})
        self.assertTrue(can_read(self.m,paper));self.assertTrue(editable(self.m,paper));self.assertTrue(can_read(self.m,f))
        later=record(self.s,'papers',projectId=p.id,fileId=f.id);self.assertFalse(can_read(self.m,later))
        guest=person('guest','mentor');Membership.objects.create(team=self.team,user=guest);self.assertFalse(editable(guest,paper))
    def test_real_usage_dedup_and_idle_session(self):
        for module in ['建模工作台','建模训练','论文写作']:self.assertEqual(self.post('/api/usage/heartbeat',{'module':module}).status_code,200)
        self.assertEqual(Usage.objects.filter(user=self.s).count(),1);row=Usage.objects.get(user=self.s);self.assertEqual(row.activity,'training');self.assertEqual(len(row.modules),3)
        Usage.objects.filter(pk=row.pk).update(ended_at=timezone.now()-timedelta(minutes=6));self.post('/api/usage/heartbeat',{'module':'知识库阅读'})
        self.assertEqual(Usage.objects.filter(user=self.s).count(),2)
    def test_usage_optout_and_source_cannot_be_forged(self):
        self.s.track_usage=False;self.s.save();self.assertIsNone(self.post('/api/usage/heartbeat',{'module':'建模训练','personId':str(self.other.id)}).json()['record']);self.assertFalse(Usage.objects.exists())
    def test_email_consent_limit_dedup_and_local_only(self):
        job=queue_learning(self.m,self.s,'学习提醒','真实内容','same');self.assertEqual(job.id,queue_learning(self.m,self.s,'学习提醒','真实内容','same').id)
        for i in range(20):queue_learning(self.m,self.s,'提醒','内容','different'+str(i))
        self.assertEqual(MailJob.objects.filter(kind='learning').count(),10)
        with patch('platform_app.mail.SMTPBackend') as smtp:process_mail();smtp.assert_not_called()
        self.assertEqual(set(MailJob.objects.values_list('status',flat=True)),{'local'})
    def test_queued_mail_cancelled_after_membership_or_consent_change(self):
        j=queue_learning(self.m,self.s,'提醒','内容','cancel');Membership.objects.filter(team=self.team,user=self.s).delete();process_mail();j.refresh_from_db();self.assertEqual(j.status,'cancelled')
    def test_inactive_accounts_do_not_receive_learning_mail(self):
        self.s.is_active=False;self.s.save();self.assertIsNone(queue_learning(self.m,self.s,'提醒','内容','inactive'))
    def test_signed_unsubscribe_works_without_login(self):
        token=signing.dumps({'user':str(self.s.id)},salt='learning-unsubscribe');self.assertEqual(self.post('/api/reminders/unsubscribe',{'token':token},Client()).status_code,200)
        self.s.refresh_from_db();self.assertFalse(self.s.reminder_consent);self.assertIsNone(queue_learning(self.m,self.s,'提醒','内容','optout'))
    def test_invitation_identity_and_renewal(self):
        self.client.force_login(self.m,backend='django.contrib.auth.backends.ModelBackend');url='/api/teams/'+self.team.id+'/invite'
        self.assertEqual(self.post(url,{'email':self.other.email}).status_code,200);inv=Invitation.objects.get(team=self.team,email=self.other.email);old=MailJob.objects.get(kind='invite')
        token=re.search(r'\?invite=([^#\s]+)',old.body).group(1)
        self.client.force_login(self.s,backend='django.contrib.auth.backends.ModelBackend');self.assertEqual(self.post('/api/invitations/accept',{'token':token}).status_code,403)
        Invitation.objects.filter(pk=inv.pk).update(issued_at=timezone.now()-timedelta(days=8));self.client.force_login(self.m,backend='django.contrib.auth.backends.ModelBackend');self.post(url,{'email':self.other.email})
        self.assertEqual(MailJob.objects.filter(kind='invite').count(),2);new=MailJob.objects.filter(kind='invite').latest('created_at');new_token=re.search(r'\?invite=([^#\s]+)',new.body).group(1)
        self.client.force_login(self.other,backend='django.contrib.auth.backends.ModelBackend');self.assertEqual(self.post('/api/invitations/accept',{'token':token}).status_code,400);self.assertEqual(self.post('/api/invitations/accept',{'token':new_token}).status_code,200)
    def test_publish_requires_current_revision_and_exact_recipients(self):
        mid=key();member=key();self.team.payload.update(members=[{'id':member,'name':'student','identifier':self.s.email,'role':'学生'}],messages=[{'id':mid,'title':'团队通知','body':'请提交训练','recipientIds':[member],'attachmentIds':[],'status':'draft'}]);self.team.save()
        self.client.force_login(self.m,backend='django.contrib.auth.backends.ModelBackend');url='/api/teams/'+self.team.id+'/publish'
        self.assertEqual(self.post(url,{'messageId':mid,'revision':0}).status_code,409);self.assertEqual(self.post(url,{'messageId':mid,'revision':1}).status_code,200)
        self.assertEqual(Record.objects.filter(collection='notifications',payload__personId=str(self.s.id)).count(),1)
        self.assertFalse(Record.objects.filter(collection='notifications',payload__personId=str(self.other.id)).exists())
        self.assertEqual(self.post(url,{'messageId':mid,'revision':2}).json()['duplicate'],True)
    def test_file_upload_acl_and_async_text_extraction(self):
        rid=key();r=self.client.post('/api/files',{'metadata':json.dumps({'id':rid,'kind':'knowledge','scope':'个人资料','category':'建模基础'}),'file':SimpleUploadedFile('原文.txt','实际数学资料'.encode())})
        self.assertEqual(r.status_code,201);parse_pending();asset=Asset.objects.get(record_id=rid);self.assertEqual(asset.parse_status,'ready');self.assertEqual(Record.objects.get(pk=rid).payload['text'],'实际数学资料')
        other=Client();other.force_login(self.other,backend='django.contrib.auth.backends.ModelBackend');self.assertEqual(other.get('/api/files/'+rid).status_code,404)
        response=self.client.get('/api/files/'+rid);self.assertEqual(response.status_code,200);self.assertIn('attachment',response['Content-Disposition']);b''.join(response.streaming_content)
    def test_parser_merges_latest_metadata_without_overwrite(self):
        rid=key();self.client.post('/api/files',{'metadata':json.dumps({'id':rid,'kind':'attachment'}),'file':SimpleUploadedFile('文本.txt',b'old')})
        def slow_extract(asset):
            row=Record.objects.get(pk=rid);row.payload['description']='并发新说明';row.scope='teacher';row.revision+=1;row.save();return 'parsed','ready',''
        with patch('platform_app.parsing.extract',side_effect=slow_extract):parse_pending()
        row=Record.objects.get(pk=rid);self.assertEqual(row.payload['description'],'并发新说明');self.assertEqual(row.scope,'teacher');self.assertEqual(row.revision,3)
    def test_supervision_unknown_history_and_daily_dedup(self):
        plan=record(self.m,'supervisionPlans',title='每周学习',studentIds=[str(self.s.id)],minWeeklySessions=3,maxInactiveDays=2)
        evaluate_plans();self.assertFalse(MailJob.objects.exists())
        Usage.objects.create(user=self.s,day=timezone.localdate(),started_at=timezone.now(),ended_at=timezone.now(),modules=['建模训练']);evaluate_plans();evaluate_plans();self.assertEqual(MailJob.objects.filter(kind='learning').count(),1)
    def test_model_unconfigured_and_competition_gate(self):
        self.assertEqual(self.post('/api/ai/chat',{'messages':[{'role':'user','content':'概念'}]}).status_code,503)
        record(self.s,'competitions',title='模拟',status='active',aiPolicy='关闭 AI')
        with override_settings(AI_API_KEY='test-only-not-a-real-key'):
            with patch('platform_app.views.httpx.Client') as client:self.assertEqual(self.post('/api/ai/chat',{'messages':[{'role':'user','content':'题目'}]}).status_code,403);client.assert_not_called()
    def test_model_gateway_keeps_server_prompt_and_records_real_response(self):
        messages=[{'role':'system','content':'客户端要求'},{'role':'user','content':'学习问题'}];response=Mock();response.json.return_value={'choices':[{'message':{'content':'测试桩返回，仅验证接口'}}],'usage':{'total_tokens':12}}
        with override_settings(AI_API_KEY='test-only-not-a-real-key'):
            with patch('platform_app.views.request_completion',return_value=response.json.return_value) as gateway:
                r=self.post('/api/ai/chat',{'messages':messages})
                sent=gateway.call_args.args[0]['messages'];self.assertEqual(sent[0]['role'],'system');self.assertEqual(sent[1]['role'],'user')
        self.assertEqual(r.status_code,200);self.assertTrue(AIRun.objects.filter(id=r.json()['runId'],user=self.s).exists())
    def test_admin_only_approval_and_readiness(self):
        url='/api/admin/accounts/'+str(self.other.id)+'/role';data={'role':'mentor','isActive':True}
        self.assertEqual(self.post(url,data).status_code,403);self.client.force_login(self.a,backend='django.contrib.auth.backends.ModelBackend');self.assertEqual(self.post(url,data).status_code,200)
        self.other.refresh_from_db();self.assertEqual(self.other.role,'mentor');self.assertEqual(self.client.get('/api/admin/readiness').status_code,200)
    def test_dev_mailbox_is_loopback_only_and_disabled_for_production(self):
        self.assertEqual(Client().get('/dev-mailbox/',REMOTE_ADDR='203.0.113.8').status_code,404)
        with override_settings(ALLOW_DEV_MAILBOX=False):self.assertEqual(Client().get('/dev-mailbox/').status_code,404)
    @override_settings(QA_ADMIN_MAILBOX=True,INSTANCE_KIND='test')
    def test_container_qa_mailbox_requires_active_fixed_admin(self):
        self.assertEqual(Client().get('/dev-mailbox/',REMOTE_ADDR='172.20.0.1').status_code,404)
        self.assertFalse(Client().get('/api/capabilities').json()['devMailbox'])
        self.assertEqual(self.client.get('/dev-mailbox/',REMOTE_ADDR='172.20.0.1').status_code,404)
        self.assertFalse(self.client.get('/api/capabilities').json()['devMailbox'])
        self.client.force_login(self.m,backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.client.get('/dev-mailbox/',REMOTE_ADDR='172.20.0.1').status_code,404)
        self.client.force_login(self.a,backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.client.get('/dev-mailbox/',REMOTE_ADDR='172.20.0.1').status_code,200)
        self.assertTrue(self.client.get('/api/capabilities').json()['devMailbox'])
        with override_settings(ALLOW_DEV_MAILBOX=False):self.assertEqual(self.client.get('/dev-mailbox/').status_code,404)
        self.a.is_active=False;self.a.save()
        self.assertEqual(self.client.get('/dev-mailbox/',REMOTE_ADDR='172.20.0.1').status_code,404)
    def test_arbitrary_static_paths_cannot_expose_database_or_config(self):
        for url in ['/.env.local','/.data/platform.sqlite3','/backend/config/settings.py','/README.md']:self.assertEqual(Client().get(url).status_code,404)
    def test_pre_registration_cannot_keep_an_attackers_password(self):
        victim=person('victim',verified=False);attacker_password=PASSWORD;new_password='Only-email-owner-knows-852!';c=Client()
        self.post('/api/auth/register',{'email':victim.email,'displayName':'邮箱主人','password':new_password},c)
        code=EmailConfirmationHMAC(EmailAddress.objects.get(user=victim)).key
        self.assertEqual(self.post('/api/auth/verify',{'email':victim.email,'code':code,'password':new_password},c).status_code,200)
        self.assertEqual(self.post('/api/auth/login',{'email':victim.email,'password':attacker_password},c).status_code,401)
        self.assertEqual(self.post('/api/auth/login',{'email':victim.email,'password':new_password},c).status_code,200)
        self.assertEqual(self.post('/api/auth/verify',{'email':victim.email,'code':code,'password':PASSWORD},c).status_code,400)
    def test_registration_does_not_create_a_usable_password_before_email_proof(self):
        self.post('/api/auth/register',{'email':'proof@example.invalid','displayName':'邮箱先行','password':PASSWORD},Client())
        self.assertFalse(User.objects.get(email='proof@example.invalid').has_usable_password())
    def test_account_binding_prevents_a_stale_tab_writing_to_new_account(self):
        self.client.force_login(self.other,backend='django.contrib.auth.backends.ModelBackend')
        self.client.defaults['HTTP_X_MM_ACCOUNT']=str(self.s.id)
        self.assertEqual(self.patch({'tasks':[{'id':key(),'title':'旧账号草稿','attachmentIds':[]}]}).status_code,409)
        self.assertFalse(Record.objects.filter(collection='tasks',owner=self.other).exists())
        self.assertEqual(self.client.get('/api/auth/session').status_code,409)
    def test_authenticated_writes_require_an_expected_account(self):
        self.client.defaults.pop('HTTP_X_MM_ACCOUNT',None)
        self.assertEqual(self.post('/api/usage/heartbeat',{'module':'建模训练'}).status_code,409)
    def test_demoted_mentor_cannot_invite_or_publish(self):
        self.m.role='student';self.m.save();self.client.force_login(self.m,backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.post('/api/teams/'+self.team.id+'/invite',{'email':self.other.email}).status_code,403)
        self.assertEqual(self.post('/api/teams/'+self.team.id+'/publish',{'messageId':key(),'revision':1}).status_code,403)
    def test_workspace_submission_roundtrip_with_display_metadata(self):
        task=record(self.m,'tasks',title='团队任务',attachmentIds=[]);task.team=self.team;task.save();p=project(self.s,task)
        save_workspace(self.s,{'taskSubmissions':[{'id':key(),'taskId':task.id,'projectId':p.id}]},{})
        row=workspace_json(self.m)['taskSubmissions'][0];self.assertIn('_studentName',row);row.update(feedback='真实导师反馈',status='reviewed')
        self.client.force_login(self.m,backend='django.contrib.auth.backends.ModelBackend');self.assertEqual(self.patch({'taskSubmissions':[row]}).status_code,200)
    def test_teacher_paper_feedback_does_not_need_live_project_access(self):
        task=record(self.m,'tasks',title='团队任务');task.team=self.team;task.save();p=project(self.s,task);file=record(self.s,'resources',name='原件.txt',text='原文')
        paper=record(self.s,'papers',title='论文',projectId=p.id,fileId=file.id,scores=[None]*7,annotations=[],aiReviews=[],findings=[])
        save_workspace(self.s,{'taskSubmissions':[{'id':key(),'taskId':task.id,'projectId':p.id}]},{})
        self.assertFalse(can_read(self.m,p));row=workspace_json(self.m)['papers'][0];row.update(scores=[85]*7,scoredAt=timezone.now().isoformat())
        self.client.force_login(self.m,backend='django.contrib.auth.backends.ModelBackend');self.assertEqual(self.patch({'papers':[row]}).status_code,200)
    def test_model_paper_run_binds_paper_and_original_snapshot(self):
        file=record(self.s,'resources',name='论文.txt',text='真实原文')
        p=record(self.s,'papers',title='论文',fileId=file.id,scores=[None]*7,annotations=[],findings=[],aiReviews=[])
        response=Mock();response.json.return_value={'choices':[{'message':{'content':'{"summary":"测试桩","issues":[]}'}}]}
        data={'paperId':p.id,'messages':[{'role':'user','content':'<paper_text>\n真实原文\n</paper_text>'}]}
        with override_settings(AI_API_KEY='test-only-not-a-real-key'):
            with patch('platform_app.views.request_completion',return_value=response.json.return_value) as gateway:
                r=self.post('/api/ai/paper-review',data)
                self.assertEqual(r.status_code,200);run=AIRun.objects.get(id=r.json()['runId']);self.assertEqual(run.paper_id,p.id);self.assertEqual(run.messages[0]['role'],'system')
                bad={**data,'messages':[{'role':'user','content':'<paper_text>\n伪造原文\n</paper_text>'}]};self.assertEqual(self.post('/api/ai/paper-review',bad).status_code,409)
        other=record(self.s,'papers',title='另一篇',fileId=file.id,scores=[None]*7,annotations=[],findings=[],aiReviews=[])
        review={'id':key(),'serverRunId':str(run.id),'input':'真实原文','output':run.output,'model':run.model,'at':timezone.now().isoformat(),'provider':'forged','instruction':'伪造提示词'}
        self.assertEqual(self.patch({'papers':[{**other.payload,'aiReviews':[review],'_revision':1}]}).status_code,400)
        self.assertEqual(self.patch({'papers':[{**p.payload,'aiReviews':[review],'_revision':1}]}).status_code,200)
        p.refresh_from_db();self.assertEqual(p.payload['aiReviews'][0]['instruction'],run.messages[0]['content'])
    def test_invalid_json_root_and_stage_return_validation_errors(self):
        self.assertEqual(self.client.patch('/api/workspace','[]',content_type='application/json').status_code,400)
        self.assertEqual(self.patch({'projects':[{'id':key(),'title':'无效','stages':['bad']*8}]}).status_code,400)
    def test_mail_failure_retries_without_claiming_delivery(self):
        self.s.email='student@example.org';self.s.save()
        EmailAddress.objects.filter(user=self.s).update(email=self.s.email)
        job=queue_learning(self.m,self.s,'提醒','内容','smtp-failure')
        with override_settings(MAIL_TRANSPORT='smtp',EMAIL_HOST='smtp.example.invalid'):
            with patch('platform_app.mail.SMTPBackend') as smtp:
                smtp.return_value.__enter__.return_value.send_messages.side_effect=smtplib.SMTPDataError(451,b'temporary rejection');process_mail()
        job.refresh_from_db();self.assertEqual(job.status,'retry');self.assertEqual(job.attempts,1);self.assertGreater(job.planned_at,timezone.now())
    def test_real_smtp_does_not_send_to_fixture_domains(self):
        for suffix in ['invalid','test','localhost','example']:
            MailJob.objects.create(recipient='fixture@sub.'+suffix,subject='QA',body='fixture',dedup_key=key(),planned_at=timezone.now())
        with override_settings(MAIL_TRANSPORT='smtp',EMAIL_HOST='smtp.example.invalid'):
            with patch('platform_app.mail.SMTPBackend') as smtp:process_mail();smtp.assert_not_called()
        self.assertEqual(MailJob.objects.filter(status='cancelled',attempts=0).count(),4)
    @override_settings(MAIL_TRANSPORT='smtp')
    def test_real_email_registration_rejects_fixture_domains_before_queue(self):
        for domain in ['sub.invalid','sub.test','localhost','sub.example']:
            response=self.post('/api/auth/register',{'email':'new@'+domain,'displayName':'placeholder'},Client())
            self.assertEqual(response.status_code,400)
        self.assertFalse(MailJob.objects.exists())
    def test_real_smtp_acceptance_is_recorded_without_claiming_receipt(self):
        job=MailJob.objects.create(recipient='fixture@example.org',subject='contract only',body='not a real delivery test',dedup_key=key(),planned_at=timezone.now())
        with override_settings(MAIL_TRANSPORT='smtp',EMAIL_HOST='smtp.example.invalid'):
            with patch('platform_app.mail.SMTPBackend') as smtp:
                smtp.return_value.__enter__.return_value.send_messages.return_value=1;process_mail()
        job.refresh_from_db();self.assertEqual(job.status,'accepted');self.assertEqual(job.attempts,1)
        self.assertIn('不能据此判定已读',job.last_error)
    def test_smtp_unknown_submission_is_not_automatically_retried(self):
        job=MailJob.objects.create(recipient='fixture@example.org',subject='contract only',body='fixture',dedup_key=key(),planned_at=timezone.now())
        with override_settings(MAIL_TRANSPORT='smtp',EMAIL_HOST='smtp.example.invalid'):
            with patch('platform_app.mail.SMTPBackend') as smtp:
                smtp.return_value.__enter__.return_value.send_messages.side_effect=TimeoutError('unknown DATA reply');process_mail()
            job.refresh_from_db();self.assertEqual(job.status,'uncertain');self.assertEqual(job.attempts,1)
            with patch('platform_app.mail.SMTPBackend') as smtp:process_mail();smtp.assert_not_called()
    def test_smtp_connection_failure_is_safe_to_retry(self):
        job=MailJob.objects.create(recipient='fixture@example.org',subject='contract only',body='fixture',dedup_key=key(),planned_at=timezone.now())
        with override_settings(MAIL_TRANSPORT='smtp',EMAIL_HOST='smtp.example.invalid'):
            with patch('platform_app.mail.SMTPBackend') as smtp:
                smtp.return_value.__enter__.side_effect=TimeoutError('connect failed');process_mail()
        job.refresh_from_db();self.assertEqual(job.status,'retry');self.assertEqual(job.attempts,1)
    def test_smtp_close_failure_does_not_resend_accepted_message(self):
        job=MailJob.objects.create(recipient='fixture@example.org',subject='contract only',body='fixture',dedup_key=key(),planned_at=timezone.now())
        with override_settings(MAIL_TRANSPORT='smtp',EMAIL_HOST='smtp.example.invalid'):
            with patch('platform_app.mail.SMTPBackend') as smtp:
                smtp.return_value.__enter__.return_value.send_messages.return_value=1
                smtp.return_value.__exit__.side_effect=OSError('QUIT failed');process_mail()
        job.refresh_from_db();self.assertEqual(job.status,'accepted');self.assertEqual(job.attempts,1)
    def test_parser_failure_keeps_original(self):
        rid=key();self.client.post('/api/files',{'metadata':json.dumps({'id':rid,'kind':'paper'}),'file':SimpleUploadedFile('broken.pdf',b'not a pdf')})
        parse_pending();asset=Asset.objects.get(record_id=rid);self.assertEqual(asset.parse_status,'failed');self.assertTrue(asset.file.storage.exists(asset.file.name))
    def test_django_admin_user_pages_work_for_custom_email_model(self):
        self.a.is_staff=True;self.a.is_superuser=True;self.a.save();self.client.force_login(self.a,backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.client.get('/admin/platform_app/user/').status_code,200)
        self.assertEqual(self.client.get('/admin/platform_app/user/add/').status_code,200)

    def test_mentor_registration_rejects_missing_and_wrong_keys(self):
        for value in ['', 'incorrect-key-723']:
            self.assertEqual(self.post('/api/auth/register',{'email':'new-mentor@example.invalid','displayName':'导师','requestedRole':'mentor','mentorKey':value},Client()).status_code,403)
        self.assertFalse(User.objects.filter(email='new-mentor@example.invalid').exists())
        self.assertFalse(MailJob.objects.filter(recipient='new-mentor@example.invalid').exists())
    def test_mentor_role_requires_email_proof_and_the_shared_key(self):
        c=Client();email='new-mentor@example.invalid'
        self.assertEqual(self.post('/api/auth/register',{'email':email,'displayName':'导师','requestedRole':'mentor','mentorKey':TEST_MENTOR_KEY},c).status_code,202)
        u=User.objects.get(email=email);self.assertEqual(u.role,'student');code=EmailConfirmationHMAC(EmailAddress.objects.get(user=u)).key
        body={'email':email,'password':PASSWORD,'code':code,'requestedRole':'mentor'}
        self.assertEqual(self.post('/api/auth/verify',body,c).status_code,403);self.assertFalse(EmailAddress.objects.get(user=u).verified)
        self.assertEqual(self.post('/api/auth/verify',{**body,'mentorKey':TEST_MENTOR_KEY},c).status_code,200);u.refresh_from_db();self.assertEqual(u.role,'mentor')
        self.assertEqual(self.post('/api/auth/login',{'email':email,'password':PASSWORD},c).json()['user']['role'],'mentor')
    def test_unverified_mentor_intent_does_not_auto_promote_email_owner(self):
        u=person('preclaimed-mentor',verified=False);u.requested_role='mentor';u.save()
        code=EmailConfirmationHMAC(EmailAddress.objects.get(user=u)).key
        self.assertEqual(self.post('/api/auth/verify',{'email':u.email,'password':PASSWORD,'code':code,'requestedRole':'student'},Client()).status_code,200)
        u.refresh_from_db();self.assertEqual(u.role,'student')
    def test_fixed_admin_uses_only_separate_login(self):
        c=Client();r=self.post('/api/auth/admin-login',{'account':'admin01','password':PASSWORD},c)
        self.assertEqual(r.status_code,200);self.assertEqual(r.json()['user']['adminLogin'],'admin01');self.assertTrue(r.json()['user']['accountVerified']);self.assertFalse(r.json()['user']['emailVerified'])
        self.assertEqual(self.post('/api/auth/login',{'email':self.a.email,'password':PASSWORD},Client()).status_code,401)
        self.assertEqual(self.post('/api/auth/admin-login',{'account':self.s.email,'password':PASSWORD},Client()).status_code,401)
        self.assertEqual(self.post('/api/auth/admin-login',{'account':'admin04','password':PASSWORD},Client()).status_code,401)
    def test_fixed_admin_cannot_use_public_signup_verification_or_reset(self):
        c=Client();email=self.a.email
        self.assertEqual(self.post('/api/auth/register',{'email':email,'displayName':'接管'},c).status_code,400)
        self.assertEqual(self.post('/api/auth/verify',{'email':email,'password':PASSWORD,'code':'bad'},c).status_code,400)
        self.post('/api/auth/forgot',{'email':email},c);self.assertFalse(MailJob.objects.filter(recipient=email).exists())
    def test_unlisted_admin_role_has_no_platform_access(self):
        u=User.objects.create_user('unlisted@example.invalid',PASSWORD,role='admin',is_staff=True,is_superuser=True)
        EmailAddress.objects.create(user=u,email=u.email,verified=True,primary=True)
        c=Client();c.force_login(u,backend='django.contrib.auth.backends.ModelBackend');self.assertIsNone(c.get('/api/auth/session').json()['user']);self.assertEqual(c.get('/api/workspace').status_code,403)
        self.assertEqual(c.get('/admin/').status_code,302)
    def test_django_admin_alias_login_and_fixed_identity_protection(self):
        c=Client();r=c.post('/admin/login/?next=/admin/',{'username':'admin01','password':PASSWORD,'next':'/admin/'})
        self.assertEqual(r.status_code,302);self.assertEqual(c.get('/admin/').status_code,200)
        url='/admin/platform_app/user/'+str(self.a.id)+'/delete/'
        self.assertEqual(c.get(url).status_code,403)
    def test_provisioning_keeps_exactly_three_admins_and_is_idempotent(self):
        # An isolated temporary directory and test database only.
        self.a.delete();RegistrationPolicy.objects.all().delete()
        with override_settings(DATA_DIR=Path(self.temp.name)):
            output=StringIO();call_command('provision_access',stdout=output);path=Path(self.temp.name)/'private-access'/'access-credentials.json';delivery=json.loads(path.read_text('utf-8'))
            self.assertEqual(User.objects.filter(role='admin').count(),3);self.assertEqual(set(User.objects.exclude(admin_login=None).values_list('admin_login',flat=True)),set(ADMIN_LOGINS))
            policy=RegistrationPolicy.objects.get();self.assertNotEqual(policy.mentor_key_hash,delivery['mentorKey']);self.assertNotIn(delivery['mentorKey'],output.getvalue())
            hashes=dict(User.objects.filter(role='admin').values_list('admin_login','password'));contents=path.read_bytes();call_command('provision_access',stdout=StringIO())
            self.assertEqual(contents,path.read_bytes());self.assertEqual(hashes,dict(User.objects.filter(role='admin').values_list('admin_login','password')))
            for row in delivery['admins']:
                self.assertEqual(self.post('/api/auth/admin-login',{'account':row['account'],'password':row['initialPassword']},Client()).status_code,200)
            self.assertEqual(Client().get('/.data/access-credentials.json').status_code,404)
    def test_provisioning_does_not_take_over_reserved_email(self):
        self.a.delete();RegistrationPolicy.objects.all().delete();victim=User.objects.create_user(ADMIN_EMAILS['admin01'],PASSWORD)
        with override_settings(DATA_DIR=Path(self.temp.name)):
            with self.assertRaises(CommandError):call_command('provision_access',stdout=StringIO())
        victim.refresh_from_db();self.assertEqual(victim.role,'student');self.assertIsNone(victim.admin_login);self.assertFalse(RegistrationPolicy.objects.exists())
    def test_provisioning_aborts_before_plaintext_when_permission_setup_fails(self):
        self.a.delete();RegistrationPolicy.objects.all().delete()
        with override_settings(DATA_DIR=Path(self.temp.name)):
            with patch('platform_app.private_storage.protect_private_file',side_effect=OSError('test ACL failure')):
                with self.assertRaises(CommandError):call_command('provision_access',stdout=StringIO())
            self.assertFalse((Path(self.temp.name)/'private-access'/'access-credentials.json').exists())
            self.assertEqual(list((Path(self.temp.name)/'private-access').iterdir()),[])
            self.assertFalse(RegistrationPolicy.objects.exists());self.assertFalse(User.objects.filter(role='admin').exists())
            call_command('provision_access',stdout=StringIO())
        self.assertEqual(User.objects.filter(role='admin').count(),3)
    def test_provisioning_checks_existing_permissions_before_reading_credentials(self):
        self.a.delete();RegistrationPolicy.objects.all().delete()
        with override_settings(DATA_DIR=Path(self.temp.name)):
            call_command('provision_access',stdout=StringIO())
            with patch('platform_app.private_storage.protect_private_file',side_effect=OSError('test ACL failure')):
                with self.assertRaises(CommandError):call_command('provision_access',stdout=StringIO())
        self.assertEqual(User.objects.filter(role='admin').count(),3)

    def legacy_library(self,unsafe_path=False):
        folder=Path(self.temp.name)/'legacy';folder.mkdir();(folder/'files').mkdir();raw='真实来源附件'.encode();(folder/'files/source.txt').write_bytes(raw)
        db=folder/'library.sqlite';connection=sqlite3.connect(db)
        connection.executescript('''CREATE TABLE library_resources(id TEXT,title TEXT,category TEXT,summary TEXT,note TEXT,body_text TEXT,tags_json TEXT,source_label TEXT,source_url TEXT,availability TEXT,kind TEXT,created_at TEXT);
        CREATE TABLE library_assets(id TEXT,sha256 TEXT,path TEXT,size INTEGER,mime TEXT,original_name TEXT);
        CREATE TABLE library_resource_assets(resource_id TEXT,asset_id TEXT,label TEXT,role TEXT);''')
        connection.execute('INSERT INTO library_resources VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',('kb_testentry','旧库真实知识','数学建模理论','来源摘要','','知识正文：线性规划','["线性规划"]','来源知识库','https://example.invalid/source','本地正文','知识卡',timezone.now().isoformat()))
        connection.execute('INSERT INTO library_assets VALUES (?,?,?,?,?,?)',('asset-test',hashlib.sha256(raw).hexdigest(),'../outside.txt' if unsafe_path else 'files/source.txt',len(raw),'text/plain','source.txt'))
        connection.execute('INSERT INTO library_resource_assets VALUES (?,?,?,?)',('kb_testentry','asset-test','来源附件','source'));connection.commit();connection.close();return db
    def test_admin_upload_defaults_to_shared_knowledge_and_is_visible_to_every_role(self):
        self.client.force_login(self.a,backend='django.contrib.auth.backends.ModelBackend');rid=key()
        result=self.client.post('/api/files',{'metadata':json.dumps({'id':rid,'kind':'knowledge','category':'数学建模理论'}),'file':SimpleUploadedFile('公共方法.txt','共同知识正文'.encode())})
        self.assertEqual(result.status_code,201);self.assertEqual(result.json()['scope'],'公共知识库');self.assertEqual(Record.objects.get(pk=rid).scope,'public');parse_pending()
        for user in [self.s,self.other,self.m,self.a,person('future-account')]:
            c=Client();c.force_login(user,backend='django.contrib.auth.backends.ModelBackend');row=next(r for r in c.get('/api/workspace').json()['resources'] if r['id']==rid);self.assertEqual(row['text'],'共同知识正文')
            response=c.get('/api/files/'+rid);self.assertEqual(response.status_code,200);b''.join(response.streaming_content)
        self.assertIn(Client().get('/api/files/'+rid).status_code,[401,403])
    def test_nonadmin_cannot_upload_or_reclassify_into_shared_knowledge(self):
        for user in [self.s,self.m]:
            c=Client();c.force_login(user,backend='django.contrib.auth.backends.ModelBackend');rid=key()
            self.assertEqual(c.post('/api/files',{'metadata':json.dumps({'id':rid,'kind':'knowledge','scope':'公共知识库'}),'file':SimpleUploadedFile('伪造公共.txt',b'private')}).status_code,403);self.assertFalse(Record.objects.filter(pk=rid).exists())
            row=record(user,'resources',name='私有.txt',kind='knowledge',text='私有内容',scope='个人资料');data={**row.payload,'scope':'公共知识库','_revision':1}
            self.assertEqual(c.patch('/api/workspace',json.dumps({'changes':{'resources':[data]}}),content_type='application/json').status_code,403)
    def test_shared_library_import_copies_source_links_and_is_idempotent(self):
        source=self.legacy_library();before=hashlib.sha256(source.read_bytes()).hexdigest();call_command('import_shared_library',source=str(source),stdout=StringIO())
        row=Record.objects.get(pk='kb_testentry');self.assertEqual(row.scope,'public');self.assertEqual(row.payload['scope'],'公共知识库');self.assertEqual(row.payload['sourceUrl'],'https://example.invalid/source')
        original=Record.objects.get(pk=row.payload['libraryAssetIds'][0]['id']);asset=Asset.objects.get(record=original)
        self.assertEqual(Path(asset.file.path).read_bytes(),'真实来源附件'.encode());self.assertNotEqual(Path(asset.file.path),source.parent/'files/source.txt')
        row.payload['description']='管理员后续补充';row.save();call_command('import_shared_library',source=str(source),stdout=StringIO());row.refresh_from_db();self.assertEqual(row.payload['description'],'管理员后续补充');self.assertEqual(Record.objects.filter(payload__libraryImport='shared-library-v1').count(),2)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)
        for user in [self.s,self.m]:
            c=Client();c.force_login(user,backend='django.contrib.auth.backends.ModelBackend');self.assertTrue(any(r['id']==row.id for r in c.get('/api/workspace').json()['resources']))
            response=c.get('/api/files/'+original.id);self.assertEqual(response.status_code,200);b''.join(response.streaming_content)
        self.assertEqual(self.patch({'resources':[{**row.payload,'description':'学生改公共库','_revision':row.revision}]}).status_code,403)
    def test_shared_library_dry_run_does_not_create_records_or_files(self):
        source=self.legacy_library();call_command('import_shared_library',source=str(source),dry_run=True,stdout=StringIO());self.assertFalse(Record.objects.filter(pk='kb_testentry').exists());self.assertFalse((Path(self.temp.name)/'shared-library').exists())
    def test_shared_library_import_rejects_paths_outside_the_source(self):
        source=self.legacy_library(unsafe_path=True)
        with self.assertRaises(CommandError):call_command('import_shared_library',source=str(source),stdout=StringIO())
        self.assertFalse(Record.objects.filter(pk='kb_testentry').exists())
    def test_shared_library_import_rejects_corrupt_originals(self):
        source=self.legacy_library();(source.parent/'files/source.txt').write_bytes(b'corrupt')
        with self.assertRaises(CommandError):call_command('import_shared_library',source=str(source),stdout=StringIO())
        self.assertFalse(Record.objects.filter(pk='kb_testentry').exists())
    def test_client_cannot_forge_library_source_metadata(self):
        row=record(self.s,'resources',name='自有.txt',kind='knowledge',text='私人正文',scope='个人资料')
        self.assertEqual(self.patch({'resources':[{**row.payload,'libraryImport':'shared-library-v1','librarySourceId':'kb_testentry','_revision':1}]}).status_code,400)
        row.refresh_from_db();self.assertNotIn('libraryImport',row.payload)
    def test_import_collision_never_trusts_a_marker_on_other_records(self):
        source=self.legacy_library();Record.objects.create(id='kb_testentry',collection='resources',owner=self.s,scope='private',payload={'id':'kb_testentry','name':'保留的私人资料','kind':'knowledge','libraryImport':'shared-library-v1','librarySourceId':'kb_testentry'})
        with self.assertRaises(CommandError):call_command('import_shared_library',source=str(source),stdout=StringIO())
        self.assertEqual(Record.objects.get(pk='kb_testentry').owner_id,self.s.id);self.assertEqual(Record.objects.filter(payload__libraryImport='shared-library-v1').count(),1)
    def test_import_snapshot_failure_can_be_retried_without_partial_final_file(self):
        source=self.legacy_library()
        with patch('platform_app.management.commands.import_shared_library.os.fsync',side_effect=OSError('test interrupted write')):
            with self.assertRaises(OSError):call_command('import_shared_library',source=str(source),stdout=StringIO())
        entries=Path(self.temp.name)/'shared-library/entries';self.assertEqual(list(entries.iterdir()),[]);self.assertFalse(Record.objects.filter(pk='kb_testentry').exists())
        call_command('import_shared_library',source=str(source),stdout=StringIO());self.assertTrue(Record.objects.filter(pk='kb_testentry').exists())
    def test_import_download_preserves_the_full_text_beyond_search_limit(self):
        source=self.legacy_library();connection=sqlite3.connect(source);connection.execute('UPDATE library_resources SET body_text=?',('文'*1000001+'完整正文结尾',));connection.commit();connection.close()
        call_command('import_shared_library',source=str(source),stdout=StringIO());row=Record.objects.get(pk='kb_testentry');self.assertEqual(len(row.payload['text']),1000000);self.assertEqual(row.payload['parseStatus'],'partial')
        self.assertIn('完整正文结尾',Path(Asset.objects.get(record=row).file.path).read_text('utf-8'))
    def test_import_repairs_missing_snapshots_and_refuses_corrupt_existing_bytes(self):
        source=self.legacy_library();call_command('import_shared_library',source=str(source),stdout=StringIO());row=Record.objects.get(pk='kb_testentry');asset=Asset.objects.get(record=row);path=Path(asset.file.path)
        self.assertTrue(path.is_relative_to(Path(self.temp.name)));original=path.read_bytes();path.unlink();call_command('import_shared_library',source=str(source),stdout=StringIO());self.assertEqual(path.read_bytes(),original)
        path.write_bytes(b'corrupt')
        with self.assertRaises(CommandError):call_command('import_shared_library',source=str(source),stdout=StringIO())
        self.assertEqual(path.read_bytes(),b'corrupt');self.assertTrue(Record.objects.filter(pk=row.id).exists())

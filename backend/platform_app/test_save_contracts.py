"""Frontend form contracts, retry identity and profile length regressions."""
import json
import uuid

from allauth.account.models import EmailAddress
from django.core.cache import cache
from django.test import TestCase, override_settings

from .models import Record, User, Membership
from .tests import Client, person, record
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], MAIL_TRANSPORT='local', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', AI_API_KEY='')
class SaveFormContractTests(TestCase):
    client_class = Client

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('save-contract@example.invalid', None, display_name='原名称', cohort='原单位')
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True, primary=True)
        self.client.force_login(self.user, backend='django.contrib.auth.backends.ModelBackend')

    def patch(self, changes):
        return self.client.patch('/api/workspace', json.dumps({'changes': changes}), content_type='application/json')

    def competition(self, members=''):
        return {'id': 'competition_' + uuid.uuid4().hex, 'title': '表单合同测试', 'hours': 2.5, 'members': members, 'rules': '原始规则', 'status': 'ready'}

    def test_competition_accepts_empty_member_notes_and_idempotent_retry(self):
        row = self.competition()
        self.assertEqual(self.patch({'competitions': [row]}).status_code, 200)
        self.assertEqual(self.patch({'competitions': [row]}).status_code, 200)
        self.assertEqual(Record.objects.filter(pk=row['id']).count(), 1)
        self.assertEqual(Record.objects.get(pk=row['id']).revision, 1)

    def test_member_notes_preserve_free_text_and_read_back(self):
        notes = '甲：负责建模、统计；乙：写作\n说明：这里不是平台成员邀请。'
        row = self.competition(notes)
        self.assertEqual(self.patch({'competitions': [row]}).status_code, 200)
        self.assertEqual(Record.objects.get(pk=row['id']).payload['members'], notes)
        rows = self.client.get('/api/workspace').json()['competitions']
        self.assertEqual(next(r for r in rows if r['id'] == row['id'])['members'], notes)

    def test_member_notes_reject_arrays_numbers_and_oversize_before_commit(self):
        for value in [[], ['成员'], 12, None, '文' * 200001]:
            with self.subTest(value_type=type(value).__name__):
                row = self.competition(value)
                response = self.patch({'competitions': [row]})
                self.assertEqual(response.status_code, 400)
                self.assertNotIn('ErrorDetail', response.content.decode())
                self.assertFalse(Record.objects.filter(pk=row['id']).exists())

    def test_real_team_members_still_require_list(self):
        row = {'id': 'team_' + uuid.uuid4().hex, 'name': '权限团队', 'members': '不能把备注当真实成员', 'fileIds': [], 'messages': []}
        self.assertEqual(self.patch({'teams': [row]}).status_code, 400)
        self.assertFalse(Record.objects.filter(pk=row['id']).exists())

    def test_draft_nonempty_title_is_still_required(self):
        for title in ['', '   ', '文' * 241]:
            row = {'id': 'draft_' + uuid.uuid4().hex, 'title': title}
            self.assertEqual(self.patch({'writingDrafts': [row]}).status_code, 400)
            self.assertFalse(Record.objects.filter(pk=row['id']).exists())

    def test_profile_accepts_exact_limit_without_truncating(self):
        row = {'displayName': '名' * 120, 'cohort': '校' * 120}
        response = self.client.patch('/api/profile', json.dumps(row), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.display_name, row['displayName'])
        self.assertEqual(self.user.cohort, row['cohort'])

    def test_profile_rejects_oversize_without_partial_update_or_silent_truncation(self):
        for row in [{'displayName': '新名称', 'cohort': '校' * 121}, {'displayName': '名' * 121, 'cohort': '新单位'}]:
            response = self.client.patch('/api/profile', json.dumps(row), content_type='application/json')
            self.assertEqual(response.status_code, 400)
            self.user.refresh_from_db()
            self.assertEqual(self.user.display_name, '原名称')
            self.assertEqual(self.user.cohort, '原单位')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], MAIL_TRANSPORT='local', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', AI_API_KEY='')
class ProblemImportContractTests(TestCase):
    client_class=Client

    def setUp(self):
        import tempfile
        self.media=tempfile.TemporaryDirectory();self.addCleanup(self.media.cleanup)
        setting=override_settings(MEDIA_ROOT=self.media.name);setting.enable();self.addCleanup(setting.disable)
        self.mentor=person('problem-mentor','mentor');self.student=person('problem-student');self.outsider=person('problem-outsider')
        self.team=record(self.mentor,'teams',name='题目导入团队',members=[],messages=[],fileIds=[])
        Membership.objects.create(team=self.team,user=self.student)
        self.client.force_login(self.mentor,backend='django.contrib.auth.backends.ModelBackend')

    def upload(self):
        key='problem_'+uuid.uuid4().hex;raw='合成题目：给定2、4、6，求均值并解释计算过程。'.encode()
        response=self.client.post('/api/files',{'metadata':json.dumps({'id':key,'kind':'attachment','scope':'个人资料'}),'file':SimpleUploadedFile('synthetic-problem.txt',raw,content_type='text/plain')})
        self.assertEqual(response.status_code,201)
        return key,raw

    def task(self,attachment):
        return {'id':'task_'+uuid.uuid4().hex,'title':'团队题目导入','mode':'自由练习','requirements':'读取附件中的原题。','criteria':'展示计算过程。','attachmentIds':[attachment],'teamId':self.team.id,'createdAt':timezone.now().isoformat()}

    def test_uploaded_problem_task_student_reads_exact_original_and_outsider_is_denied(self):
        key,raw=self.upload();task=self.task(key)
        response=self.client.patch('/api/workspace',json.dumps({'changes':{'tasks':[task]}}),content_type='application/json');self.assertEqual(response.status_code,200)
        student=Client();student.force_login(self.student,backend='django.contrib.auth.backends.ModelBackend')
        self.assertIn(task['id'],[r['id'] for r in student.get('/api/workspace').json()['tasks']])
        self.assertEqual(b''.join(student.get('/api/files/'+key).streaming_content),raw)
        outsider=Client();outsider.force_login(self.outsider,backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(outsider.get('/api/files/'+key).status_code,404)

    def test_competition_retains_uploaded_problem_and_existing_backups_without_attachments(self):
        key,_=self.upload();base={'id':'comp_'+uuid.uuid4().hex,'title':'导入赛题','members':'','rules':'读取原题','hours':1,'status':'ready'}
        self.assertEqual(self.client.patch('/api/workspace',json.dumps({'changes':{'competitions':[base]}}),content_type='application/json').status_code,200)
        base.update(_revision=1,attachmentIds=[key])
        self.assertEqual(self.client.patch('/api/workspace',json.dumps({'changes':{'competitions':[base]}}),content_type='application/json').status_code,200)
        self.assertEqual(Record.objects.get(pk=base['id']).payload['attachmentIds'],[key])

    def test_competition_cannot_import_unreadable_private_problem(self):
        private=record(self.outsider,'resources',name='他人题目',scope='个人资料')
        row={'id':'comp_'+uuid.uuid4().hex,'title':'无权导入','members':'','rules':'','hours':1,'status':'ready','attachmentIds':[private.id]}
        self.assertEqual(self.client.patch('/api/workspace',json.dumps({'changes':{'competitions':[row]}}),content_type='application/json').status_code,404)
        self.assertFalse(Record.objects.filter(pk=row['id']).exists())

    def test_competition_restore_requires_original_problem_attachment(self):
        key,_=self.upload();row={'id':'comp_'+uuid.uuid4().hex,'title':'保留题目附件','members':'','rules':'','hours':1,'status':'ready','attachmentIds':[key]}
        self.assertEqual(self.client.patch('/api/workspace',json.dumps({'changes':{'competitions':[row]}}),content_type='application/json').status_code,200)
        def action(collection,key,verb,revision):
            return self.client.post('/api/records/'+collection+'/'+key+'/'+verb,json.dumps({'revision':revision}),content_type='application/json')
        self.assertEqual(action('competitions',row['id'],'delete',1).status_code,200)
        self.assertEqual(action('resources',key,'delete',1).status_code,200)
        self.assertEqual(action('competitions',row['id'],'restore',2).status_code,409)
        self.assertEqual(action('resources',key,'restore',2).status_code,200)
        self.assertEqual(action('competitions',row['id'],'restore',2).status_code,200)

    def test_mentor_cannot_republish_student_private_submission_attachment(self):
        from unittest.mock import patch
        private=record(self.student,'resources',name='学生私有提交',scope='个人资料')
        # Even a reviewer who can read a submission must not publish its private original as a new school/team problem.
        from .domain import reference as original
        def readable(user,key,collection,**kwargs):
            return private if key==private.id and collection=='resources' else original(user,key,collection,**kwargs)
        with patch('platform_app.domain.reference',side_effect=readable):
            response=self.client.patch('/api/workspace',json.dumps({'changes':{'tasks':[self.task(private.id)]}}),content_type='application/json')
        self.assertEqual(response.status_code,403)

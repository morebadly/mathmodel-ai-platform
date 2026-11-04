"""Compiler API/permission regressions. Remote-command tests are contracts, not real TeX runs."""
import copy,json,tempfile,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from django.conf import settings
from django.test import TestCase,override_settings
from django.core.files.base import ContentFile
from rest_framework.exceptions import ValidationError
from .tests import Client,person,record,key
from .models import ExecutionJob,ExecutionArtifact
from .domain import save_workspace,workspace_json
from . import execution


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],E2B_API_KEY='',E2B_LATEX_TEMPLATE='',RUNNER_URL='',RUNNER_API_KEY='',SANDBOX_PROVIDER='e2b')
class WritingCompilerTests(TestCase):
    client_class=Client
    def setUp(self):
        self.owner=person('compiler');self.other=person('other-compiler')
        self.draft=record(self.owner,'writingDrafts',title='论文',format='latex',source='actual source',target='',notes='',compileInputIds=[])
        self.client.force_login(self.owner,backend='django.contrib.auth.backends.ModelBackend')
        self.temp=tempfile.TemporaryDirectory(dir=settings.DATA_DIR);self.addCleanup(self.temp.cleanup)
        media=override_settings(MEDIA_ROOT=self.temp.name);media.enable();self.addCleanup(media.disable)
    def post(self,path,data):return self.client.post(path,json.dumps(data),content_type='application/json')
    def body(self,**extra):return {'clientId':key(),'runtime':'latex','code':r'\documentclass{article}\begin{document}Actual\end{document}','writingId':self.draft.id,'field':'source','inputIds':[],'seconds':10,**extra}
    def test_formats_persist_and_legacy_is_not_rewritten(self):
        for fmt in ['latex','markdown','text']:
            value={'id':key(),'title':fmt,'format':fmt,'source':'# 原文 $x^2$','target':'English','notes':''}
            save_workspace(self.owner,{'writingDrafts':[value]},{});self.assertEqual(next(d for d in workspace_json(self.owner)['writingDrafts'] if d['id']==value['id'])['format'],fmt)
        legacy=record(self.owner,'writingDrafts',title='旧文稿',source='原文',target='',notes='')
        save_workspace(self.owner,{'writingDrafts':[copy.deepcopy(legacy.payload)]},{})
        legacy.refresh_from_db();self.assertNotIn('format',legacy.payload)
    def test_invalid_format_text_and_attachment_shapes_rejected(self):
        for change in [{'format':'executable'},{'source':{}},{'compileInputIds':[{}]},{'compileInputIds':'bad'}]:
            with self.subTest(change=change),self.assertRaises(ValidationError):save_workspace(self.owner,{'writingDrafts':[{'id':key(),'title':'坏数据',**change}]},{})
    def test_compilation_requires_owned_document_and_valid_field(self):
        foreign=record(self.other,'writingDrafts',title='私有')
        for change,expected in [({'writingId':foreign.id},404),({'writingId':{}},400),({'field':'notes'},400)]:
            with self.subTest(change=change):self.assertEqual(self.post('/api/execution/jobs',self.body(**change)).status_code,expected)
        self.assertEqual(ExecutionJob.objects.count(),0)
    def test_waiting_state_is_explicit_and_not_success(self):
        response=self.post('/api/execution/jobs',self.body());self.assertEqual(response.status_code,202)
        job=response.json()['job'];self.assertEqual(job['status'],'awaiting_credentials');self.assertFalse(job['artifacts']);self.assertEqual(job['limits']['writingId'],self.draft.id)
    @override_settings(E2B_API_KEY='contract-not-a-real-key',E2B_LATEX_TEMPLATE='contract-tex')
    def test_idempotency_includes_document_and_field(self):
        body=self.body();first=self.post('/api/execution/jobs',body);self.assertEqual(first.status_code,202)
        second=self.post('/api/execution/jobs',body);self.assertTrue(second.json()['duplicate']);self.assertEqual(second.json()['job']['id'],first.json()['job']['id'])
        self.assertEqual(self.post('/api/execution/jobs',{**body,'field':'target'}).status_code,400)
        self.assertEqual(ExecutionJob.objects.count(),1)
    @override_settings(SANDBOX_DAILY_JOBS=1,LATEX_DAILY_JOBS=1)
    def test_latex_daily_quota_does_not_consume_python_quota(self):
        self.assertEqual(self.post('/api/execution/jobs',self.body()).status_code,202)
        self.assertEqual(self.post('/api/execution/jobs',self.body()).status_code,429)
        self.assertEqual(self.post('/api/execution/jobs',self.body(runtime='python')).status_code,202)
        self.assertEqual(self.post('/api/execution/jobs',self.body(runtime='python')).status_code,429)
    def test_other_account_cannot_access_job_or_pdf(self):
        job=ExecutionJob.objects.create(owner=self.owner,client_id=uuid.uuid4(),runtime='latex',provider='e2b',code='private',limits={'writingId':self.draft.id,'field':'source'},status='completed')
        item=ExecutionArtifact.objects.create(job=job,name='main.pdf',size=10,mime='application/pdf',sha256='x',file=ContentFile(b'%PDF-test',name='main.pdf'))
        self.client.force_login(self.other,backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.client.get('/api/execution/jobs/'+str(job.id)).status_code,404)
        self.assertEqual(self.client.get('/api/execution/artifacts/'+str(item.id)).status_code,404)
    def test_document_deletion_redacts_history_and_restore_restores_access(self):
        job=ExecutionJob.objects.create(owner=self.owner,client_id=uuid.uuid4(),runtime='latex',provider='e2b',code='private',limits={'writingId':self.draft.id,'field':'source'},status='completed')
        self.assertEqual(self.post('/api/records/writingDrafts/'+self.draft.id+'/delete',{'revision':1}).status_code,200)
        row=self.client.get('/api/execution/jobs').json()['jobs'][0]
        self.assertEqual(row['status'],'access_revoked');self.assertNotIn('limits',row);self.assertNotIn('code',row)
        self.draft.refresh_from_db();self.assertEqual(self.post('/api/records/writingDrafts/'+self.draft.id+'/restore',{'revision':self.draft.revision}).status_code,200)
        self.assertEqual(self.client.get('/api/execution/jobs/'+str(job.id)).status_code,200)
    def test_filtered_history_is_owned_and_not_lost_behind_unrelated_jobs(self):
        wanted=ExecutionJob.objects.create(owner=self.owner,client_id=uuid.uuid4(),runtime='latex',provider='e2b',code='wanted',limits={'writingId':self.draft.id,'field':'source'},status='completed')
        ExecutionJob.objects.bulk_create([ExecutionJob(owner=self.owner,client_id=uuid.uuid4(),runtime='python',provider='e2b',code='unrelated',status='cancelled') for _ in range(101)])
        rows=self.client.get('/api/execution/jobs',{'writingId':self.draft.id,'field':'source'}).json()['jobs']
        self.assertEqual([row['id'] for row in rows],[str(wanted.id)])
        self.client.force_login(self.other,backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.client.get('/api/execution/jobs',{'writingId':self.draft.id}).status_code,404)
    def test_uncompiled_attachment_reference_blocks_trash_and_restores_with_draft(self):
        resource=record(self.owner,'resources',name='source.tex',scope='个人资料')
        self.draft.payload['compileInputIds']=[resource.id];self.draft.save()
        self.assertEqual(self.post('/api/records/resources/'+resource.id+'/delete',{'revision':1}).status_code,409)
        self.assertEqual(self.post('/api/records/writingDrafts/'+self.draft.id+'/delete',{'revision':1}).status_code,200)
        self.draft.refresh_from_db();self.assertEqual(self.post('/api/records/writingDrafts/'+self.draft.id+'/restore',{'revision':self.draft.revision}).status_code,200)
        self.assertEqual(self.post('/api/records/resources/'+resource.id+'/delete',{'revision':1}).status_code,409)
    @override_settings(E2B_API_KEY='contract-key',E2B_TEMPLATE='python-template',E2B_LATEX_TEMPLATE='tex-template')
    def test_latex_uses_separate_template_and_never_enables_shell_or_network(self):
        provider=execution.E2BProvider();job=SimpleNamespace(id='contract',runtime='latex',code='actual-source',limits={'seconds':5,'cpus':2,'memoryMb':4096})
        with patch('e2b_code_interpreter.Sandbox.create') as create:
            create.return_value.sandbox_id='sandbox';self.assertEqual(provider.create(job),'sandbox')
            self.assertEqual(create.call_args.kwargs['template'],'tex-template');self.assertIs(create.call_args.kwargs['allow_internet_access'],False)
        box=Mock();box.get_info.return_value=SimpleNamespace(cpu_count=2,memory_mb=2048)
        box.commands.run.return_value=SimpleNamespace(exit_code=0)
        box.files.list.return_value=[SimpleNamespace(path='/home/user/mathmodel-contract/output/main.pdf',type='file',size=9)]
        box.files.read.return_value.__enter__=Mock(return_value=iter([b'%PDF-test']));box.files.read.return_value.__exit__=Mock(return_value=False)
        with patch.object(provider,'connect',return_value=box):result=provider.run(job,'sandbox',[],lambda text:None)
        self.assertEqual(result['status'],'completed');call=box.commands.run.call_args;self.assertIn('-no-shell-escape',call.args[0]);self.assertEqual(call.kwargs['envs']['openin_any'],'p');self.assertEqual(call.kwargs['envs']['openout_any'],'p')
        uploaded=box.files.write_files.call_args.args[0]
        self.assertEqual(len(uploaded),3)
        self.assertTrue(any(item['path'].endswith('/main.tex') and 'actual-source' in item['data'] for item in uploaded))
        box.files.make_dir.assert_not_called()

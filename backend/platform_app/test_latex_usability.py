"""Regression contracts; real remote compilation is recorded separately."""
import copy,json,tempfile
from types import SimpleNamespace
from unittest.mock import patch
from django.conf import settings
from django.test import TestCase,SimpleTestCase,override_settings
from django.core.files.base import ContentFile
from .tests import Client,person,record,key
from .models import ExecutionJob,ExecutionArtifact,Asset
from .domain import save_workspace
from .latex_support import prepare,diagnostics

class LatexInputTests(SimpleTestCase):
    def test_replaceable_gateway_receives_prepared_source_but_original_is_preserved(self):
        from .execution import GatewayProvider
        provider=GatewayProvider();job=SimpleNamespace(runtime='latex',code=r'\frac{a}{b}',limits={'seconds':2})
        with patch.object(provider,'request',side_effect=[{}, {'status':'completed','logs':'','logOffset':0,'artifacts':[]}]) as request:
            self.assertEqual(provider.run(job,'contract',[],lambda text:None)['status'],'completed')
        self.assertIn(r'\begin{document}',request.call_args_list[0].kwargs['json']['code'])
        self.assertEqual(job.code,r'\frac{a}{b}')
    def test_reported_quadratic_formula_gets_math_environment_without_rewriting_original(self):
        original='\\documentclass{article}\n\\begin{document}\n'+r'\frac{-b\pm\sqrt{b^2-4ac}}{2a}'+'\n\\end{document}'
        prepared,offset,notes=prepare(original)
        self.assertIn(r'\[ \frac{-b\pm\sqrt{b^2-4ac}}{2a} \]',prepared)
        self.assertEqual(offset,0);self.assertTrue(any('第3行' in note for note in notes))
        self.assertNotIn(r'\[',original)
    def test_body_fence_and_common_macros(self):
        compiled,offset,notes=prepare('```latex\n'+r'\section{模型} $\mathbb{R}$'+'\n```')
        self.assertIn('ctexart',compiled);self.assertIn('amssymb',compiled);self.assertNotIn('```',compiled)
        self.assertEqual(offset,0)
        full=r'\documentclass{article}\begin{document}$\mathbb{R}$\end{document}'
        self.assertIn(r'\usepackage{amssymb}',prepare(full)[0])
    def test_existing_math_verbatim_and_prose_are_not_wrapped_twice(self):
        for source in [r'\[ \frac{a}{b} \]', '$$\n'+r'\frac{a}{b}'+'\n$$',r'\begin{equation}'+'\n'+r'\frac{a}{b}'+'\n'+r'\end{equation}',r'\begin{verbatim}'+'\n'+r'\frac{a}{b}'+'\n'+r'\end{verbatim}',r'说明中使用 \frac{a}{b} 但应由作者选择数学环境']:
            result=prepare(source)[0];self.assertIn(source,result)
    def test_errors_map_back_to_original_body_line(self):
        result=diagnostics('./main.tex:3: Undefined control sequence.\nl.3 \\badcommand','第一行\n'+r'\badcommand')
        self.assertEqual(result[0]['line'],2);self.assertIn('命令未定义',result[0]['hint'])
    def test_alignat_and_comment_documentclass_remain_valid_inputs(self):
        original=r'\begin{alignat}{2}'+'\nx &= y +\n'+r'\frac{a}{b}'+'\n'+r'\end{alignat}'
        self.assertIn(original,prepare(original)[0])
        self.assertIn('ctexart',prepare('% '+r'\documentclass{article}'+'\n正文')[0])
    def test_multiline_documentclass_and_commented_packages(self):
        code='\\documentclass [\n12pt,a4paper\n]{article}\n% \\usepackage{amssymb}\n% \\begin{document}\n\\begin{document}$\\mathbb{R}$\\end{document}'
        result=prepare(code)[0]
        self.assertEqual(result.count(r'\documentclass'),1)
        self.assertIn('% '+r'\begin{document}'+'\n'+r'\usepackage{amssymb}\begin{document}',result)
    def test_alignat_and_other_common_amsmath_environments_load_package(self):
        for environment in ['alignat','flalign','align*','gathered','alignedat','smallmatrix']:
            code=r'\documentclass{article}\begin{document}\begin{'+environment+r'}x=y\end{'+environment+r'}\end{document}'
            self.assertIn(r'\usepackage{amsmath}',prepare(code)[0])

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],E2B_API_KEY='contract-only',E2B_LATEX_TEMPLATE='contract-tex',SANDBOX_PROVIDER='e2b',REDIS_URL='')
class LatexWorkflowTests(TestCase):
    client_class=Client
    def setUp(self):
        self.owner=person('new-compiler');self.other=person('unrelated-compiler')
        self.draft=record(self.owner,'writingDrafts',title='论文',format='latex',source='正文',target='',notes='')
        self.project=record(self.owner,'projects',title='项目',stages=[{'title':str(i),'content':'旧阶段'+str(i),'done':False} for i in range(8)],resourceIds=[])
        self.client.force_login(self.owner,backend='django.contrib.auth.backends.ModelBackend')
        self.temp=tempfile.TemporaryDirectory(dir=settings.DATA_DIR);self.addCleanup(self.temp.cleanup)
        media=override_settings(MEDIA_ROOT=self.temp.name);media.enable();self.addCleanup(media.disable)
    def post(self,path,data):return self.client.post(path,json.dumps(data),content_type='application/json')
    def body(self,**extra):return {'clientId':key(),'runtime':'latex','code':r'\frac{a}{b}','writingId':self.draft.id,'field':'source','inputIds':[],'seconds':10,**extra}
    def complete(self,body=None):
        response=self.post('/api/execution/jobs',body or self.body());self.assertEqual(response.status_code,202)
        job=ExecutionJob.objects.get(pk=response.json()['job']['id']);job.status='completed';job.remote_id='contract-remote-proof';job.save()
        from .execution import store_artifacts
        store_artifacts(job,[('main.pdf',b'%PDF-contract-content')]);return job
    def test_project_paper_field_and_history_have_owner_and_collection_checks(self):
        body=self.body(writingId=self.project.id,documentCollection='projects',field='stage5')
        job=self.complete(body)
        rows=self.client.get('/api/execution/jobs',{'writingId':self.project.id,'documentCollection':'projects','field':'stage5'}).json()['jobs']
        self.assertEqual([row['id'] for row in rows],[str(job.id)])
        self.assertEqual(self.post('/api/execution/jobs',{**body,'clientId':key(),'field':'source'}).status_code,400)
        self.client.force_login(self.other,backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.post('/api/execution/jobs',self.body(writingId=self.project.id,documentCollection='projects',field='stage5')).status_code,404)
        self.assertEqual(self.client.get('/api/execution/jobs',{'writingId':self.project.id,'documentCollection':'projects','field':'stage5'}).status_code,404)
    def test_project_format_and_inputs_persist_without_changing_other_stages(self):
        data=copy.deepcopy(self.project.payload);data['_revision']=self.project.revision;data['stages'][5].update(format='latex',content=r'\frac{a}{b}');data['compileInputIds']=[]
        save_workspace(self.owner,{'projects':[data]},{});self.project.refresh_from_db()
        self.assertEqual(self.project.payload['stages'][5]['format'],'latex');self.assertEqual(self.project.payload['stages'][2]['content'],'旧阶段2')
    def test_cache_is_explicit_and_uses_an_independent_private_artifact(self):
        original=self.complete();cached=self.post('/api/execution/jobs',self.body()).json()['job'];self.assertTrue(cached['cacheHit']);self.assertEqual(cached['status'],'completed')
        item=ExecutionArtifact.objects.get(job_id=cached['id']);first=original.artifacts.get();self.assertNotEqual(item.file.name,first.file.name)
        first.file.delete();self.assertTrue(item.file.storage.exists(item.file.name))
        self.assertEqual(self.post('/api/execution/jobs',self.body(clientId=str(ExecutionJob.objects.get(pk=cached['id']).client_id))).json()['job']['id'],cached['id'])
        self.assertFalse(self.post('/api/execution/jobs',self.body(code=r'\frac{a}{c}')).json()['job']['cacheHit'])
        other_draft=record(self.owner,'writingDrafts',title='另一个文稿')
        self.assertFalse(self.post('/api/execution/jobs',self.body(writingId=other_draft.id)).json()['job']['cacheHit'])
    def test_cache_does_not_bypass_current_attachment_permissions(self):
        resource=record(self.owner,'resources',name='test.tex',scope='个人资料');Asset.objects.create(record=resource,file=ContentFile(b'original',name='test.tex'),original_name='test.tex',size=8,sha256='a')
        self.complete(self.body(inputIds=[resource.id]));resource.scope='deleted';resource.save()
        self.assertEqual(self.post('/api/execution/jobs',self.body(inputIds=[resource.id])).status_code,404)
    @override_settings(SANDBOX_DAILY_JOBS=1,LATEX_DAILY_JOBS=1)
    def test_legacy_missing_cache_flag_counts_and_cache_does_not_spend_quota(self):
        ExecutionJob.objects.create(owner=self.owner,client_id=key(),runtime='python',provider='e2b',code='legacy',status='completed',limits={})
        self.assertEqual(self.post('/api/execution/jobs',self.body(runtime='python')).status_code,429)
        self.complete();self.assertTrue(self.post('/api/execution/jobs',self.body()).json()['job']['cacheHit'])
        self.assertEqual(self.post('/api/execution/jobs',self.body(code='a different compile')).status_code,429)
    def test_cache_invalidates_when_input_hash_or_template_changes(self):
        resource=record(self.owner,'resources',name='test.tex',scope='个人资料');asset=Asset.objects.create(record=resource,file=ContentFile(b'original',name='test.tex'),original_name='test.tex',size=8,sha256='a')
        self.complete(self.body(inputIds=[resource.id]));asset.sha256='b';asset.save()
        self.assertFalse(self.post('/api/execution/jobs',self.body(inputIds=[resource.id])).json()['job']['cacheHit'])
        self.complete()
        with override_settings(E2B_LATEX_TEMPLATE='new-contract-template'):
            self.assertFalse(self.post('/api/execution/jobs',self.body()).json()['job']['cacheHit'])
    def test_prepared_source_and_original_source_are_both_available(self):
        original=self.complete();response=self.client.get('/api/execution/jobs/'+str(original.id),{'prepared':'1'}).json()['job']
        self.assertEqual(response['code'],r'\frac{a}{b}');self.assertIn(r'\begin{document}',response['preparedCode']);self.assertIn(r'\[',response['preparedCode'])
    def test_project_deletion_revokes_existing_compile_history(self):
        job=self.complete(self.body(writingId=self.project.id,documentCollection='projects',field='stage5'))
        self.assertEqual(self.post('/api/records/projects/'+self.project.id+'/delete',{'revision':1}).status_code,200)
        self.assertEqual(self.client.get('/api/execution/jobs/'+str(job.id)).status_code,403)
        self.assertEqual(self.client.get('/api/execution/artifacts/'+str(job.artifacts.get().id)).status_code,403)
    @override_settings(REDIS_URL='redis://contract')
    def test_immediate_dispatch_happens_only_after_commit_and_falls_back_on_broker_failure(self):
        with patch('platform_app.tasks.execution_tick.apply_async') as dispatch,self.captureOnCommitCallbacks(execute=True):
            self.post('/api/execution/jobs',self.body());self.assertFalse(dispatch.called)
        self.assertEqual(dispatch.call_count,1)
        with patch('platform_app.tasks.execution_tick.apply_async',side_effect=RuntimeError('contract broker outage')),self.captureOnCommitCallbacks(execute=True):
            response=self.post('/api/execution/jobs',self.body(code='different source'))
        self.assertEqual(response.json()['job']['status'],'queued')

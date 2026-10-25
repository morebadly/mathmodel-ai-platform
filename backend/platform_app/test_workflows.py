"""Isolated authorization/state-machine regressions; remote provider doubles are CONTRACT tests only."""
import json,tempfile,uuid,hashlib
from pathlib import Path
from unittest.mock import patch,Mock
from django.test import TestCase,TransactionTestCase,override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core import signing
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from .tests import Client,person,record,key
from .models import Asset,Membership,Invitation,ChatMessage,ExecutionJob,ExecutionArtifact,SearchChunk,Record,IndexTask
from . import execution,retrieval

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],E2B_API_KEY='',RUNNER_URL='',RUNNER_API_KEY='',AI_API_KEY='',SANDBOX_PROVIDER='e2b',RUNTIME_AUTHORIZATION={})
class WorkflowTests(TransactionTestCase):
    client_class=Client
    def setUp(self):
        cache.clear();self.temp=tempfile.TemporaryDirectory(dir=settings.DATA_DIR);self.addCleanup(self.temp.cleanup)
        scope=override_settings(MEDIA_ROOT=self.temp.name);scope.enable();self.addCleanup(scope.disable)
        self.s=person('student');self.peer=person('peer');self.o=person('outsider');self.m=person('mentor','mentor');self.a=person('admin','admin')
        self.team=record(self.m,'teams',name='QA team',members=[],messages=[],fileIds=[])
        for u in [self.s,self.peer]:Membership.objects.create(team=self.team,user=u)
        self.login(self.s)
    def login(self,u):self.client.force_login(u,backend='django.contrib.auth.backends.ModelBackend')
    def post(self,url,body):return self.client.post(url,json.dumps(body),content_type='application/json')
    def room(self):
        r=self.post('/api/chat/rooms',{'teamId':self.team.id});self.assertEqual(r.status_code,201);return r.json()['room']['id']
    def send(self,room,**extra):return self.post('/api/chat/rooms/'+room+'/messages',{'clientId':key(),'body':'actual persisted text','attachmentIds':[],**extra})
    def upload(self,owner=None,scope='个人资料',kind='knowledge',name='actual.txt',data=b'actual parser source'):
        if owner:self.login(owner)
        r=self.client.post('/api/files',{'metadata':json.dumps({'id':key(),'kind':kind,'scope':scope}),'file':SimpleUploadedFile(name,data)})
        self.assertEqual(r.status_code,201);return r.json()['id']
    def runjob(self,**extra):return self.post('/api/execution/jobs',{'clientId':key(),'runtime':'python','code':'print(7)','seconds':5,'inputIds':[],**extra})
    def test_chat_relationship_and_admin_does_not_imply_membership(self):
        room=self.room();self.login(self.o);self.assertEqual(self.send(room).status_code,404)
        self.assertEqual(self.post('/api/chat/rooms',{'peerId':str(self.s.id)}).status_code,403)
        self.login(self.a);self.assertEqual(self.client.get('/api/chat/rooms/'+room+'/messages').status_code,404)
        self.login(self.peer);self.assertEqual(self.post('/api/chat/rooms',{'peerId':str(self.s.id)}).status_code,201)
    def test_messages_persist_and_nonce_deduplicates(self):
        room=self.room();nonce=key();first=self.send(room,clientId=nonce);second=self.send(room,clientId=nonce)
        self.assertEqual(first.status_code,201);self.assertEqual(first.json()['message']['id'],second.json()['message']['id']);self.assertTrue(second.json()['duplicate'])
        self.assertEqual(self.send(room,clientId=nonce,body='changed').status_code,400);self.assertEqual(ChatMessage.objects.count(),1)
        self.assertEqual(self.client.get('/api/chat/rooms/'+room+'/messages').json()['messages'][0]['body'],'actual persisted text')
    def test_unread_cursor_monotonic(self):
        room=self.room();message=self.send(room).json()['message'];self.login(self.peer)
        self.assertEqual(self.client.get('/api/chat/rooms').json()['rooms'][0]['unread'],1)
        self.post('/api/chat/rooms/'+room+'/read',{'cursor':message['id']});self.post('/api/chat/rooms/'+room+'/read',{'cursor':0})
        self.assertEqual(self.client.get('/api/chat/rooms').json()['rooms'][0]['unread'],0)
        self.assertEqual(self.post('/api/chat/rooms/'+room+'/read',{'cursor':message['id']+99}).status_code,400)
    def test_chat_attachment_upload_dedup_and_revocation(self):
        room=self.room();nonce=key();url='/api/chat/rooms/'+room+'/files'
        upload=lambda:self.client.post(url,{'clientId':nonce,'file':SimpleUploadedFile('message.txt',b'file message')})
        first=upload();self.assertEqual(first.status_code,201);rid=first.json()['file']['id'];self.assertTrue(upload().json()['duplicate'])
        self.assertEqual(self.send(room,attachmentIds=[rid]).status_code,201)
        self.login(self.peer);response=self.client.get('/api/files/'+rid);self.assertEqual(response.status_code,200);b''.join(response.streaming_content)
        self.login(self.a);self.assertEqual(self.client.get('/api/files/'+rid).status_code,404)
        self.login(self.m);self.assertEqual(self.post(f'/api/teams/{self.team.id}/members/{self.s.id}/remove',{}).status_code,200)
        self.login(self.s);self.assertEqual(self.client.get('/api/files/'+rid).status_code,404);self.assertEqual(self.send(room).status_code,404)
    def test_cross_room_attachment_rejected(self):
        room=self.room();rid=self.client.post('/api/chat/rooms/'+room+'/files',{'clientId':key(),'file':SimpleUploadedFile('f.txt',b'x')}).json()['file']['id']
        direct=self.post('/api/chat/rooms',{'peerId':str(self.peer.id)}).json()['room']['id']
        self.assertEqual(self.send(direct,attachmentIds=[rid]).status_code,403)
    def test_removed_member_cannot_reuse_old_signed_invite(self):
        inv=Invitation.objects.create(team=self.team,email=self.s.email,issued_at=timezone.now());token=signing.dumps({'invitation':str(inv.id),'version':inv.version},salt='team-invite')
        self.login(self.m);self.post(f'/api/teams/{self.team.id}/members/{self.s.id}/remove',{})
        self.login(self.s);self.assertEqual(self.post('/api/invitations/accept',{'token':token}).status_code,400);self.assertFalse(Membership.objects.filter(team=self.team,user=self.s).exists())
    def csv(self,email=None,score=80):return 'email,assessment,assessmentDate,score,maxScore,source\n'+(email or self.s.email)+f',QA test,2026-10-24,{score},100,explicit QA fixture'
    def test_grades_preflight_commit_idempotency_and_conflict(self):
        self.login(self.m);url='/api/grades/import';body={'csv':self.csv(),'preview':True}
        self.assertEqual(self.post(url,body).status_code,200);self.assertFalse(Record.objects.filter(collection='scoreRecords').exists())
        body['preview']=False;self.assertEqual(self.post(url,body).json()['created'],1);self.assertEqual(self.post(url,body).json()['duplicates'],1)
        self.assertEqual(self.post(url,{'csv':self.csv(score=90),'preview':False}).status_code,409)
        self.assertEqual(Record.objects.get(collection='scoreRecords').payload['score'],80)
    def test_grades_authorization_and_atomic_bad_row(self):
        self.assertEqual(self.post('/api/grades/import',{'csv':self.csv(),'preview':False}).status_code,403)
        self.login(self.m);raw=self.csv()+'\n'+self.o.email+',bad,2026-10-24,90,100,fixture'
        self.assertEqual(self.post('/api/grades/import',{'csv':raw,'preview':False}).status_code,403);self.assertFalse(Record.objects.filter(collection='scoreRecords').exists())
        Membership.objects.filter(user=self.s).delete();self.assertEqual(self.post('/api/grades/import',{'csv':self.csv(),'preview':False}).status_code,403)
    def test_keyword_citations_and_private_filter(self):
        private=record(self.o,'resources',kind='knowledge',name='private',text='unique_keyword classified')
        public=record(self.a,'resources',kind='knowledge',name='public',text='prefix unique_keyword source');public.scope='public';public.save()
        data=self.client.get('/api/retrieval/search?q=unique_keyword').json();self.assertFalse(data['vectorReady']);self.assertEqual([h['resourceId'] for h in data['hits']],[public.id])
        h=data['hits'][0];self.assertEqual(h['quote'],public.payload['text'][h['start']:h['end']]);self.assertEqual(h['revision'],public.revision)
        self.assertEqual(self.client.get('/api/retrieval/search?q=unique_keyword&backend=vector').status_code,400)
    def test_index_upsert_edit_invalidation_and_delete(self):
        rid=self.upload();row=Record.objects.get(pk=rid);row.payload['text']='indexed source '*150;row.save()
        url='/api/retrieval/index-tasks';body={'resourceIds':[rid],'action':'upsert'};self.assertEqual(self.post(url,body).status_code,202);retrieval.process_indexes()
        chunks=list(SearchChunk.objects.filter(resource=row));self.assertGreater(len(chunks),1);self.assertEqual(chunks[0].text,row.payload['text'][:900])
        self.post(url,{'resourceIds':[rid],'action':'delete'});retrieval.process_indexes();self.assertFalse(SearchChunk.objects.filter(resource=row).exists());self.assertTrue(Asset.objects.filter(pk=rid).exists())
        self.post(url,body);retrieval.process_indexes();row.payload['text']='new revision';row.payload['_revision']=row.revision
        result=self.client.patch('/api/workspace',json.dumps({'changes':{'resources':[row.payload]}}),content_type='application/json');self.assertEqual(result.status_code,200);self.assertFalse(SearchChunk.objects.filter(resource=row).exists())
    def test_vector_tasks_wait_server_and_index_revocation(self):
        rid=self.upload();r=self.post('/api/retrieval/index-tasks',{'resourceIds':[rid],'provider':'vector'});self.assertEqual(r.json()['status'],'awaiting_server')
        self.post('/api/retrieval/index-tasks/'+r.json()['id']+'/cancel',{});self.assertEqual(IndexTask.objects.get(pk=r.json()['id']).status,'cancelled')
        self.login(self.o);self.assertEqual(self.post('/api/retrieval/index-tasks',{'resourceIds':[rid]}).status_code,404)
    def test_execution_without_credentials_never_dispatches_or_creates_results(self):
        r=self.runjob();self.assertEqual(r.status_code,202);job=ExecutionJob.objects.get(pk=r.json()['job']['id']);self.assertEqual(job.status,'awaiting_credentials')
        with patch.object(execution,'provider') as provider:execution.dispatch();provider.assert_not_called()
        self.assertFalse(ExecutionArtifact.objects.exists());self.assertFalse(self.client.get('/api/execution/runtimes').json()['hostExecution'])
    def test_commercial_runtime_gated_even_with_gateway_config(self):
        with override_settings(RUNNER_URL='https://runner.example.invalid',RUNNER_API_KEY='contract-only-key'):
            for runtime in ['matlab','gurobi','cplex']:self.assertEqual(self.runjob(runtime=runtime).json()['job']['status'],'awaiting_authorization')
    def test_execution_nonce_and_owner_isolation(self):
        nonce=key();first=self.runjob(clientId=nonce);jid=first.json()['job']['id'];self.assertTrue(self.runjob(clientId=nonce).json()['duplicate'])
        self.assertEqual(self.runjob(clientId=nonce,code='changed').status_code,400)
        self.login(self.o);self.assertEqual(self.client.get('/api/execution/jobs/'+jid).status_code,404);self.assertEqual(self.post('/api/execution/jobs/'+jid,{'action':'cancel'}).status_code,404)
    def test_execution_private_inputs_and_revocation(self):
        rid=self.upload(self.o);self.login(self.s);self.assertEqual(self.runjob(inputIds=[rid]).status_code,404)
        rid=self.upload(self.m,scope='校内资料');self.login(self.s);jid=self.runjob(inputIds=[rid]).json()['job']['id']
        row=Record.objects.get(pk=rid);row.scope='private';row.save();self.assertEqual(self.client.get('/api/execution/jobs/'+jid).status_code,403)
    def test_retry_cannot_reset_active_remote_or_uncertain_task(self):
        jid=self.runjob().json()['job']['id'];job=ExecutionJob.objects.get(pk=jid)
        for state in ['queued','starting','running','uncertain']:
            job.status=state;job.remote_id='durable-remote';job.attempts=1;job.save();self.assertEqual(self.post('/api/execution/jobs/'+jid,{'action':'retry'}).status_code,400)
            job.refresh_from_db();self.assertEqual(job.remote_id,'durable-remote');self.assertEqual(job.status,state)
        job.status='failed';job.cleanup_pending=True;job.save();self.assertEqual(self.post('/api/execution/jobs/'+jid,{'action':'retry'}).status_code,400)
    def test_cancel_pending_and_repeated_retry_once_queued(self):
        jid=self.runjob().json()['job']['id'];self.assertEqual(self.post('/api/execution/jobs/'+jid,{'action':'cancel'}).json()['job']['status'],'cancelled')
        jid=self.runjob().json()['job']['id']
        with override_settings(E2B_API_KEY='contract-only-key'):
            self.assertEqual(self.post('/api/execution/jobs/'+jid,{'action':'retry'}).json()['job']['status'],'queued')
            self.assertEqual(self.post('/api/execution/jobs/'+jid,{'action':'retry'}).status_code,400)
    def test_cancel_running_calls_remote_contract_with_durable_identifier(self):
        jid=self.runjob().json()['job']['id'];ExecutionJob.objects.filter(pk=jid).update(status='running',remote_id='contract-only-session',claimed_at=timezone.now(),cleanup_pending=True)
        remote=Mock()
        with patch.object(execution,'provider',return_value=remote):r=self.post('/api/execution/jobs/'+jid,{'action':'cancel'})
        self.assertEqual(r.status_code,200);self.assertEqual(r.json()['job']['status'],'cancelled');self.assertFalse(r.json()['job']['cleanupPending']);remote.cancel.assert_called_once_with('contract-only-session')
    def test_dispatch_global_and_per_owner_limits_contract_only(self):
        """State scheduling only, never a real E2B execution/resource benchmark."""
        with override_settings(E2B_API_KEY='contract-only',SANDBOX_CONCURRENCY=2):
            first=self.runjob().json()['job']['id'];second=self.runjob().json()['job']['id'];self.login(self.peer);third=self.runjob().json()['job']['id']
            with patch.object(execution,'process_job') as run:execution.dispatch(limit=4)
            self.assertEqual(run.call_count,2);self.assertEqual(set(str(c.args[0]) for c in run.call_args_list),{first,third});self.assertEqual(ExecutionJob.objects.get(pk=second).status,'queued')
    def test_execution_daily_and_input_limits_checked_before_remote(self):
        with override_settings(SANDBOX_DAILY_JOBS=1):
            nonce=key();self.assertEqual(self.runjob(clientId=nonce).status_code,202);self.assertTrue(self.runjob(clientId=nonce).json()['duplicate']);self.assertEqual(self.runjob().status_code,429)
        rid=self.upload()
        with override_settings(SANDBOX_INPUT_BYTES=1):self.assertEqual(self.runjob(inputIds=[rid]).status_code,400)
    def test_remote_contract_state_and_artifact_only_not_real_execution(self):
        """Provider double: verifies orchestration only; DOES NOT accept E2B execution."""
        jid=self.runjob().json()['job']['id'];ExecutionJob.objects.filter(pk=jid).update(status='starting',attempts=1,claimed_at=timezone.now())
        remote=Mock();remote.create.return_value='contract-session';remote.run.side_effect=lambda job,rid,inputs,log:(log('contract fixture log') or {'status':'completed','artifacts':[('fixture.csv',b'x,y\n1,2')],'error':''})
        with patch.object(execution,'provider',return_value=remote):execution.process_job(jid)
        job=ExecutionJob.objects.get(pk=jid);self.assertEqual(job.status,'completed');self.assertEqual(job.artifacts.count(),1);self.assertFalse(job.cleanup_pending);remote.cancel.assert_called()
        response=self.client.get('/api/execution/artifacts/'+str(job.artifacts.first().id));self.assertEqual(response.status_code,200);b''.join(response.streaming_content)
    def test_artifacts_validate_entire_batch_before_writing(self):
        jid=self.runjob().json()['job']['id'];job=ExecutionJob.objects.get(pk=jid)
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):execution.store_artifacts(job,[('safe.csv',b'one'),('../escape',b'two')])
        self.assertFalse(job.artifacts.exists());self.assertFalse(list(Path(self.temp.name).rglob('*')))
        with override_settings(SANDBOX_OUTPUT_BYTES=2):
            with self.assertRaises(execution.OutputLimit):execution.store_artifacts(job,[('big',b'big')])
    def test_parse_retry_merges_current_metadata_and_cancel_protects_completion(self):
        rid=self.upload();asset=Asset.objects.get(pk=rid);asset.parse_status='failed';asset.save();row=Record.objects.get(pk=rid);row.payload.update(description='latest author edit',text='latest result');row.revision=8;row.save()
        self.assertEqual(self.post('/api/files/'+rid+'/parse',{'action':'retry','mode':'ocr','language':'en'}).status_code,200)
        row.refresh_from_db();asset.refresh_from_db();self.assertEqual(row.payload['description'],'latest author edit');self.assertEqual(row.revision,9);self.assertEqual(row.payload['parseMode'],'ocr');self.assertEqual(asset.parse_status,'pending')
        self.assertEqual(self.post('/api/files/'+rid+'/parse',{'action':'retry'}).status_code,400)
        self.post('/api/files/'+rid+'/parse',{'action':'cancel'});asset.refresh_from_db();self.assertEqual(asset.parse_status,'cancelled')
        self.login(self.o);self.assertEqual(self.post('/api/files/'+rid+'/parse',{'action':'retry'}).status_code,404)
    def test_local_jobs_entry_drives_real_text_parse(self):
        rid=self.upload(data=b'local worker actual source');call_command('run_jobs',once=True,verbosity=0)
        asset=Asset.objects.get(pk=rid);self.assertEqual(asset.parse_status,'ready');self.assertEqual(Record.objects.get(pk=rid).payload['text'],'local worker actual source')
    def test_old_execution_result_cannot_overwrite_or_cancel_new_attempt(self):
        jid=self.runjob().json()['job']['id'];claim=timezone.now();ExecutionJob.objects.filter(pk=jid).update(status='starting',claimed_at=claim)
        new_claim=claim+__import__('datetime').timedelta(seconds=1);remote=Mock();remote.create.return_value='old-remote'
        def delayed_result(*args):
            ExecutionJob.objects.filter(pk=jid).update(status='running',claimed_at=new_claim,remote_id='new-remote',logs='new attempt',cleanup_pending=True)
            return {'status':'completed','artifacts':[('old.csv',b'old')],'error':''}
        remote.run.side_effect=delayed_result
        with patch.object(execution,'provider',return_value=remote):execution.process_job(jid)
        job=ExecutionJob.objects.get(pk=jid);self.assertEqual(job.remote_id,'new-remote');self.assertEqual(job.status,'running');self.assertEqual(job.logs,'new attempt');self.assertTrue(job.cleanup_pending);self.assertFalse(job.artifacts.exists())
        self.assertTrue(all(c.args[0]=='old-remote' for c in remote.cancel.call_args_list))
    def test_old_reaper_cannot_clear_new_remote_cleanup_flag(self):
        jid=self.runjob().json()['job']['id'];claim=timezone.now()-__import__('datetime').timedelta(minutes=20)
        ExecutionJob.objects.filter(pk=jid).update(status='running',claimed_at=claim,remote_id='old-remote',cleanup_pending=True)
        remote=Mock()
        def cancel(identifier):ExecutionJob.objects.filter(pk=jid).update(status='running',claimed_at=timezone.now(),remote_id='new-remote',cleanup_pending=True)
        remote.cancel.side_effect=cancel
        with patch.object(execution,'provider',return_value=remote):execution.reap()
        job=ExecutionJob.objects.get(pk=jid);self.assertEqual(job.remote_id,'new-remote');self.assertEqual(job.status,'running');self.assertTrue(job.cleanup_pending)
    def test_media_helper_tree_terminated_when_polling_raises(self):
        from . import media
        rid=self.upload();asset=Asset.objects.get(pk=rid);asset.claimed_at=timezone.now();asset.parse_status='processing'
        child=Mock();child.poll.return_value=None
        with patch('platform_app.media.spawn_helper') as popen,patch('platform_app.media.Asset.objects.filter',side_effect=RuntimeError('database unavailable')),patch('platform_app.media.terminate_tree') as kill,patch('platform_app.media.close_job'):
            popen.return_value.__enter__.return_value=child
            with self.assertRaises(RuntimeError):media.process(asset,'transcribe','zh')
            kill.assert_called_once_with(child);child.wait.assert_called()

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class BackupTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=settings.DATA_DIR);self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
        setting=override_settings(DATA_DIR=self.root/'source-data',MEDIA_ROOT=self.root/'source-data/files');setting.enable();self.addCleanup(setting.disable);settings.DATA_DIR.mkdir()
        self.user=person('migration-user');self.row=record(self.user,'resources',name='中文.txt',kind='knowledge',text='正文',personId=str(self.user.pk))
        Asset.objects.create(record=self.row,file=SimpleUploadedFile('中文.txt',b'fixed source'),original_name='中文.txt',size=12,sha256=hashlib.sha256(b'fixed source').hexdigest(),parse_status='ready')
        self.bundle=self.root/'bundle'
    def backup(self):call_command('backup_platform',destination=str(self.bundle),writers_stopped=True,verbosity=0)
    def target(self):
        self.user.delete()
        return override_settings(DATA_DIR=self.root/'target-data',MEDIA_ROOT=self.root/'target-data/files')
    def test_backup_restore_preserves_uuid_json_references_and_hashes(self):
        uid=str(self.user.pk);rid=self.row.pk;joined=self.user.date_joined;created=self.row.created_at;self.backup()
        with self.target():
            call_command('restore_platform',source=str(self.bundle),empty_database=True,verbosity=0)
            row=Record.objects.get(pk=rid);self.assertEqual(str(row.owner_id),uid);self.assertEqual(row.payload['personId'],uid);self.assertEqual(row.payload['text'],'正文')
            self.assertEqual(row.created_at,created);self.assertEqual(row.owner.date_joined,joined)
            with Asset.objects.get(record=row).file.open('rb') as source:self.assertEqual(source.read(),b'fixed source')
    def test_missing_or_corrupt_original_rejects_backup(self):
        from django.core.management.base import CommandError
        asset=Asset.objects.get(record=self.row);Path(asset.file.path).write_bytes(b'corrupt')
        with self.assertRaises(CommandError):self.backup()
        self.assertFalse(self.bundle.exists());Path(asset.file.path).unlink()
        with self.assertRaises(CommandError):self.backup()
    def test_restore_load_failure_rolls_back_and_allows_retry(self):
        from django.core.management.base import CommandError
        self.backup()
        from .models import User
        with self.target():
            with patch('platform_app.management.commands.restore_platform.call_command',side_effect=CommandError('fixture failure')):
                with self.assertRaises(CommandError):call_command('restore_platform',source=str(self.bundle),empty_database=True,verbosity=0)
            self.assertFalse(User.objects.exists());self.assertFalse(Path(settings.MEDIA_ROOT).exists())
            call_command('restore_platform',source=str(self.bundle),empty_database=True,verbosity=0);self.assertTrue(User.objects.exists())
    def test_restore_wrong_count_rolls_back_and_allows_retry(self):
        from django.core.management.base import CommandError
        self.backup();path=self.bundle/'manifest.json';manifest=json.loads(path.read_text('utf-8'));manifest['counts']['platform_app.User']+=1;path.write_text(json.dumps(manifest),'utf-8')
        from .models import User
        with self.target():
            with self.assertRaises(CommandError):call_command('restore_platform',source=str(self.bundle),empty_database=True,verbosity=0)
            self.assertFalse(User.objects.exists());self.assertFalse(Path(settings.MEDIA_ROOT).exists())
            manifest['counts']['platform_app.User']-=1;path.write_text(json.dumps(manifest),'utf-8');call_command('restore_platform',source=str(self.bundle),empty_database=True,verbosity=0)

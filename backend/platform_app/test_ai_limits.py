"""No provider traffic: bounded requests, durable attempts, released leases."""
from datetime import timedelta
from unittest.mock import Mock, patch
import uuid
import asyncio
from contextlib import asynccontextmanager
import httpx
from django.conf import settings
from django.test import TestCase, SimpleTestCase, override_settings
from django.utils import timezone
from .ai_limits import model_attempt
from .models import Audit, RuntimeStatus, ExecutionJob
from .execution import profiles
from . import tests as fixtures


@override_settings(AI_API_KEY='fixture-only', AI_BASE_URL='https://model.example.invalid/v1', AI_MODEL='fixture', AI_DAILY_REQUESTS=2, AI_GLOBAL_DAILY_REQUESTS=3, AI_CONCURRENCY=1, AI_MAX_OUTPUT_TOKENS=512, AI_MAX_INPUT_CHARS=30000)
class ModelLiveAdapterTests(TestCase):
    client_class=fixtures.Client
    setUp=fixtures.PlatformTests.setUp
    post=fixtures.PlatformTests.post
    def call(self):
        return self.post('/api/ai/chat', {'messages': [{'role': 'user', 'content': 'mean of 10, 12, 14?'}]})

    def test_request_is_bounded_and_success_releases_slots(self):
        result=Mock();result.json.return_value={'choices':[{'message':{'content':'12'}}], 'usage':{'total_tokens':30}}
        with patch('platform_app.views.request_completion',return_value=result.json.return_value) as client:
            self.assertEqual(self.call().status_code,200)
            self.assertEqual(client.call_args.args[0]['max_tokens'],512)
        self.assertEqual(Audit.objects.filter(action='ai-attempt').count(),1)
        self.assertFalse(RuntimeStatus.objects.filter(name__startswith='ai-slot-',last_seen__gt=timezone.now()).exists())

    def test_failures_count_and_daily_limit_prevents_upstream(self):
        with patch('platform_app.views.request_completion',side_effect=httpx.ReadTimeout('private upstream details')) as client:
            self.assertEqual(self.call().status_code,504)
            self.assertEqual(self.call().status_code,504)
            self.assertEqual(self.call().status_code,429)
            self.assertEqual(client.call_count,2)
        self.assertEqual(Audit.objects.filter(action='ai-attempt').count(),2)

    def test_concurrent_user_and_global_slots_prevent_upstream(self):
        with model_attempt(self.s,'chat'):
            with patch('platform_app.views.request_completion') as client:
                self.assertEqual(self.call().status_code,429)
                self.client.force_login(self.other)
                self.assertEqual(self.call().status_code,429)
                client.assert_not_called()

    def test_quota_error_does_not_expose_provider_response(self):
        response=httpx.Response(429,request=httpx.Request('POST',settings.AI_BASE_URL+'/chat/completions'),text='private credentials and balance')
        with patch('platform_app.views.request_completion',side_effect=httpx.HTTPStatusError('fixture',request=response.request,response=response)) as client:
            result=self.call()
        self.assertEqual(result.status_code,503)
        self.assertNotIn('private',result.content.decode())

    def test_runtime_badge_requires_completed_remote_record_and_cleanup(self):
        with override_settings(E2B_API_KEY='fixture-only'):
            self.assertFalse(next(p for p in profiles() if p['id']=='python')['executionVerified'])
            job=ExecutionJob.objects.create(owner=self.s,client_id=uuid.uuid4(),runtime='python',provider='e2b',code='print(12)',status='completed',remote_id='fixture-remote',cleanup_pending=True)
            self.assertFalse(next(p for p in profiles() if p['id']=='python')['executionVerified'])
            job.cleanup_pending=False;job.save()
            self.assertTrue(next(p for p in profiles() if p['id']=='python')['executionVerified'])


class ModelTransportBoundsTests(SimpleTestCase):
    def factory(self,chunks,delay=0):
        class Response:
            def raise_for_status(self):pass
            async def aiter_bytes(self):
                for chunk in chunks:
                    if delay:await asyncio.sleep(delay)
                    yield chunk
        class Client:
            closed=False
            def __init__(self,**kwargs):pass
            async def __aenter__(self):return self
            async def __aexit__(self,*args):Client.closed=True
            @asynccontextmanager
            async def stream(self,*args,**kwargs):yield Response()
        return Client

    def test_total_deadline_cancels_slow_body_and_closes_client(self):
        from .ai_gateway import request_completion
        client=self.factory([b'{}']*10,delay=.02)
        with patch('platform_app.ai_gateway.httpx.AsyncClient',client),patch('platform_app.ai_gateway.TOTAL_SECONDS',.03):
            with self.assertRaises(httpx.ReadTimeout):request_completion({})
        self.assertTrue(client.closed)

    def test_response_size_limit_closes_client(self):
        from .ai_gateway import request_completion
        client=self.factory([b'12345',b'67890'])
        with patch('platform_app.ai_gateway.httpx.AsyncClient',client),patch('platform_app.ai_gateway.MAX_RESPONSE_BYTES',8):
            with self.assertRaises(ValueError):request_completion({})
        self.assertTrue(client.closed)

    def test_e2b_program_error_is_a_program_failure(self):
        from types import SimpleNamespace
        from e2b import CommandExitException
        from .execution import E2BProvider
        sandbox=Mock();sandbox.get_info.return_value=SimpleNamespace(cpu_count=2,memory_mb=2048)
        sandbox.commands.run.side_effect=CommandExitException(stderr='fixture syntax error',stdout='',exit_code=1,error=None)
        job=SimpleNamespace(id=uuid.uuid4(),runtime='python',code='invalid fixture',limits={'cpus':2,'memoryMb':4096,'seconds':5})
        with patch.object(E2BProvider,'connect',return_value=sandbox):result=E2BProvider().run(job,'fixture',[],lambda text:None)
        self.assertEqual(result['status'],'failed')
        self.assertIn('退出码1',result['error'])

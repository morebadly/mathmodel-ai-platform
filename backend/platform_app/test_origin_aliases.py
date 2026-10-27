from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator
from channels.security.websocket import OriginValidator
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.test import SimpleTestCase, RequestFactory, override_settings
from config.origins import additional_https_origins


class DomainOriginAliasesTests(SimpleTestCase):
    hosts=['model.example.invalid','203.0.113.10']

    def test_exact_aliases_and_deduplication(self):
        value='https://203.0.113.10:9443, https://model.example.invalid,https://203.0.113.10:9443'
        self.assertEqual(additional_https_origins(value,self.hosts),['https://203.0.113.10:9443','https://model.example.invalid'])
        self.assertEqual(additional_https_origins('',self.hosts),[])

    def test_unsafe_or_ambiguous_origins_rejected(self):
        values=['*','https://*.example.invalid','http://203.0.113.10:9443','https://evil.invalid','https://model.example.invalid/','https://model.example.invalid/path','https://user@model.example.invalid','https://model.example.invalid?x=1','https://model.example.invalid#x','https://model.example.invalid:0','https://model.example.invalid:99999','HTTPS://model.example.invalid','https://model.example.invalid:09443']
        for value in values:
            with self.subTest(value=value),self.assertRaises(RuntimeError):
                additional_https_origins(value,self.hosts)

    def test_actual_channels_origin_validator_accepts_only_exact_hosts_and_ports(self):
        origins=additional_https_origins('https://model.example.invalid,https://203.0.113.10:9443',self.hosts)
        async def probe(scope,receive,send):
            await receive()
            await send({'type':'websocket.accept'})
            await receive()
        async def check():
            for origin,expected in [('https://model.example.invalid',True),('https://203.0.113.10:9443',True),('https://model.example.invalid:9443',False),('https://evil.invalid',False),('http://model.example.invalid',False)]:
                ws=ApplicationCommunicator(OriginValidator(probe,origins),{'type':'websocket','path':'/ws/chat/','headers':[(b'origin',origin.encode())],'query_string':b'','subprotocols':[]})
                await ws.send_input({'type':'websocket.connect'})
                reply=await ws.receive_output(timeout=2)
                accepted=reply['type']=='websocket.accept'
                self.assertEqual(accepted,expected,origin)
                await ws.send_input({'type':'websocket.disconnect','code':1000})
                await ws.wait(timeout=2)
        async_to_sync(check)()

    @override_settings(ALLOWED_HOSTS=['model.example.invalid'],CSRF_TRUSTED_ORIGINS=['https://model.example.invalid','https://203.0.113.10:9443'])
    def test_actual_csrf_validation_retains_cookie_and_rejects_other_origins(self):
        factory=RequestFactory()
        for origin,expected in [('https://model.example.invalid',True),('https://203.0.113.10:9443',True),('https://203.0.113.10:9444',False),('https://evil.invalid',False)]:
            request=factory.post('/api/auth/login',{},secure=True,HTTP_HOST='model.example.invalid',HTTP_ORIGIN=origin)
            token=get_token(request)
            request.COOKIES['csrftoken']=request.META['CSRF_COOKIE']
            request.META['HTTP_X_CSRFTOKEN']=token
            middleware=CsrfViewMiddleware(lambda r:HttpResponse('ok'))
            middleware.process_request(request)
            result=middleware.process_view(request,lambda r:HttpResponse('ok'),(),{})
            self.assertEqual(result is None,expected,origin)
        request=factory.post('/api/auth/login',{},secure=True,HTTP_HOST='model.example.invalid',HTTP_ORIGIN='https://model.example.invalid')
        middleware=CsrfViewMiddleware(lambda r:HttpResponse('ok'))
        middleware.process_request(request)
        self.assertEqual(middleware.process_view(request,lambda r:HttpResponse('ok'),(),{}).status_code,403)

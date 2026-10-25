import smtplib
import socket
from unittest.mock import Mock,patch
from django.test import SimpleTestCase,override_settings
from .smtp_backend import EmailBackend,ProxySMTP,ProxySMTP_SSL,proxy_address


class SMTPProxyTests(SimpleTestCase):
    @override_settings(EMAIL_PROXY_URL='')
    def test_empty_proxy_preserves_standard_django_connection(self):
        self.assertIs(EmailBackend(use_ssl=False,use_tls=True).connection_class,smtplib.SMTP)
        self.assertIs(EmailBackend(use_ssl=True,use_tls=False).connection_class,smtplib.SMTP_SSL)

    def test_proxy_configuration_rejects_credentials_and_unsupported_protocols(self):
        self.assertEqual(proxy_address('http://127.0.0.1:7897'),('127.0.0.1',7897))
        for value in ['http://user:secret@localhost:7897','socks5://localhost:7897','http://localhost','http://localhost:7897/path','http://localhost:7897?target=other','http://localhost:99999']:
            with self.subTest(value=value),self.assertRaises(ValueError):proxy_address(value)

    @override_settings(EMAIL_PROXY_URL='http://127.0.0.1:7897')
    def test_backend_selects_proxy_without_changing_global_socket_behavior(self):
        plain=EmailBackend(use_ssl=False,use_tls=True).connection_class
        secure=EmailBackend(use_ssl=True,use_tls=False).connection_class
        self.assertIs(plain.func,ProxySMTP);self.assertIs(secure.func,ProxySMTP_SSL)
        self.assertEqual(plain.keywords,{'proxy_host':'127.0.0.1','proxy_port':7897})

    def test_connect_tunnel_targets_smtp_and_transfers_socket_ownership(self):
        smtp=ProxySMTP(proxy_host='127.0.0.1',proxy_port=7897,local_hostname='isolated.test')
        connection=Mock();connection.sock=Mock();raw=connection.sock
        with patch('platform_app.smtp_backend.HTTPConnection',return_value=connection) as factory:
            self.assertIs(smtp._get_socket('smtp.gmail.com',587,12),raw)
        factory.assert_called_once_with('127.0.0.1',7897,timeout=12,source_address=None)
        connection.set_tunnel.assert_called_once_with('smtp.gmail.com',587)
        self.assertIsNone(connection.sock);connection.close.assert_called_once()

    def test_failed_tunnel_is_closed(self):
        smtp=ProxySMTP(proxy_host='127.0.0.1',proxy_port=7897,local_hostname='isolated.test')
        connection=Mock();connection.connect.side_effect=OSError('connection refused')
        with patch('platform_app.smtp_backend.HTTPConnection',return_value=connection),self.assertRaises(OSError):smtp._get_socket('smtp.gmail.com',587,12)
        connection.close.assert_called_once()

    def test_connect_headers_and_smtp_greeting_in_one_packet_preserve_greeting(self):
        # Use actual TCP sockets: Linux socketpair() returns AF_UNIX sockets,
        # while HTTPConnection correctly enables TCP_NODELAY on its socket.
        listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.addCleanup(listener.close);listener.bind(('127.0.0.1',0));listener.listen(1)
        client=socket.create_connection(listener.getsockname(),timeout=2)
        server,_=listener.accept()
        self.addCleanup(client.close);self.addCleanup(server.close)
        client.settimeout(2)
        server.sendall(b'HTTP/1.0 200 Connection established\r\nProxy-Agent: isolated-test\r\n\r\n220 smtp.example.invalid ESMTP ready\r\n')
        smtp=ProxySMTP(proxy_host='127.0.0.1',proxy_port=7897,local_hostname='isolated.test')
        with patch('http.client.socket.create_connection',return_value=client):
            connection=smtp._get_socket('smtp.example.invalid',587,2)
        self.assertEqual(connection.recv(1024),b'220 smtp.example.invalid ESMTP ready\r\n')
        self.assertTrue(server.recv(4096).startswith(b'CONNECT smtp.example.invalid:587 HTTP/'))

    def test_implicit_tls_uses_original_smtp_hostname_and_closes_on_failure(self):
        context=Mock();smtp=ProxySMTP_SSL(proxy_host='127.0.0.1',proxy_port=7897,local_hostname='isolated.test',context=context)
        smtp._host='smtp.gmail.com';connection=Mock();raw=connection.sock
        with patch('platform_app.smtp_backend.HTTPConnection',return_value=connection):
            self.assertIs(smtp._get_socket('smtp.gmail.com',465,12),context.wrap_socket.return_value)
        context.wrap_socket.assert_called_once_with(raw,server_hostname='smtp.gmail.com')
        connection=Mock();raw=connection.sock;context.wrap_socket.side_effect=OSError('certificate validation failed')
        with patch('platform_app.smtp_backend.HTTPConnection',return_value=connection),self.assertRaises(OSError):smtp._get_socket('smtp.gmail.com',465,12)
        raw.close.assert_called_once()

"""Django SMTP with an optional HTTP CONNECT tunnel; TLS stays end-to-end."""
from functools import partial
from http.client import HTTPConnection,HTTPResponse
import smtplib
from urllib.parse import urlsplit
from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPBackend


def proxy_address(value):
    try:
        proxy=urlsplit(value)
        port=proxy.port
        if proxy.scheme!='http' or not proxy.hostname or not port or proxy.username or proxy.password or proxy.path not in ['', '/'] or proxy.query or proxy.fragment:
            raise ValueError
        return proxy.hostname,port
    except ValueError:
        raise ValueError('EMAIL_PROXY_URL 必须是包含端口、不含账号密码的 HTTP 代理地址。') from None


class HTTPConnectMixin:
    def __init__(self,*args,proxy_host,proxy_port,**kwargs):
        self.proxy_host=proxy_host
        self.proxy_port=proxy_port
        super().__init__(*args,**kwargs)

    def _get_socket(self,host,port,timeout):
        tunnel=HTTPConnection(self.proxy_host,self.proxy_port,timeout=timeout,source_address=self.source_address)
        # A buffered CONNECT parser can read ahead into SMTP's 220 greeting.
        # Keep stdlib status/header validation, but do not buffer past the headers.
        tunnel.response_class=UnbufferedConnectResponse
        try:
            tunnel.set_tunnel(host,port)
            tunnel.connect()
            connection=tunnel.sock
            if connection is None:raise OSError('SMTP proxy did not open a socket.')
            tunnel.sock=None
            return connection
        finally:
            tunnel.close()


class UnbufferedConnectResponse(HTTPResponse):
    def __init__(self,sock,*args,**kwargs):
        class ReaderSocket:
            def makefile(self,mode):
                return sock.makefile(mode,buffering=0)
        super().__init__(ReaderSocket(),*args,**kwargs)


class ProxySMTP(HTTPConnectMixin,smtplib.SMTP):
    pass


class ProxySMTP_SSL(HTTPConnectMixin,smtplib.SMTP_SSL):
    def _get_socket(self,host,port,timeout):
        connection=HTTPConnectMixin._get_socket(self,host,port,timeout)
        try:
            return self.context.wrap_socket(connection,server_hostname=self._host)
        except Exception:
            connection.close()
            raise


class EmailBackend(DjangoSMTPBackend):
    @property
    def connection_class(self):
        proxy=getattr(settings,'EMAIL_PROXY_URL','')
        if not proxy:return super().connection_class
        host,port=proxy_address(proxy)
        return partial(ProxySMTP_SSL if self.use_ssl else ProxySMTP,proxy_host=host,proxy_port=port)

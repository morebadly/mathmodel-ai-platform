"""Exact HTTPS aliases for a controlled domain transition."""
from urllib.parse import urlsplit


def additional_https_origins(value, allowed_hosts):
    """Only configured exact hosts may become CSRF/WebSocket origin aliases."""
    hosts={host.strip().lower() for host in allowed_hosts if host.strip()}
    result=[]
    for item in value.split(','):
        origin=item.strip()
        if not origin:
            continue
        try:
            parsed=urlsplit(origin)
            host=parsed.hostname
            port=parsed.port
            if (parsed.scheme!='https' or not host or parsed.username is not None
                    or parsed.password is not None or parsed.path or parsed.query
                    or parsed.fragment or '*' in origin or host not in hosts
                    or (port is not None and not 1<=port<=65535)):
                raise ValueError('Invalid exact HTTPS origin')
            authority=('['+host+']') if ':' in host else host
            if port is not None:
                authority+=':'+str(port)
            if origin!='https://'+authority:
                raise ValueError('Use the canonical HTTPS origin')
        except ValueError as exc:
            raise RuntimeError('MATHMODEL_ADDITIONAL_HTTPS_ORIGINS 必须为已允许主机的精确 HTTPS 来源，不允许通配符、路径或用户信息。') from exc
        if origin not in result:
            result.append(origin)
    return result

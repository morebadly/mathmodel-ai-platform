from django.http import JsonResponse
from django.db import connection
from django.conf import settings
from django.utils import timezone
from .models import RuntimeStatus

def live(request):return JsonResponse({'status':'alive','app':'MathModel AI','asgi':True})
def ready(request):
    checks={}
    try:
        with connection.cursor() as cursor:cursor.execute('SELECT 1');cursor.fetchone()
        checks['database']=True
    except Exception:checks['database']=False
    if settings.REDIS_URL:
        try:
            from redis import Redis
            checks['redis']=bool(Redis.from_url(settings.REDIS_URL,socket_connect_timeout=2,socket_timeout=2).ping())
        except Exception:checks['redis']=False
    try:
        marker=RuntimeStatus.objects.filter(name='maintenance').first()
        checks['scheduler']=bool(marker and (timezone.now()-marker.last_seen).total_seconds()<120)
    except Exception:checks['scheduler']=False
    return JsonResponse({'status':'ready' if all(checks.values()) else 'degraded','checks':checks},status=200 if all(checks.values()) else 503)

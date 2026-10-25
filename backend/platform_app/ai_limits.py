"""Persisted attempt limits and expiring leases; never hold DB locks over HTTP."""
from contextlib import contextmanager
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import Throttled
from .models import Audit, RuntimeStatus, User


@contextmanager
def model_attempt(user, operation):
    now = timezone.now()
    expired = now - timedelta(days=1)
    lease = now + timedelta(seconds=300)
    with transaction.atomic():
        RuntimeStatus.objects.get_or_create(name='ai-admission', defaults={'last_seen': now})
        RuntimeStatus.objects.select_for_update().get(name='ai-admission')
        User.objects.select_for_update().get(pk=user.pk)
        attempts = Audit.objects.filter(action='ai-attempt', created_at__gte=expired)
        if attempts.filter(actor=user).count() >= settings.AI_DAILY_REQUESTS:
            raise Throttled(detail='已达到当前账号24小时内的模型调用限额。')
        if attempts.count() >= settings.AI_GLOBAL_DAILY_REQUESTS:
            raise Throttled(detail='平台24小时内的模型调用限额已用完，请联系管理员。')
        user_slot, _ = RuntimeStatus.objects.get_or_create(name='aiu' + str(user.pk), defaults={'last_seen': expired})
        if user_slot.last_seen > now:
            raise Throttled(detail='上一条模型请求仍在处理中，请稍后再试。')
        slot = None
        for index in range(settings.AI_CONCURRENCY):
            row, _ = RuntimeStatus.objects.get_or_create(name='ai-slot-' + str(index), defaults={'last_seen': expired})
            if row.last_seen <= now:
                slot = row
                break
        if slot is None:
            raise Throttled(detail='模型服务繁忙，请稍后再试。')
        for row in (user_slot, slot):
            row.last_seen = lease
            row.save(update_fields=['last_seen'])
        Audit.objects.create(actor=user, action='ai-attempt', target=operation)
    try:
        yield
    finally:
        RuntimeStatus.objects.filter(name__in=[user_slot.name, slot.name], last_seen=lease).update(last_seen=timezone.now())

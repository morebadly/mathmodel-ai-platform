from celery import shared_task
@shared_task
def maintenance():
    from django.db import close_old_connections
    from django.utils import timezone
    from .models import RuntimeStatus
    from .mail import evaluate_plans,process_mail
    from .retrieval import process_indexes
    from .execution import reap
    close_old_connections()
    evaluate_plans();process_mail();process_indexes();reap()
    RuntimeStatus.objects.update_or_create(name='maintenance',defaults={'last_seen':timezone.now()})
    close_old_connections()

@shared_task
def media_tick():
    from django.db import close_old_connections
    from .parsing import parse_pending
    close_old_connections()
    try:parse_pending(limit=1)
    finally:close_old_connections()

@shared_task
def execution_tick():
    from django.db import close_old_connections
    from .execution import dispatch
    close_old_connections()
    try:dispatch(limit=1)
    finally:close_old_connections()

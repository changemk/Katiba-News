"""Persistent local alerts and heartbeat evaluation for backend monitoring."""
from datetime import timedelta
from django.utils import timezone
from .models import CollectionAlert, SchedulerState, Source
from .source_catalog import SOURCES


def ensure_sources():
    for slug, config in SOURCES.items():
        Source.objects.get_or_create(slug=slug, defaults={'name': config['name'], 'feed_url': config['feed_url']})


def refresh_alerts():
    now = timezone.now()
    for source in Source.objects.all():
        # A small grace period avoids flagging a normal timer tick as a failure.
        overdue = source.enabled and bool(source.next_check and source.next_check < now - timedelta(minutes=10))
        conditions = {'failures': source.enabled and source.failures >= 3, 'overdue': overdue}
        for kind, active in conditions.items():
            if active:
                message = (f'{source.failures} consecutive collection failures: {source.last_error}'
                           if kind == 'failures' else 'Collection is more than 10 minutes overdue. Check the scheduler.')
                CollectionAlert.objects.update_or_create(source=source, kind=kind, resolved_at=None,
                                                         defaults={'message': message})
            else:
                CollectionAlert.objects.filter(source=source, kind=kind, resolved_at=None).update(resolved_at=now)


def scheduler_status():
    state = SchedulerState.objects.filter(pk='sources').first()
    if not state or not state.last_started:
        return 'Not started'
    if state.last_started < timezone.now() - timedelta(minutes=10):
        return 'Missed heartbeat — check the scheduler'
    if state.last_error:
        return 'Running with collection errors'
    return 'Recent heartbeat'

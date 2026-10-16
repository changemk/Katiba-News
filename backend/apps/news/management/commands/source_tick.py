"""One scheduled tick. The OS timer handles repetition and process restarts."""
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.news.models import SchedulerState
from apps.news.monitoring import ensure_sources, refresh_alerts


class Command(BaseCommand):
    help = 'Check all due feeds, refresh local alerts, and record scheduler heartbeat.'

    def handle(self, *args, **options):
        ensure_sources()
        SchedulerState.objects.update_or_create(pk='sources', defaults={'last_started': timezone.now(), 'last_error': ''})
        try:
            call_command('collect_sources', source='all', stdout=self.stdout, stderr=self.stderr)
        except Exception as exc:
            SchedulerState.objects.filter(pk='sources').update(last_error=str(exc)[:2000])
            raise
        finally:
            SchedulerState.objects.filter(pk='sources').update(last_finished=timezone.now())
            refresh_alerts()

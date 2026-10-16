"""CLI entry point: process due sources independently and report partial failures."""
import json
from django.core.management.base import BaseCommand, CommandError
from apps.news.sourcing import collect_source
from apps.news.source_catalog import SOURCES


class Command(BaseCommand):
    help = 'Collect due constitutional-news feeds from the reviewed source catalog.'

    def add_arguments(self, parser):
        parser.add_argument('--source', choices=[*SOURCES, 'all'], default='kenya-law')

    def handle(self, *args, **options):
        slugs = list(SOURCES) if options['source'] == 'all' else [options['source']]
        failed = []
        for slug in slugs:
            # A failing publisher must not prevent collecting other sources.
            try:
                result = collect_source(slug)
            except Exception as exc:
                failed.append(slug)
                result = {'error': str(exc)}
            self.stdout.write(json.dumps({'source': slug, **result}))
        if failed:
            raise CommandError('Collection failed for: ' + ', '.join(failed))

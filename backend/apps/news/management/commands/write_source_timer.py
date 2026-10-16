"""Generate reviewable user-systemd units; installation is a separate explicit step."""
import sys
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Write a user service and five-minute timer for due source checks.'

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', required=True)

    def handle(self, *args, **options):
        # A /tmp virtualenv can disappear at reboot; never install it in a timer.
        executable = Path(sys.executable).absolute()
        if str(executable).startswith('/tmp/'):
            raise CommandError('Use a persistent virtual environment, not /tmp, to generate a timer.')
        output = Path(options['output_dir']).resolve()
        output.mkdir(parents=True, exist_ok=True)
        backend = Path(settings.BASE_DIR)
        database = Path(settings.DATABASES['default']['NAME']).resolve()

        def quote(value):
            # systemd performs percent specifier expansion even inside quotes.
            return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'

        service = f'''[Unit]
Description=Katiba constitutional news collection
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory={str(backend.parent).replace('%', '%%')}
Environment={quote('KATIBA_SOURCING_DB=' + str(database))}
ExecStart={quote(executable)} {quote(backend / 'manage.py')} source_tick --settings=apps.news.sourcing_settings
TimeoutStartSec=10min
NoNewPrivileges=true
'''
        timer = '''[Unit]
Description=Check due Katiba sources every five minutes

[Timer]
OnCalendar=*:0/5
OnStartupSec=1min
Persistent=true
RandomizedDelaySec=15
Unit=katiba-sourcing.service

[Install]
WantedBy=timers.target
'''
        (output / 'katiba-sourcing.service').write_text(service)
        (output / 'katiba-sourcing.timer').write_text(timer)
        self.stdout.write(f'Wrote units to {output}. Link and enable them with systemctl --user.')

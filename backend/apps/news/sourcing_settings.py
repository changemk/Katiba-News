"""Opt-in sourcing configuration; leaves the project's base settings untouched."""
import os
from katiba_news.settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, 'apps.news.apps.NewsConfig']  # noqa: F405
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': os.environ.get('KATIBA_SOURCING_DB', str(BASE_DIR / 'sourcing.sqlite3')),  # noqa: F405
}}

# Keep API wiring local to this app rather than editing project-wide routes.
ROOT_URLCONF = 'apps.news.sourcing_urls'

# Match the existing user migration's BigAutoField in this opt-in environment.
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

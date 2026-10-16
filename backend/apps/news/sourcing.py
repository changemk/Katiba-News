"""Metadata-only collection from reviewed Kenyan constitutional-news feeds."""
import hashlib
import json
import re
import time
from datetime import timedelta, timezone as dt_timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.robotparser import RobotFileParser

from defusedxml import ElementTree
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Lead, LeadRevision, Source, TopicRule
from .source_catalog import SOURCES
from .topics import plain_text, topic_matches

FEED_URL = 'https://new.kenyalaw.org/feeds/judgments.xml'
ROBOTS_URL = 'https://new.kenyalaw.org/robots.txt'
USER_AGENT = 'KatibaNewsSourcing/0.1'
ATOM = '{http://www.w3.org/2005/Atom}'
MAX_BYTES = 2_000_000


class NoRedirects(HTTPRedirectHandler):
    """Require review of feed moves instead of following an unapproved location."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Source redirected; review its new location before collecting.')


def fetch(url, headers=None):
    """Return bounded response bytes and headers; HTTP 304 returns None bytes.

    Network, size-limit and redirect failures propagate to collect_source(),
    which records the error and defers the next eligible attempt.
    """
    request = Request(url, headers={'User-Agent': USER_AGENT, **(headers or {})})
    try:
        with build_opener(NoRedirects()).open(request, timeout=30) as response:
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError('Source response exceeds the size limit.')
            return data, response.headers
    except HTTPError as exc:
        if exc.code == 304:
            return None, exc.headers
        raise


def date_value(value):
    """Normalize a supplied timestamp to UTC; missing dates remain unknown."""
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None or timezone.is_naive(parsed):
        raise ValueError(f'Invalid or timezone-less feed timestamp: {value}')
    return parsed.astimezone(dt_timezone.utc).isoformat()


def official_url(value, source_slug='kenya-law'):
    """Validate publisher host/path; retain query identity and drop fragments."""
    config = SOURCES[source_slug]
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or parsed.netloc != config['host']
            or not parsed.path.startswith(config['path_prefix'])):
        raise ValueError('Feed entry has an unexpected document URL.')
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), parsed.query, ''))


def parse_feed(data, source_slug='kenya-law'):
    """Parse Atom or RSS into metadata dictionaries without fetching articles.

    Malformed entries fail the run before any lead writes, rather than silently
    accepting a partial feed. Topic hints are derived separately from metadata.
    """
    root = ElementTree.fromstring(data)
    if root.tag == 'rss':
        return parse_rss(root, source_slug)
    if root.tag != ATOM + 'feed':
        raise ValueError('Expected an Atom or RSS feed.')
    items = []
    for entry in root.findall(ATOM + 'entry'):
        title = ' '.join((entry.findtext(ATOM + 'title') or '').split())
        links = [link.get('href') for link in entry.findall(ATOM + 'link')
                 if link.get('rel', 'alternate') == 'alternate' and link.get('href')]
        if not title or not links:
            raise ValueError('Feed entry is missing a title or original link.')
        url = official_url(links[0], source_slug)
        external_id = (entry.findtext(ATOM + 'id') or url).strip()
        if not external_id or len(external_id) > 1000 or len(url) > 1000:
            raise ValueError('Invalid feed entry identity.')
        items.append({
            'external_id': external_id, 'title': title, 'original_url': url,
            'published_at': date_value(entry.findtext(ATOM + 'published')),
            'source_updated_at': date_value(entry.findtext(ATOM + 'updated')),
            'topic_matches': topic_matches(title=title, summary=entry.findtext(ATOM + 'summary') or ''),
        })
    return items


def parse_rss(root, source_slug):
    """Adapt RSS dates/IDs and use descriptions only for transient topic matching."""
    if root.find('channel') is None:
        raise ValueError('RSS feed is missing its channel.')
    items = []
    for entry in root.findall('channel/item'):
        title = plain_text(entry.findtext('title'))
        link = entry.findtext('link')
        if not title or not link:
            raise ValueError('Feed entry is missing a title or original link.')
        url = official_url(link.strip(), source_slug)
        external_id = (entry.findtext('guid') or url).strip()
        if not external_id or len(external_id) > 1000 or len(url) > 1000:
            raise ValueError('Invalid feed entry identity.')
        published = entry.findtext('pubDate')
        # RSS uses RFC 2822 dates rather than Atom's ISO 8601 dates.
        published = date_value(parsedate_to_datetime(published).isoformat()) if published else None
        items.append({'external_id': external_id, 'title': title, 'original_url': url,
                      'published_at': published, 'source_updated_at': None,
                      'topic_matches': topic_matches(title=title,
                          summary=entry.findtext('description') or '',
                          category=' '.join(
                              node.text or '' for node in entry.findall('category')))})
    return items


def persist_items(source, items, now):
    """Atomically upsert one source batch and return new/updated/unchanged counts.

    Identity is scoped to the publisher. Snapshots exclude derived topic hints;
    only source-owned columns and hints are updated on existing leads.
    """
    counts = {'new': 0, 'updated': 0, 'unchanged': 0}
    with transaction.atomic():
        for item in items:
            # Topic hints are derived, so changing a matching rule must not invent
            # a source revision or overwrite an editor's manually maintained tags.
            metadata = {key: value for key, value in item.items() if key != 'topic_matches'}
            fingerprint = hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest()
            defaults = {key: value for key, value in item.items() if key != 'external_id'}
            lead, created = Lead.objects.get_or_create(source=source, external_id=item['external_id'],
                defaults={**defaults, 'fingerprint': fingerprint, 'last_seen': now})
            changed = lead.fingerprint != fingerprint
            if created or changed:
                LeadRevision.objects.create(lead=lead, fingerprint=fingerprint, metadata=metadata)
            if changed:
                Lead.objects.filter(pk=lead.pk).update(**defaults, fingerprint=fingerprint,
                    last_seen=now, has_update=True)
            elif not created:
                Lead.objects.filter(pk=lead.pk).update(last_seen=now, topic_matches=item.get('topic_matches', []))
            counts['new' if created else 'updated' if changed else 'unchanged'] += 1
    return counts


def collect_source(source_slug='kenya-law'):
    """Run one due feed from the reviewed catalog, or report why it was skipped.

    Reserve the interval, check robots, fetch conditionally, filter new leads,
    then commit metadata and success state together. Failures are recorded and
    re-raised; a later command invocation performs the retry (no background job
    is started here). The reservation expires even if a process crashes.
    """
    config = SOURCES[source_slug]
    feed_url = config['feed_url']
    robots_url = f"https://{config['host']}/robots.txt"
    source, _ = Source.objects.get_or_create(slug=source_slug, defaults={
        'name': config['name'], 'feed_url': feed_url})
    now = timezone.now()
    # Atomic reservation prevents overlapping runs. A crashed worker can retry later.
    claimed = Source.objects.filter(pk=source.pk, enabled=True).filter(
        Q(next_check__isnull=True) | Q(next_check__lte=now)
    ).update(last_attempt=now, next_check=now + timedelta(minutes=max(15, source.interval_minutes)))
    if not claimed:
        return {'skipped': 'Source is disabled, already running, or not due.'}
    try:
        if source.feed_url != feed_url:
            raise ValueError('Unverified feed URL; review the collector configuration.')
        robots_data, _ = fetch(robots_url)
        if not robots_data:
            raise ValueError('Could not verify robots.txt.')
        robots = RobotFileParser()
        robots.parse(robots_data.decode('utf-8').splitlines())
        if not robots.can_fetch(USER_AGENT, feed_url):
            raise ValueError('robots.txt does not permit feed collection.')
        delay = max(5, robots.crawl_delay(USER_AGENT) or 0)
        if delay > 60:
            raise ValueError('Source crawl delay requires scheduling review.')
        time.sleep(delay)
        headers = {'Accept': 'application/atom+xml, application/rss+xml'}
        if source.etag:
            headers['If-None-Match'] = source.etag
        if source.last_modified:
            headers['If-Modified-Since'] = source.last_modified
        data, response_headers = fetch(feed_url, headers)
        with transaction.atomic():
            if data is None:
                counts = {'not_modified': True}
            else:
                items = parse_feed(data, source_slug)
                # Editor-approved feedback rules extend title matching without
                # changing source fingerprints or copying publisher article text.
                rules = list(TopicRule.objects.filter(enabled=True).values('phrase', 'topic'))
                for item in items:
                    for rule in rules:
                        if re.search(r'(?<!\w)' + re.escape(rule['phrase']) + r'(?!\w)', item['title'], re.I):
                            item['topic_matches'].append({'topic': rule['topic'], 'term': rule['phrase'], 'field': 'title (editor rule)'})
                filtered = 0
                if config['filter_topics']:
                    # Keep tracking existing leads even if an update loses its
                    # keywords; this preserves editorial decisions and history.
                    existing = set(Lead.objects.filter(source=source,
                        external_id__in=[item['external_id'] for item in items]
                    ).values_list('external_id', flat=True))
                    relevant = [item for item in items if item['topic_matches'] or item['external_id'] in existing]
                    filtered = len(items) - len(relevant)
                    items = relevant
                counts = persist_items(source, items, now)
                if config['filter_topics']:
                    counts['filtered_out'] = filtered
            Source.objects.filter(pk=source.pk).update(last_success=timezone.now(), failures=0,
                last_error='', etag=response_headers.get('ETag', source.etag if data is None else ''),
                last_modified=response_headers.get('Last-Modified', source.last_modified if data is None else ''))
        from .monitoring import refresh_alerts
        refresh_alerts()
        return counts
    except Exception as exc:
        # Persist backoff instead of sleeping through retries. Other publishers
        # can still be checked by the multi-source command in this invocation.
        failures = source.failures + 1
        minutes = min(1440, max(15, source.interval_minutes) * (2 ** min(failures, 10)))
        Source.objects.filter(pk=source.pk).update(failures=failures, last_error=str(exc)[:2000],
            next_check=timezone.now() + timedelta(minutes=minutes))
        from .monitoring import refresh_alerts
        refresh_alerts()
        raise

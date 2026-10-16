"""Reviewed feed allowlist. Adding a URL in the database never authorizes a new host.

Verified 2026-09-19: both RSS feeds return publisher-owned news; robots.txt
permits the feed paths. These are discovery sources, not guarantees of accuracy.
"""
SOURCES = {
    'kenya-law': {
        'name': 'Kenya Law — judgments',
        'feed_url': 'https://new.kenyalaw.org/feeds/judgments.xml',
        'host': 'new.kenyalaw.org',
        'path_prefix': '/akn/ke/judgment/',
        'kind': 'Official legal publication',
        'context': 'Original judgments. Read the decision before reporting its effect.',
        'filter_topics': False,
    },
    'katiba-institute': {
        'name': 'Katiba Institute — constitutional affairs',
        'feed_url': 'https://katibainstitute.org/feed/',
        'host': 'katibainstitute.org',
        'path_prefix': '/',
        'kind': 'Civil society / constitutional advocacy',
        'context': 'May be a party to litigation. Corroborate legal outcomes with the judgment.',
        'filter_topics': True,
    },
    'judiciary': {
        'name': 'Judiciary of Kenya — constitutional affairs',
        'feed_url': 'https://judiciary.go.ke/feed/',
        'host': 'judiciary.go.ke',
        'path_prefix': '/',
        'kind': 'Official institutional news',
        'context': 'Institutional announcements and statements; not a substitute for a judgment.',
        'filter_topics': True,
    },
}


def source_context(slug):
    config = SOURCES.get(slug, {})
    return {'kind': config.get('kind', 'Unreviewed source'),
            'context': config.get('context', 'No source assessment recorded.')}

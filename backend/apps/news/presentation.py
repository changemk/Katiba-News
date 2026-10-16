"""Shared, read-only presentation for the admin inbox and sourcing API."""
from django.utils import timezone


def source_health(source):
    # "Due" describes scheduling, not a claim that a worker is currently running.
    if not source.enabled:
        return 'disabled'
    if source.failures:
        return 'retry_due' if source.next_check and source.next_check <= timezone.now() else 'retry_scheduled'
    if not source.last_success:
        return 'never_collected'
    if not source.next_check or source.next_check <= timezone.now():
        return 'due'
    return 'scheduled'


def revision_history(lead):
    """Compare each saved snapshot with its predecessor, including reverted values."""
    previous = None
    history = []
    for revision in lead.revisions.order_by('captured_at', 'pk'):
        changes = []
        if previous is not None:
            for field in sorted(previous.keys() | revision.metadata.keys()):
                before, after = previous.get(field), revision.metadata.get(field)
                if before != after:
                    changes.append({'field': field, 'previous': before, 'current': after})
        history.append({'id': revision.pk, 'captured_at': revision.captured_at,
                        'initial': previous is None, 'changes': changes,
                        'metadata': revision.metadata})
        previous = revision.metadata
    return list(reversed(history))

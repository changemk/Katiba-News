"""Shared editorial services so API and admin record consistent history."""
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import EditorialEvent, Lead, StoryGroup

EDITORIAL_FIELDS = ('status', 'has_update', 'tags', 'notes', 'brief', 'assigned_to_id',
                    'relevance', 'relevance_reason', 'story_group_id')


def snapshot(lead):
    return {field: getattr(lead, field) for field in EDITORIAL_FIELDS}


def audit(lead, actor, action, before):
    after = snapshot(lead)
    changes = {field: {'previous': before[field], 'current': value}
               for field, value in after.items() if value != before[field]}
    if changes:
        EditorialEvent.objects.create(lead=lead, actor=actor, actor_name=actor.get_username(),
                                      action=action, changes=changes)


@transaction.atomic
def group_leads(lead, other, actor):
    """Attach one ungrouped lead, or join an existing group. Never silently merge groups."""
    if lead.pk == other.pk:
        raise ValidationError('Choose a different lead.')
    locked = {item.pk: item for item in Lead.objects.select_for_update().filter(
        pk__in=[lead.pk, other.pk]).order_by('pk')}
    lead, other = locked[lead.pk], locked[other.pk]
    if lead.story_group_id and other.story_group_id and lead.story_group_id != other.story_group_id:
        raise ValidationError('These leads belong to different groups. Unlink one before regrouping.')
    group = lead.story_group or other.story_group or StoryGroup.objects.create(title=lead.title[:500])
    for item in (lead, other):
        before = snapshot(item)
        item.story_group = group
        item.save(update_fields=['story_group'])
        audit(item, actor, 'group', before)
    return group

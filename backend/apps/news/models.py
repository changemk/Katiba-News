"""Source collection state, editorial leads, and immutable-by-convention snapshots."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Source(models.Model):
    """One publisher feed and its persisted polling/backoff state."""
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=200)
    feed_url = models.URLField(max_length=1000)
    enabled = models.BooleanField(default=True)
    interval_minutes = models.PositiveIntegerField(default=60)
    last_attempt = models.DateTimeField(null=True, blank=True)
    last_success = models.DateTimeField(null=True, blank=True)
    next_check = models.DateTimeField(null=True, blank=True)
    failures = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    etag = models.CharField(max_length=500, blank=True)
    last_modified = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.name


class Lead(models.Model):
    """A source item plus editorial decisions that collection must preserve."""
    class Status(models.TextChoices):
        NEW = 'new', 'New'
        SELECTED = 'selected', 'Selected'
        ASSIGNED = 'assigned', 'Assigned'
        DISMISSED = 'dismissed', 'Dismissed'

    source = models.ForeignKey(Source, on_delete=models.PROTECT)
    external_id = models.CharField(max_length=1000)
    title = models.TextField()
    original_url = models.URLField(max_length=1000)
    published_at = models.DateTimeField(null=True, blank=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    discovered_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField()
    fingerprint = models.CharField(max_length=64)
    has_update = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    topic_matches = models.JSONField(default=list, blank=True, help_text='Automatic topic hints; editors must verify relevance.')
    relevance = models.CharField(max_length=12, default='unreviewed', choices=[
        ('unreviewed', 'Unreviewed'), ('relevant', 'Relevant'), ('irrelevant', 'Irrelevant')])
    relevance_reason = models.TextField(blank=True)
    story_group = models.ForeignKey('StoryGroup', null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='leads')
    tags = models.CharField(max_length=500, blank=True, help_text='Editor-managed topic tags')
    notes = models.TextField(blank=True)
    brief = models.TextField(blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, limit_choices_to={'groups__name': 'Author', 'is_active': True})

    class Meta:
        permissions = [
            ('view_assigned_lead', 'View own assigned source leads'),
            ('review_lead', 'Review source leads and relevance'),
            ('assign_lead', 'Assign source leads to authors'),
            ('group_lead', 'Group related source coverage'),
        ]
        ordering = ['-discovered_at']
        constraints = [models.UniqueConstraint(fields=['source', 'external_id'], name='news_external_identity')]

    def clean(self):
        """Validate editorial assignments in admin and API validation paths.

        Django save() does not call this automatically; other writers must call
        full_clean() before persisting editorial changes.
        """
        from apps.users.access import eligible_author
        if self.assigned_to_id and not eligible_author(self.assigned_to):
            raise ValidationError({'assigned_to': 'Choose an active member of the Author group with assignment access.'})
        if self.status == self.Status.ASSIGNED and (not self.assigned_to_id or not self.brief.strip()):
            raise ValidationError('Assigned leads require an author and a reporting brief.')

    @property
    def needs_reassignment(self):
        # Derived live: removing Author membership or deactivating an account
        # revokes access immediately while preserving the previous assignment.
        from apps.users.access import eligible_author
        return self.status == self.Status.ASSIGNED and (
            not self.assigned_to_id or not eligible_author(self.assigned_to))

    def __str__(self):
        return self.title


class LeadRevision(models.Model):
    """Snapshot created on first capture and each source-metadata change."""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='revisions')
    captured_at = models.DateTimeField(auto_now_add=True)
    fingerprint = models.CharField(max_length=64)
    metadata = models.JSONField()

    class Meta:
        ordering = ['-captured_at']


class StoryGroup(models.Model):
    """Editor-confirmed related coverage; each lead keeps its own attribution."""
    title = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class EditorialEvent(models.Model):
    """Append-only through app interfaces; source revisions remain separate."""
    lead = models.ForeignKey(Lead, on_delete=models.PROTECT, related_name='editorial_events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actor_name = models.CharField(max_length=150)
    action = models.CharField(max_length=40)
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class TopicRule(models.Model):
    """An explicitly approved phrase derived from editorial feedback, not automatic training."""
    phrase = models.CharField(max_length=120, unique=True)
    topic = models.CharField(max_length=60)
    enabled = models.BooleanField(default=True)
    rationale = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.topic}: {self.phrase}'


class CollectionAlert(models.Model):
    """Local collection alert; no email or other outbound notification is sent."""
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='alerts')
    kind = models.CharField(max_length=20, choices=[('failures', 'Repeated failures'), ('overdue', 'Missed check')])
    message = models.TextField()
    opened_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source', 'kind'],
            condition=models.Q(resolved_at__isnull=True), name='news_one_open_alert')]


class SchedulerState(models.Model):
    """Persisted heartbeat for scheduled invocations and backend health checks."""
    name = models.CharField(max_length=40, primary_key=True, default='sources')
    last_started = models.DateTimeField(null=True)
    last_finished = models.DateTimeField(null=True)
    last_error = models.TextField(blank=True)

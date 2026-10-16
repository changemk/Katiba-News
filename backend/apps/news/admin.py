"""A compact editorial inbox with safe links and readable source history."""
from django.contrib import admin
from django.utils.html import format_html, format_html_join
from .models import Lead, Source, EditorialEvent, TopicRule, CollectionAlert
from .editorial import snapshot, audit
from apps.users.access import has_news_permission
from .presentation import revision_history, source_health
from .source_catalog import source_context


class ReviewFilter(admin.SimpleListFilter):
    title = 'review queue'
    parameter_name = 'review'

    def lookups(self, request, model_admin):
        return [('unreviewed', 'New leads'), ('updated', 'Source updates to review')]

    def queryset(self, request, queryset):
        if self.value() == 'unreviewed':
            return queryset.filter(status=Lead.Status.NEW)
        if self.value() == 'updated':
            return queryset.filter(has_update=True)
        return queryset


class ConstitutionalFilter(admin.SimpleListFilter):
    title = 'constitutional topic hints'
    parameter_name = 'constitutional'

    def lookups(self, request, model_admin):
        return [('yes', 'Has topic matches'), ('no', 'No topic matches')]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(topic_matches=[])
        if self.value() == 'no':
            return queryset.filter(topic_matches=[])
        return queryset


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('title', 'source', 'source_link', 'status', 'has_update', 'needs_reassignment',
                    'source_publication', 'discovery_time', 'assigned_to')
    list_filter = (ReviewFilter, ConstitutionalFilter, 'source', 'status', 'has_update', 'relevance')
    search_fields = ('title', 'original_url', 'tags', 'notes')
    list_select_related = ('source', 'assigned_to')
    list_per_page = 25
    ordering = ('-discovered_at', '-pk')
    readonly_fields = ('source', 'external_id', 'title', 'source_link',
                       'source_publication', 'source_updated_at', 'discovery_time',
                       'last_seen', 'fingerprint', 'change_history', 'topic_hints', 'publisher_context')
    fieldsets = (
        ('Original source', {'fields': ('title', 'source', 'source_link',
            'source_publication', 'discovery_time', 'source_updated_at', 'last_seen', 'publisher_context', 'topic_hints'),
            'description': 'Publication is the timestamp supplied by the feed; discovery is when Katiba first collected it.'}),
        ('Editorial review', {'fields': ('status', 'has_update', 'tags', 'notes', 'assigned_to', 'brief', 'relevance', 'relevance_reason'),
            'description': 'Review the history below before clearing the update flag. Assigned leads require an author and brief.'}),
        ('Source change history', {'fields': ('change_history',)}),
        ('Identifiers', {'fields': ('external_id', 'fingerprint'), 'classes': ('collapse',)}),
    )

    def has_change_permission(self, request, obj=None):
        # The admin form edits several actions at once; require both grants.
        return all(has_news_permission(request.user, permission)
                   for permission in ('view_lead', 'review_lead', 'assign_lead'))

    def save_model(self, request, obj, form, change):
        # Django wraps admin change forms in a transaction. Write only editorial
        # fields, so a concurrent collector cannot lose its source metadata.
        previous = Lead.objects.get(pk=obj.pk)
        before = snapshot(previous)
        fields = [field for field in form.changed_data if field in
                  ('status', 'has_update', 'tags', 'notes', 'assigned_to', 'brief', 'relevance', 'relevance_reason')]
        if fields:
            obj.save(update_fields=fields)
        audit(obj, request.user, 'admin_edit', before)

    @admin.display(description='Source perspective')
    def publisher_context(self, obj):
        context = source_context(obj.source.slug)
        return f"{context['kind']}: {context['context']}"

    @admin.display(description='Why this may concern the Constitution')
    def topic_hints(self, obj):
        return format_html_join('', '<p>{}: “{}” in {}</p>',
            ((match['topic'], match['term'], match['field']) for match in obj.topic_matches)
        ) or 'No keyword matches. Relevance still needs editorial review.'

    @admin.display(description='Original document')
    def source_link(self, obj):
        # format_html escapes source-controlled values; never mark titles as safe.
        return format_html('<a href="{}" target="_blank" rel="noopener noreferrer">Open original document</a>', obj.original_url)

    @admin.display(description='Published by source', ordering='published_at')
    def source_publication(self, obj):
        return obj.published_at

    @admin.display(description='Discovered by Katiba', ordering='discovered_at')
    def discovery_time(self, obj):
        return obj.discovered_at

    @admin.display(description='Previous and current values')
    def change_history(self, obj):
        sections = []
        for revision in revision_history(obj):
            if revision['initial']:
                rows = [('Initial capture', '—', revision['metadata'].get('title', ''))]
            else:
                rows = [(change['field'].replace('_', ' ').capitalize(),
                         change['previous'] if change['previous'] is not None else 'Not supplied',
                         change['current'] if change['current'] is not None else 'Not supplied')
                        for change in revision['changes']]
            table_rows = format_html_join('', '<tr><th>{}</th><td>{}</td><td>{}</td></tr>', rows)
            sections.append((revision['captured_at'], table_rows))
        return format_html_join('',
            '<section><h3>{}</h3><table><thead><tr><th>Field</th><th>Previous</th>'
            '<th>Current</th></tr></thead><tbody>{}</tbody></table></section>', sections) or 'No snapshots yet.'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'collection_status', 'last_attempt', 'last_success',
                    'next_check', 'failures', 'last_error')
    list_filter = ('enabled',)
    readonly_fields = ('slug', 'name', 'feed_url', 'collection_status', 'effective_interval',
                       'last_attempt', 'last_success', 'next_check', 'failures',
                       'last_error', 'etag', 'last_modified')
    fieldsets = (
        ('Collection status', {'fields': ('name', 'collection_status', 'last_attempt',
            'last_success', 'next_check', 'failures', 'last_error'),
            'description': 'The command checks only when due. Failures defer the next attempt; a scheduler must invoke the command to retry.'}),
        ('Configuration', {'fields': ('enabled', 'interval_minutes', 'effective_interval', 'feed_url', 'slug')}),
        ('HTTP cache', {'fields': ('etag', 'last_modified'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Collection status')
    def collection_status(self, obj):
        return source_health(obj).replace('_', ' ').capitalize()

    @admin.display(description='Effective interval (minutes)')
    def effective_interval(self, obj):
        return max(15, obj.interval_minutes)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EditorialEvent)
class EditorialEventAdmin(admin.ModelAdmin):
    list_display = ('lead', 'actor_name', 'action', 'created_at')
    readonly_fields = ('lead', 'actor', 'actor_name', 'action', 'changes', 'created_at')
    list_filter = ('action',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TopicRule)
class TopicRuleAdmin(admin.ModelAdmin):
    list_display = ('phrase', 'topic', 'enabled', 'created_by')
    readonly_fields = ('created_by', 'created_at')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.phrase = ' '.join(obj.phrase.casefold().split())
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(CollectionAlert)
class CollectionAlertAdmin(admin.ModelAdmin):
    list_display = ('source', 'kind', 'opened_at', 'resolved_at')
    readonly_fields = ('source', 'kind', 'message', 'opened_at', 'resolved_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

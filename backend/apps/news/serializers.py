"""Separate source-owned metadata from the small set of editor-writable fields."""
from collections.abc import Mapping
from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Lead, Source
from .presentation import source_health
from .source_catalog import source_context


class LeadSerializer(serializers.ModelSerializer):
    source_context = serializers.SerializerMethodField()

    def get_source_context(self, lead):
        return source_context(lead.source.slug)

    source_name = serializers.CharField(source='source.name', read_only=True)
    source_slug = serializers.CharField(source='source.slug', read_only=True)
    assigned_author = serializers.CharField(source='assigned_to.username', read_only=True, default=None)

    class Meta:
        model = Lead
        fields = ('id', 'source_name', 'source_slug', 'external_id', 'title', 'original_url',
                  'published_at', 'source_updated_at', 'discovered_at', 'last_seen',
                  'fingerprint', 'has_update', 'status', 'topic_matches', 'source_context', 'tags', 'notes', 'brief',
                  'assigned_to', 'assigned_author', 'needs_reassignment', 'relevance', 'relevance_reason', 'story_group')
        read_only_fields = fields


class StrictInputSerializer(serializers.Serializer):
    """Reject unknown fields so clients cannot silently attempt metadata edits."""
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({'non_field_errors': ['Expected a JSON object.']})
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: 'This field cannot be edited here.' for key in unknown})
        return super().to_internal_value(data)


class EditorialSerializer(StrictInputSerializer):
    tags = serializers.CharField(max_length=500, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    brief = serializers.CharField(required=False, allow_blank=True)


class AssignmentSerializer(StrictInputSerializer):
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.filter(groups__name='Author', is_active=True).distinct())
    brief = serializers.CharField(allow_blank=False)

    def validate_assigned_to(self, user):
        from apps.users.access import eligible_author
        if not eligible_author(user):
            raise serializers.ValidationError('Author no longer has assignment access.')
        return user


class ReviewSerializer(StrictInputSerializer):
    # Prevent acknowledging a newer revision that the editor has not seen yet.
    fingerprint = serializers.CharField(max_length=64)


class SourceSerializer(serializers.ModelSerializer):
    context = serializers.SerializerMethodField()

    def get_context(self, source):
        return source_context(source.slug)

    health = serializers.SerializerMethodField()
    effective_interval_minutes = serializers.SerializerMethodField()

    class Meta:
        model = Source
        fields = ('id', 'slug', 'name', 'feed_url', 'enabled', 'health', 'context',
                  'effective_interval_minutes', 'last_attempt', 'last_success',
                  'next_check', 'failures', 'last_error')
        read_only_fields = fields

    def get_health(self, source):
        return source_health(source)

    def get_effective_interval_minutes(self, source):
        return max(15, source.interval_minutes)


class FeedbackSerializer(StrictInputSerializer):
    relevance = serializers.ChoiceField(choices=['relevant', 'irrelevant', 'unreviewed'])
    relevance_reason = serializers.CharField(allow_blank=False)


class GroupSerializer(StrictInputSerializer):
    other = serializers.PrimaryKeyRelatedField(queryset=Lead.objects.all())


class AuthorAssignmentSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source='source.name', read_only=True)

    class Meta:
        model = Lead
        fields = ('id', 'title', 'source_name', 'original_url', 'published_at', 'brief', 'status')
        read_only_fields = fields


class AuthorChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ('id', 'username', 'first_name', 'last_name')
        read_only_fields = fields


class SourceConfigSerializer(StrictInputSerializer):
    enabled = serializers.BooleanField(required=False)
    interval_minutes = serializers.IntegerField(min_value=15, max_value=1440, required=False)


from .models import TopicRule


class TopicRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopicRule
        fields = ('id', 'phrase', 'topic', 'enabled', 'rationale', 'created_by', 'created_at')
        read_only_fields = ('created_by', 'created_at')

    def validate_phrase(self, value):
        value = ' '.join(value.casefold().split())
        if len(value) < 4:
            raise serializers.ValidationError('Use a specific phrase of at least four characters.')
        matches = TopicRule.objects.filter(phrase__iexact=value)
        if self.instance:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            raise serializers.ValidationError('This phrase already exists.')
        return value

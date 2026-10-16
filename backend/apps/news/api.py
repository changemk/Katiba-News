"""Editor inbox API. Collection remains a management command, never a GET side effect."""
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from rest_framework import filters, mixins, serializers, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from apps.users.authentication import VersionedJWTAuthentication
from apps.users.access import has_news_permission, eligible_author
from .models import Lead, Source
from .presentation import revision_history
from .editorial import audit, snapshot, group_leads
from .related import suggested_coverage
from .serializers import (AssignmentSerializer, EditorialSerializer, LeadSerializer,
                          ReviewSerializer, SourceSerializer, StrictInputSerializer, FeedbackSerializer, GroupSerializer)


class NewsActionPermission(BasePermission):
    def has_permission(self, request, view):
        if view.action is None:
            return bool(request.user.is_authenticated and request.user.is_active)
        required = view.action_permissions.get(view.action)
        return bool(required and has_news_permission(request.user, required))


class InboxPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class EditorViewSet(viewsets.GenericViewSet):
    authentication_classes = (VersionedJWTAuthentication, SessionAuthentication)
    permission_classes = (NewsActionPermission,)
    action_permissions = {}
    pagination_class = InboxPagination


class LeadViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, EditorViewSet):
    action_permissions = {
        'list': 'view_lead', 'retrieve': 'view_lead', 'revisions': 'view_lead',
        'history': 'view_lead', 'related': 'view_lead',
        'partial_update': 'review_lead', 'select': 'review_lead', 'dismiss': 'review_lead',
        'feedback': 'review_lead', 'acknowledge': 'review_lead',
        'assign': 'assign_lead', 'group': 'group_lead', 'ungroup': 'group_lead',
    }
    serializer_class = LeadSerializer
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ('title', 'original_url', 'tags', 'notes')
    ordering_fields = ('discovered_at', 'published_at', 'title')
    ordering = ('-discovered_at', '-pk')

    def get_queryset(self):
        qs = Lead.objects.select_related('source', 'assigned_to')
        # Filters apply to the inbox, not to detail/action lookups.
        if self.action != 'list':
            return qs
        params = self.request.query_params
        if params.get('needs_reassignment') == 'true':
            ids = [lead.pk for lead in qs.filter(status='assigned') if lead.needs_reassignment]
            qs = qs.filter(pk__in=ids)
        if 'constitutional' in params:
            if params['constitutional'] not in ('true', 'false'):
                raise serializers.ValidationError({'constitutional': 'Use true or false.'})
            qs = qs.exclude(topic_matches=[]) if params['constitutional'] == 'true' else qs.filter(topic_matches=[])
        if 'relevance' in params:
            if params['relevance'] not in ('unreviewed', 'relevant', 'irrelevant'):
                raise serializers.ValidationError({'relevance': 'Unknown relevance decision.'})
            qs = qs.filter(relevance=params['relevance'])
        if 'status' in params:
            if params['status'] not in Lead.Status.values:
                raise serializers.ValidationError({'status': 'Unknown lead status.'})
            qs = qs.filter(status=params['status'])
        if 'source' in params:
            qs = qs.filter(source__slug=params['source'])
        if 'has_update' in params:
            if params['has_update'] not in ('true', 'false'):
                raise serializers.ValidationError({'has_update': 'Use true or false.'})
            qs = qs.filter(has_update=params['has_update'] == 'true')
        return qs

    def partial_update(self, request, pk=None):
        return self.edit(request, EditorialSerializer)

    def edit(self, request, input_class, status=None, reviewed=False):
        """Validate and apply one editorial action without rewriting source fields."""
        payload = input_class(data=request.data)
        payload.is_valid(raise_exception=True)
        with transaction.atomic():
            lead = self.get_object()
            # Row locks serialize actions on databases that support them; SQLite
            # does not provide select_for_update row locks. Save only editorial
            # columns so collector-owned metadata cannot be overwritten.
            lead = Lead.objects.select_for_update().get(pk=lead.pk)
            before = snapshot(lead)
            values = dict(payload.validated_data)
            if reviewed:
                expected = values.pop('fingerprint')
                # Conditional UPDATE also protects against a collector update
                # arriving between the editor's read and acknowledgement.
                changed = Lead.objects.filter(pk=lead.pk, fingerprint=expected).update(has_update=False)
                if not changed:
                    return Response({'detail': 'Lead changed; reload its history before acknowledging.'}, status=409)
            else:
                if status:
                    values['status'] = status
                if status in ('selected', 'dismissed'):
                    values['assigned_to'] = None
                for field, value in values.items():
                    setattr(lead, field, value)
                try:
                    lead.full_clean()
                except ModelValidationError as exc:
                    raise serializers.ValidationError(exc.message_dict)
                if values:
                    lead.save(update_fields=list(values))
            lead.refresh_from_db()
            audit(lead, request.user, self.action, before)
        return Response(LeadSerializer(lead).data)

    @action(detail=True, methods=['post'])
    def select(self, request, pk=None):
        return self.edit(request, StrictInputSerializer, status='selected')

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        return self.edit(request, StrictInputSerializer, status='dismissed')

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        return self.edit(request, AssignmentSerializer, status='assigned')

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        return self.edit(request, ReviewSerializer, reviewed=True)

    @action(detail=True, methods=['post'])
    def feedback(self, request, pk=None):
        return self.edit(request, FeedbackSerializer)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        events = self.get_object().editorial_events.values('id', 'actor_name', 'action', 'changes', 'created_at')
        return self.get_paginated_response(self.paginate_queryset(events))

    @action(detail=True, methods=['get'])
    def related(self, request, pk=None):
        lead = self.get_object()
        confirmed = Lead.objects.filter(story_group_id=lead.story_group_id).exclude(pk=lead.pk) if lead.story_group_id else Lead.objects.none()
        return Response({'confirmed': LeadSerializer(confirmed, many=True).data,
                         'suggestions': [{'lead': LeadSerializer(item['lead']).data, 'reason': item['reason']}
                                         for item in suggested_coverage(lead)]})

    @action(detail=True, methods=['post'])
    def group(self, request, pk=None):
        payload = GroupSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            group = group_leads(self.get_object(), payload.validated_data['other'], request.user)
        except ModelValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return Response({'story_group': group.pk})

    @action(detail=True, methods=['post'])
    def ungroup(self, request, pk=None):
        payload = StrictInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        with transaction.atomic():
            lead = Lead.objects.select_for_update().get(pk=self.get_object().pk)
            before = snapshot(lead)
            lead.story_group = None
            lead.save(update_fields=['story_group'])
            audit(lead, request.user, 'ungroup', before)
        return Response(LeadSerializer(lead).data)

    @action(detail=True, methods=['get'])
    def revisions(self, request, pk=None):
        history = revision_history(self.get_object())
        return self.get_paginated_response(self.paginate_queryset(history))


class SourceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, EditorViewSet):
    action_permissions = {'list': 'view_source', 'retrieve': 'view_source', 'partial_update': 'change_source'}
    queryset = Source.objects.order_by('name', 'pk')
    serializer_class = SourceSerializer


    def partial_update(self, request, pk=None):
        from .serializers import SourceConfigSerializer
        payload = SourceConfigSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        source = self.get_object()
        for key, value in payload.validated_data.items():
            setattr(source, key, value)
        source.save(update_fields=list(payload.validated_data))
        return Response(self.get_serializer(source).data)


class AuthorAssignmentPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and eligible_author(request.user))


class AssignmentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, EditorViewSet):
    """Authors receive only their active assignments and source/brief fields."""
    permission_classes = (AuthorAssignmentPermission,)

    def get_serializer_class(self):
        from .serializers import AuthorAssignmentSerializer
        return AuthorAssignmentSerializer

    def get_queryset(self):
        return Lead.objects.filter(assigned_to=self.request.user, status='assigned').select_related('source').order_by('-discovered_at', '-pk')


class AuthorViewSet(mixins.ListModelMixin, EditorViewSet):
    action_permissions = {'list': 'assign_lead'}

    def get_queryset(self):
        from django.contrib.auth import get_user_model
        users = get_user_model().objects.filter(is_active=True, groups__name='Author').distinct()
        return users.filter(pk__in=[user.pk for user in users if eligible_author(user)]).order_by('username')

    def get_serializer_class(self):
        from .serializers import AuthorChoiceSerializer
        return AuthorChoiceSerializer


class TopicRuleViewSet(viewsets.ModelViewSet, EditorViewSet):
    action_permissions = {'list': 'view_topicrule', 'retrieve': 'view_topicrule',
        'create': 'add_topicrule', 'update': 'change_topicrule',
        'partial_update': 'change_topicrule', 'destroy': 'delete_topicrule'}

    def get_queryset(self):
        from .models import TopicRule
        return TopicRule.objects.order_by('phrase')

    def get_serializer_class(self):
        from .serializers import TopicRuleSerializer
        return TopicRuleSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

from datetime import timedelta
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from apps.users.models import User
from django.contrib.auth.models import Group


def grant(user, group):
    user.groups.add(Group.objects.get(name=group))
    return user

from .models import Lead, LeadRevision, Source
from .sourcing import FEED_URL, collect_source, parse_feed, persist_items

URL = 'https://new.kenyalaw.org/akn/ke/judgment/kehc/2026/1/eng@2026-01-01'


def feed(title='Example v Republic', date='<published>2026-01-01T00:00:00Z</published>'):
    return (f'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>{URL}</id>'
            f'<title>{title}</title><link href="{URL}"/>{date}</entry></feed>').encode()


class SourcingTests(TestCase):
    def setUp(self):
        self.source = Source.objects.create(slug='kenya-law', name='Kenya Law', feed_url=FEED_URL)

    def test_repeat_and_update_preserve_editor_work(self):
        now = timezone.now()
        self.assertEqual(persist_items(self.source, parse_feed(feed()), now)['new'], 1)
        lead = Lead.objects.get()
        lead.status = 'dismissed'
        lead.notes = 'Already covered'
        lead.tags = 'courts'
        lead.save()
        self.assertEqual(persist_items(self.source, parse_feed(feed()), now)['unchanged'], 1)
        self.assertEqual(persist_items(self.source, parse_feed(feed('Corrected title')), now)['updated'], 1)
        lead.refresh_from_db()
        self.assertEqual((lead.status, lead.notes, lead.tags), ('dismissed', 'Already covered', 'courts'))
        self.assertTrue(lead.has_update)
        self.assertEqual(LeadRevision.objects.count(), 2)
        self.assertEqual(lead.revisions.order_by('pk').first().metadata['title'], 'Example v Republic')

    def test_missing_date_stays_unknown(self):
        self.assertIsNone(parse_feed(feed(date=''))[0]['published_at'])

    def test_bad_feed_rejected(self):
        for data in [b'<html/>', feed(date='<published>not-a-date</published>'),
                     feed().replace(b'new.kenyalaw.org', b'example.com'),
                     b'<!DOCTYPE feed [<!ENTITY x SYSTEM "file:///etc/passwd">]><feed>&x;</feed>']:
            with self.subTest(data=data), self.assertRaises(Exception):
                parse_feed(data)

    @patch('apps.news.sourcing.time.sleep')
    @patch('apps.news.sourcing.fetch')
    def test_collection_and_due_guard(self, fetch, sleep):
        fetch.side_effect = [(b'User-agent: *\nAllow: /\nCrawl-delay: 5', {}), (feed(), {'ETag': 'v1'})]
        self.assertEqual(collect_source()['new'], 1)
        self.assertIn('skipped', collect_source())
        self.assertEqual(fetch.call_count, 2)
        sleep.assert_called_once_with(5)
        self.source.refresh_from_db()
        self.assertEqual(self.source.etag, 'v1')
        self.assertIsNotNone(self.source.last_success)

    @patch('apps.news.sourcing.time.sleep')
    @patch('apps.news.sourcing.fetch')
    def test_conditional_response(self, fetch, sleep):
        self.source.etag = 'v1'
        self.source.save()
        fetch.side_effect = [(b'User-agent: *\nAllow: /', {}), (None, {})]
        self.assertTrue(collect_source()['not_modified'])
        self.assertEqual(fetch.call_args.args[1]['If-None-Match'], 'v1')
        self.assertEqual(Lead.objects.count(), 0)

    @patch('apps.news.sourcing.fetch', side_effect=OSError('Unavailable'))
    def test_failure_records_backoff(self, fetch):
        with self.assertRaises(OSError):
            collect_source()
        self.source.refresh_from_db()
        self.assertEqual(self.source.failures, 1)
        self.assertEqual(self.source.last_error, 'Unavailable')
        self.assertIsNone(self.source.last_success)
        self.assertGreater(self.source.next_check, timezone.now() + timedelta(minutes=119))

    @patch('apps.news.sourcing.fetch', return_value=(b'User-agent: *\nDisallow: /', {}))
    def test_robots_denial_stops_feed_request(self, fetch):
        with self.assertRaises(ValueError):
            collect_source()
        self.assertEqual(fetch.call_count, 1)

    def test_assignment_requires_author_and_brief(self):
        persist_items(self.source, parse_feed(feed()), timezone.now())
        lead = Lead.objects.get()
        lead.status = 'assigned'
        with self.assertRaises(ValidationError):
            lead.full_clean()
        lead.assigned_to = User.objects.create_user(username='reporter', email='reporter@example.org', role='AUTHOR')
        grant(lead.assigned_to, 'Author')
        lead.brief = 'Verify the ruling and report its implications.'
        lead.full_clean()

    def test_admin_inbox_and_history_render(self):
        persist_items(self.source, parse_feed(feed()), timezone.now())
        admin = User.objects.create_superuser(username='editor-admin', email='admin@example.org', password='test-only-password')
        self.client.force_login(admin)
        response = self.client.get('/admin/news/lead/')
        self.assertContains(response, 'Example v Republic')
        response = self.client.get(f'/admin/news/lead/{Lead.objects.get().pk}/change/')
        self.assertContains(response, URL)


class InboxAPITests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()
        self.editor = User.objects.create_user(username='editor', email='editor@example.org', role='EDITOR', is_staff=True)
        self.author = User.objects.create_user(username='author', email='author@example.org', role='AUTHOR')
        grant(self.editor, 'Editor')
        grant(self.author, 'Author')
        self.source = Source.objects.create(slug='kenya-law', name='Kenya Law', feed_url=FEED_URL)
        persist_items(self.source, parse_feed(feed()), timezone.now())
        self.lead = Lead.objects.get()
        self.url = f'/api/news/leads/{self.lead.pk}/'

    def test_only_approved_editors_and_superusers_have_access(self):
        endpoints = ['/api/news/leads/', '/api/news/sources/', self.url + 'revisions/']
        for endpoint in endpoints:
            self.assertEqual(self.client.get(endpoint).status_code, 401)
        for role, staff in [('READER', False), ('AUTHOR', True), ('EDITOR', False)]:
            user = User.objects.create_user(username=f'{role}{staff}', email=f'{role}{staff}@example.org', role=role, is_staff=staff)
            self.client.force_authenticate(user)
            for endpoint in endpoints:
                self.assertEqual(self.client.get(endpoint).status_code, 403)
            for action in ['select', 'dismiss', 'assign', 'acknowledge']:
                self.assertEqual(self.client.post(self.url + action + '/', {}, format='json').status_code, 403)
            self.assertEqual(self.client.patch(self.url, {'notes': 'Denied'}, format='json').status_code, 403)
        self.client.force_authenticate(self.editor)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.editor.is_superuser = True
        self.editor.role = 'READER'
        self.editor.save()
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_search_filters_and_pagination(self):
        self.client.force_authenticate(self.editor)
        response = self.client.get('/api/news/leads/?status=new&source=kenya-law&has_update=false&search=Republic&page_size=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(self.client.get('/api/news/leads/?status=invalid').status_code, 400)
        self.assertEqual(self.client.get('/api/news/leads/?has_update=invalid').status_code, 400)
        self.assertEqual(self.client.get('/api/news/leads/?search=missing').data['count'], 0)

    def test_editor_actions_and_assignment_validation(self):
        self.client.force_authenticate(self.editor)
        self.assertEqual(self.client.post(self.url + 'select/', {}, format='json').data['status'], 'selected')
        self.assertEqual(self.client.post(self.url + 'assign/', {'assigned_to': self.author.pk, 'brief': ''}, format='json').status_code, 400)
        self.assertEqual(self.client.post(self.url + 'assign/', {'assigned_to': self.editor.pk, 'brief': 'Report'}, format='json').status_code, 400)
        result = self.client.post(self.url + 'assign/', {'assigned_to': self.author.pk, 'brief': 'Verify and report'}, format='json')
        self.assertEqual(result.data['status'], 'assigned')
        self.assertEqual(self.client.patch(self.url, {'brief': ''}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.url, {'title': 'Overwrite'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.url, {'notes': 'Editor note', 'tags': 'courts'}, format='json').status_code, 200)
        result = self.client.post(self.url + 'dismiss/', {}, format='json')
        self.assertEqual(result.data['status'], 'dismissed')
        self.assertIsNone(result.data['assigned_to'])
        self.assertEqual(result.data['notes'], 'Editor note')
        self.assertEqual(self.client.delete(self.url).status_code, 405)
        self.assertEqual(self.client.post('/api/news/leads/', {}, format='json').status_code, 405)

    def test_revision_comparison_and_stale_acknowledgement(self):
        self.client.force_authenticate(self.editor)
        old_fingerprint = self.lead.fingerprint
        persist_items(self.source, parse_feed(feed('Corrected title')), timezone.now())
        result = self.client.get(self.url + 'revisions/')
        self.assertEqual(result.data['count'], 2)
        self.assertEqual(result.data['results'][0]['changes'], [
            {'field': 'title', 'previous': 'Example v Republic', 'current': 'Corrected title'}])
        self.assertEqual(self.client.post(self.url + 'acknowledge/', {'fingerprint': old_fingerprint}, format='json').status_code, 409)
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.has_update)
        result = self.client.post(self.url + 'acknowledge/', {'fingerprint': self.lead.fingerprint}, format='json')
        self.assertFalse(result.data['has_update'])

    def test_source_health_and_read_only_endpoint(self):
        self.client.force_authenticate(self.editor)
        self.source.failures = 2
        self.source.next_check = timezone.now() + timedelta(hours=2)
        self.source.last_error = 'Connection timed out'
        self.source.save()
        result = self.client.get('/api/news/sources/').data['results'][0]
        self.assertEqual(result['health'], 'retry_scheduled')
        self.assertEqual(result['last_error'], 'Connection timed out')
        self.assertEqual(self.client.patch(f'/api/news/sources/{self.source.pk}/', {'enabled': False}, format='json').status_code, 403)

    def test_admin_history_escapes_source_text(self):
        persist_items(self.source, parse_feed(feed('&lt;script&gt;alert(1)&lt;/script&gt;')), timezone.now())
        self.editor.is_superuser = True
        self.editor.save()
        self.client.force_login(self.editor)
        response = self.client.get(f'/admin/news/lead/{self.lead.pk}/change/')
        self.assertContains(response, 'Previous')
        self.assertContains(response, 'Example v Republic')
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_jwt_access_and_session_csrf(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.editor)
        self.assertEqual(client.get('/api/news/leads/').status_code, 200)
        self.assertEqual(client.post(self.url + 'select/', {}, format='json').status_code, 403)
        client.logout()
        from apps.users.authentication import LoginSerializer
        token = LoginSerializer.get_token(self.editor).access_token
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(client.post(self.url + 'select/', {}, format='json').status_code, 200)
        self.assertEqual(client.patch(self.url, [], format='json').status_code, 400)


class MultiSourceTests(TestCase):
    def rss(self, title='Public participation in constitutional reform', link='https://katibainstitute.org/story/'):
        return f'''<rss version="2.0"><channel><title>KI</title><item>
            <title>{title}</title><link>{link}</link><guid>story-1</guid>
            <pubDate>Fri, 18 Sep 2026 10:53:02 +0000</pubDate>
            <description>Update from the publisher.</description>
            </item></channel></rss>'''.encode()

    def test_rss_metadata_and_topic_evidence(self):
        item = parse_feed(self.rss(), 'katiba-institute')[0]
        self.assertEqual(item['published_at'], '2026-09-18T10:53:02+00:00')
        self.assertIn({'topic': 'participation', 'term': 'public participation', 'field': 'title'}, item['topic_matches'])
        self.assertNotIn('description', item)
        with self.assertRaises(ValueError):
            parse_feed(self.rss(link='https://evil.example/story/'), 'katiba-institute')
        with self.assertRaises(ValueError):
            parse_feed(self.rss(link='https://judiciary.go.ke/story/'), 'katiba-institute')

    def test_topic_matching_boundaries_and_swahili(self):
        from .topics import topic_matches
        self.assertEqual(topic_matches(title='Government court sports day'), [])
        self.assertEqual(topic_matches(title='Constitutionally styled sportswear'), [])
        self.assertTrue(topic_matches(title='Katiba na ugatuzi'))
        self.assertTrue(topic_matches(summary='<p>Access to <b>information</b></p>'))

    @patch('apps.news.sourcing.time.sleep')
    @patch('apps.news.sourcing.fetch')
    def test_filter_new_items_but_track_updates_to_existing_leads(self, fetch, sleep):
        robots = (b'User-agent: *\nAllow: /', {})
        fetch.side_effect = [robots, (self.rss('Office sports day'), {})]
        self.assertEqual(collect_source('katiba-institute')['filtered_out'], 1)
        self.assertEqual(Lead.objects.count(), 0)
        Source.objects.update(next_check=None)
        fetch.side_effect = [robots, (self.rss(), {})]
        self.assertEqual(collect_source('katiba-institute')['new'], 1)
        Lead.objects.update(status='selected', notes='Keep this lead')
        Source.objects.update(next_check=None)
        fetch.side_effect = [robots, (self.rss('New title without keywords'), {})]
        self.assertEqual(collect_source('katiba-institute')['updated'], 1)
        lead = Lead.objects.get()
        self.assertEqual(lead.notes, 'Keep this lead')
        self.assertEqual(lead.status, 'selected')
        self.assertEqual(lead.topic_matches, [])
        self.assertEqual(lead.revisions.count(), 2)

    def test_reclassification_does_not_create_source_revision(self):
        source = Source.objects.create(slug='katiba-institute', name='KI', feed_url='https://katibainstitute.org/feed/')
        item = parse_feed(self.rss(), 'katiba-institute')[0]
        persist_items(source, [item], timezone.now())
        item['topic_matches'] = []
        result = persist_items(source, [item], timezone.now())
        self.assertEqual(result['unchanged'], 1)
        self.assertEqual(LeadRevision.objects.count(), 1)

    @patch('apps.news.management.commands.collect_sources.collect_source')
    def test_all_sources_continue_after_failure(self, collect):
        from io import StringIO
        from django.core.management import call_command, CommandError
        collect.side_effect = [OSError('offline'), {'new': 2}, {'new': 1}]
        output = StringIO()
        with self.assertRaises(CommandError):
            call_command('collect_sources', source='all', stdout=output)
        self.assertEqual(collect.call_count, 3)
        self.assertIn('"source": "judiciary"', output.getvalue())

    def test_constitution_filter_and_source_context(self):
        from rest_framework.test import APIClient
        source = Source.objects.create(slug='katiba-institute', name='KI', feed_url='https://katibainstitute.org/feed/')
        persist_items(source, parse_feed(self.rss(), 'katiba-institute'), timezone.now())
        editor = User.objects.create_user(username='constitutional-editor', email='constitutional@example.org', role='EDITOR', is_staff=True)
        client = APIClient()
        grant(editor, 'Editor')
        client.force_authenticate(editor)
        result = client.get('/api/news/leads/?constitutional=true')
        self.assertEqual(result.data['count'], 1)
        self.assertIn('Civil society', result.data['results'][0]['source_context']['kind'])
        self.assertEqual(client.get('/api/news/leads/?constitutional=false').data['count'], 0)
        self.assertEqual(client.get('/api/news/leads/?constitutional=wrong').status_code, 400)


class NewsroomWorkflowTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        from .models import EditorialEvent, StoryGroup, TopicRule, CollectionAlert
        self.client = APIClient()
        self.editor = User.objects.create_user(username='desk-editor', email='desk@example.org', role='EDITOR', is_staff=True)
        grant(self.editor, 'Editor')
        self.source = Source.objects.create(slug='kenya-law', name='Kenya Law', feed_url=FEED_URL)
        persist_items(self.source, parse_feed(feed('Public participation in constitutional reform')), timezone.now())
        self.lead = Lead.objects.get()
        self.url = f'/api/news/leads/{self.lead.pk}/'
        self.client.force_authenticate(self.editor)

    def test_feedback_and_editorial_actions_are_audited(self):
        from .models import EditorialEvent
        response = self.client.post(self.url + 'feedback/', {'relevance': 'irrelevant', 'relevance_reason': 'Title match, but no Kenyan constitutional issue.'}, format='json')
        self.assertEqual(response.status_code, 200)
        event = EditorialEvent.objects.get()
        self.assertEqual(event.actor, self.editor)
        self.assertEqual(event.changes['relevance']['previous'], 'unreviewed')
        self.assertEqual(event.changes['relevance']['current'], 'irrelevant')
        self.client.post(self.url + 'select/', {}, format='json')
        self.client.patch(self.url, {'notes': 'Research before assigning'}, format='json')
        history = self.client.get(self.url + 'history/').data
        self.assertEqual(history['count'], 3)
        self.assertEqual(history['results'][0]['actor_name'], 'desk-editor')
        persist_items(self.source, parse_feed(feed('Updated constitutional reform title')), timezone.now())
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.relevance, 'irrelevant')
        self.assertEqual(EditorialEvent.objects.count(), 3)

    def test_failed_action_does_not_create_an_audit_event(self):
        from .models import EditorialEvent
        response = self.client.post(self.url + 'feedback/', {'relevance': 'relevant', 'relevance_reason': ''}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EditorialEvent.objects.exists())

    def test_related_suggestions_require_confirmation_and_keep_attribution(self):
        from .models import EditorialEvent, StoryGroup
        other_source = Source.objects.create(slug='judiciary', name='Judiciary', feed_url='https://judiciary.go.ke/feed/')
        other = Lead.objects.create(source=other_source, external_id='other', title=self.lead.title,
            original_url='https://judiciary.go.ke/story/', fingerprint='x', last_seen=timezone.now())
        result = self.client.get(self.url + 'related/').data
        self.assertEqual(result['suggestions'][0]['lead']['id'], other.pk)
        self.assertFalse(StoryGroup.objects.exists())
        self.assertEqual(self.client.post(self.url + 'group/', {'other': other.pk}, format='json').status_code, 200)
        other.refresh_from_db()
        self.lead.refresh_from_db()
        self.assertEqual(other.story_group_id, self.lead.story_group_id)
        self.assertNotEqual(other.source_id, self.lead.source_id)
        self.assertEqual(EditorialEvent.objects.filter(action='group').count(), 2)
        self.assertEqual(self.client.get(self.url + 'related/').data['confirmed'][0]['id'], other.pk)
        self.assertEqual(self.client.post(self.url + 'ungroup/', {}, format='json').status_code, 200)
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.story_group_id)
        self.assertEqual(self.client.post(self.url + 'group/', {'other': self.lead.pk}, format='json').status_code, 400)

    def test_custom_dashboard_removed_but_api_and_admin_remain(self):
        browser = self.client_class()
        browser.force_login(self.editor)
        self.assertEqual(browser.get('/newsroom/').status_code, 404)
        self.assertEqual(browser.get(f'/newsroom/leads/{self.lead.pk}/').status_code, 404)
        self.assertEqual(browser.post('/newsroom/rules/add/', {}).status_code, 404)
        self.assertEqual(browser.post('/newsroom/rules/1/toggle/', {}).status_code, 404)
        self.assertEqual(self.client.get('/api/news/leads/').status_code, 200)
        self.assertEqual(browser.get('/admin/').status_code, 200)

    def test_admin_edits_create_same_editorial_history(self):
        from django.contrib.admin.sites import site
        from django.test import RequestFactory
        from types import SimpleNamespace
        from .models import EditorialEvent
        request = RequestFactory().post('/admin/')
        request.user = self.editor
        self.lead.notes = 'Edited in admin'
        site._registry[Lead].save_model(request, self.lead, SimpleNamespace(changed_data=['notes']), True)
        self.assertEqual(EditorialEvent.objects.get().action, 'admin_edit')

    def test_alert_deduplication_recovery_and_stale_scheduler(self):
        from .models import CollectionAlert, SchedulerState
        from .monitoring import refresh_alerts, scheduler_status
        self.source.failures = 3
        self.source.last_error = 'Unavailable'
        self.source.next_check = timezone.now() - timedelta(minutes=11)
        self.source.save()
        refresh_alerts()
        refresh_alerts()
        self.assertEqual(CollectionAlert.objects.filter(resolved_at=None).count(), 2)
        self.source.failures = 0
        self.source.next_check = timezone.now() + timedelta(hours=1)
        self.source.save()
        refresh_alerts()
        self.assertFalse(CollectionAlert.objects.filter(resolved_at=None).exists())
        SchedulerState.objects.create(name='sources', last_started=timezone.now() - timedelta(minutes=11))
        self.assertIn('Missed heartbeat', scheduler_status())

    @patch('apps.news.management.commands.source_tick.call_command', side_effect=RuntimeError('Feed failed'))
    def test_failed_scheduler_tick_records_heartbeat(self, collect):
        from django.core.management import call_command
        from .models import SchedulerState
        with self.assertRaises(RuntimeError):
            call_command('source_tick')
        state = SchedulerState.objects.get(pk='sources')
        self.assertIsNotNone(state.last_finished)
        self.assertEqual(state.last_error, 'Feed failed')

    @patch('apps.news.sourcing.time.sleep')
    @patch('apps.news.sourcing.fetch')
    def test_editor_rule_recovers_previously_unmatched_feed_item(self, fetch, sleep):
        from .models import TopicRule
        TopicRule.objects.create(phrase='cabinet composition', topic='equality', rationale='Gender representation cases', created_by=self.editor)
        data = MultiSourceTests().rss('Cabinet composition challenged')
        fetch.side_effect = [(b'User-agent: *\nAllow: /', {}), (data, {})]
        result = collect_source('katiba-institute')
        self.assertEqual(result['new'], 1)
        self.assertEqual(Lead.objects.get(source__slug='katiba-institute').topic_matches[0]['field'], 'title (editor rule)')


class GroupAccessTests(TestCase):
    setUp = InboxAPITests.setUp

    def test_group_grants_work_without_staff_and_legacy_role_grants_nothing(self):
        self.editor.role = 'READER'
        self.editor.is_staff = False
        self.editor.save()
        self.client.force_authenticate(self.editor)
        self.assertEqual(self.client.get('/api/news/leads/').status_code, 200)
        self.editor.groups.clear()
        self.editor.role = 'EDITOR'
        self.editor.is_staff = True
        self.editor.save()
        self.assertEqual(self.client.get('/api/news/leads/').status_code, 403)

    def test_author_can_only_read_own_assignment_and_loses_access_on_removal(self):
        self.lead.assigned_to = self.author
        self.lead.status = 'assigned'
        self.lead.brief = 'Investigate this ruling'
        self.lead.save()
        other = Lead.objects.create(source=self.source, external_id='other', title='Other lead',
            original_url=URL, last_seen=timezone.now(), fingerprint='x')
        self.client.force_authenticate(self.author)
        result = self.client.get('/api/news/assignments/')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['count'], 1)
        self.assertNotIn('notes', result.data['results'][0])
        self.assertEqual(self.client.get(f'/api/news/assignments/{other.pk}/').status_code, 404)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.patch(f'/api/news/assignments/{self.lead.pk}/', {'brief':'Change'}, format='json').status_code, 405)
        self.author.groups.clear()
        self.assertEqual(self.client.get('/api/news/assignments/').status_code, 403)
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.needs_reassignment)
        self.client.force_authenticate(self.editor)
        self.assertEqual(self.client.get('/api/news/leads/?needs_reassignment=true').data['count'], 1)
        self.assertEqual(self.client.get('/api/news/authors/').data['count'], 0)

    def test_action_grants_and_news_administrator_configuration(self):
        from django.contrib.auth.models import Permission
        user = User.objects.create_user(username='reviewer', email='reviewer@example.org')
        user.user_permissions.add(Permission.objects.get(content_type__app_label='news', codename='review_lead'))
        self.client.force_authenticate(user)
        self.assertEqual(self.client.post(self.url+'select/', {}, format='json').status_code, 200)
        self.assertEqual(self.client.post(self.url+'assign/', {'assigned_to':self.author.pk,'brief':'Report'}, format='json').status_code, 403)
        self.assertEqual(self.client.post(self.url+'group/', {'other':self.lead.pk}, format='json').status_code, 403)
        grant(user, 'News Administrator')
        result = self.client.patch(f'/api/news/sources/{self.source.pk}/', {'interval_minutes':30}, format='json')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.client.patch(f'/api/news/sources/{self.source.pk}/', {'feed_url':'https://evil.example/'}, format='json').status_code, 400)
        result = self.client.post('/api/news/topic-rules/', {'phrase':'Cabinet composition', 'topic':'equality', 'rationale':'Gender representation'}, format='json')
        self.assertEqual(result.status_code, 201)
        self.client.force_authenticate(self.editor)
        self.assertEqual(self.client.get('/api/news/topic-rules/').status_code, 403)

    def test_removing_author_permission_or_deactivating_flags_assignment(self):
        from django.contrib.auth.models import Permission
        self.lead.assigned_to = self.author
        self.lead.status = 'assigned'
        self.lead.brief = 'Report'
        self.lead.save()
        self.assertFalse(self.lead.needs_reassignment)
        group = Group.objects.get(name='Author')
        group.permissions.remove(Permission.objects.get(content_type__app_label='news', codename='view_assigned_lead'))
        self.assertTrue(self.lead.needs_reassignment)
        self.client.force_authenticate(self.author)
        self.assertEqual(self.client.get('/api/news/assignments/').status_code, 403)

    def test_legacy_migration_preserves_only_previously_approved_editor_access(self):
        import importlib
        from django.apps import apps
        from django.db import connection
        from types import SimpleNamespace
        approved = User.objects.create_user(username='approved-old', email='approved@example.org', role='EDITOR', is_staff=True)
        unapproved = User.objects.create_user(username='unapproved-old', email='unapproved@example.org', role='EDITOR')
        migration = importlib.import_module('apps.news.migrations.0005_news_groups')
        migration.create_groups(apps, SimpleNamespace(connection=connection))
        self.assertTrue(approved.groups.filter(name='Editor').exists())
        self.assertFalse(unapproved.groups.filter(name='Editor').exists())
        self.assertTrue(unapproved.groups.filter(name='Reader').exists())

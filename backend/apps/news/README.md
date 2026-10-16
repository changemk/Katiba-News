# Katiba constitutional news sourcing API

Collect publisher-attributed leads, review constitutional relevance, link coverage,
and hand reporting briefs to human authors. Collection never writes or publishes
articles. The implementation lives in `apps/news`; identity, groups and authentication are managed in `apps/users`.

## Start locally

From the repository root, use Python 3.12 and a persistent virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/apps/news/requirements.txt
export DJANGO_SETTINGS_MODULE=apps.news.sourcing_settings
python backend/manage.py migrate
python backend/manage.py createsuperuser  # first setup only
python backend/manage.py collect_sources --source all
python backend/manage.py runserver
```

Use http://127.0.0.1:8000/api/news/ for frontend integration.
Django admin remains at http://127.0.0.1:8000/admin/ for backend administration.
The custom `/newsroom/` pages have been removed; the frontend developer owns the UI.
The optional sourcing settings preserve existing admin/user URLs and use
`backend/sourcing.sqlite3`. Set `KATIBA_SOURCING_DB` to choose a different SQLite
path. Existing migrations must be applied before using the API.
This configuration inherits development settings; production hosting needs its
own deployment configuration and database/concurrency review.

## Editorial workflow through the API

The frontend can build these flows using the endpoints below.

1. Search/filter leads by source, constitutional hints, status, relevance or updates.
2. Open a lead and read the original publisher link. Publication and discovery
   times are shown separately, alongside publisher perspective and topic hints.
3. Record relevant/irrelevant/needs-review feedback with a reason. Feedback is
   independent of source metadata and of the selected/dismissed workflow.
4. Select or dismiss a lead. Assigning requires an active Author and a brief.
5. Review related-coverage suggestions, then explicitly confirm a link. Each lead
   retains its publisher identity and original URL. You can manually link a lead
   by ID or unlink it. Different existing groups are not silently merged.
6. Compare source snapshots side by side. Acknowledge the fingerprint you reviewed;
   a stale acknowledgement returns 409 so newly arrived changes are not hidden.
7. Inspect editorial history for actor, time, action, and before/after values.

Admin and API edits create editorial events transactionally. No-op or rejected
changes do not create events. Events are read-only in app interfaces, though a
privileged database operator can still modify them. History begins with this
feature: old activity is not reconstructed. Source changes remain a separate
revision history; editorial notes and decisions survive collection updates.

### Feedback and matching rules

The API exposes relevance decisions and automatic hints for frontend reporting.
Matching rules can be managed through the permission-protected API or Django admin: add a specific phrase,
topic and rationale from reviewed feedback, then enable/disable the rule. Rules extend title matching on
subsequent non-304 feed responses; they do not automatically train a classifier,
rewrite past feedback, or change source fingerprints. Default rules in `topics.py`
continue to match titles, feed summaries and RSS categories. Summaries are used
transiently and are not retained; article bodies are not fetched.

Keyword hints can be wrong or miss relevant stories. New Katiba Institute and
Judiciary entries require a match; existing leads are always tracked even if they
lose their keywords. Kenya Law retains broader judgment coverage because titles
may not reveal constitutional issues. Older leads get hints when seen again, not
through an automatic archive backfill. Editor feedback applies only to collected
leads; missed entries outside the rolling feeds require a separate discovery process.

Related suggestions compare exact case citations or at least three meaningful
shared title words with Jaccard similarity >= 0.45, across different publishers.
They scan the most recent 500 other-source leads and show at most ten suggestions.
This is a review aid, not an exhaustive case index or a claim that two stories
concern the same event.

## Sources and access

Verified on 2026-09-19:

| CLI slug | Feed | Perspective |
| --- | --- | --- |
| `kenya-law` | https://new.kenyalaw.org/feeds/judgments.xml | Official judgments; primary legal material |
| `katiba-institute` | https://katibainstitute.org/feed/ | Constitutional civil society; may be a litigant |
| `judiciary` | https://judiciary.go.ke/feed/ | Official institutional announcements |

The new RSS feeds returned ten items each during verification. A feed's rolling
window is not a full archive or a completeness guarantee. Preserve separate
attribution and corroborate legal outcomes against the actual decision.

Kenya Law advertises its Atom feed and prohibits scraping/bulk downloading in
https://new.kenyalaw.org/terms-of-use/. Its robots file disallows `/api/` and sets a
five-second general crawl delay. Judiciary advertises RSS on its homepage. Its
linked https://judiciary.go.ke/terms-and-conditions/ concerns the e-filing system,
not a blanket licence to republish news. Katiba Institute describes its constitutional
mandate at https://katibainstitute.org/. Both new robots files permitted the feeds
when checked. Titles, links and dates are stored with attribution, not full articles.

`source_catalog.py` pins reviewed publisher hosts/feed URLs and records perspectives.
Each due run rechecks robots, honours the delay, requests a single bounded feed
response with conditional HTTP headers, and refuses redirects for manual review.
No crawling, pagination or document/PDF downloading occurs. Missing timestamps
remain unknown. A source Atom ID/RSS GUID identifies an item, falling back to its
URL; identity is scoped to the source. New/changed metadata creates a snapshot;
unchanged metadata is skipped. Body-only changes cannot be detected.

## Scheduled collection and alerts

`collect_sources --source all` checks each source independently and prints one JSON
result per source. A failure does not stop other sources; any failure makes the
command exit nonzero. Omitting `--source` preserves the Kenya Law default.
Sources default to hourly checks with a minimum 15-minute interval. Failure backoff
doubles the interval, capped at 24 hours. Disabled/not-due sources make no requests.
An atomic interval reservation limits overlapping runs; crashed reservations expire.

`source_tick` runs all sources, records start/finish/error heartbeat, and refreshes
persistent local alerts. Three consecutive failures open an alert; a check more
than ten minutes overdue opens a missed-check alert. Success/disable resolves the
appropriate alert. Alerts are deduplicated while open and can be inspected in
Django admin. With the custom UI removed, alert refresh runs during collection
and scheduled ticks. Check `systemctl --user status katiba-sourcing.timer` and
service logs to detect a stopped timer independently. The backend
`scheduler_status()` helper evaluates heartbeat age; alerts and heartbeat do not yet have dedicated API endpoints. No outbound notifications
are sent.

Generate and inspect user-systemd units using a persistent virtualenv (not `/tmp`):

```bash
.venv/bin/python backend/manage.py write_source_timer \
  --settings=apps.news.sourcing_settings --output-dir backend/apps/news/deploy
cat backend/apps/news/deploy/katiba-sourcing.service
cat backend/apps/news/deploy/katiba-sourcing.timer
```

The generated units contain absolute paths to this checkout, interpreter and
SQLite database. Regenerate them if those locations change. Install using absolute
paths (replace `/path/to/Katiba-News`):

```bash
systemctl --user link /path/to/Katiba-News/backend/apps/news/deploy/katiba-sourcing.service
systemctl --user link /path/to/Katiba-News/backend/apps/news/deploy/katiba-sourcing.timer
systemctl --user daemon-reload
systemctl --user enable --now katiba-sourcing.timer
systemctl --user start katiba-sourcing.service
systemctl --user list-timers katiba-sourcing.timer
journalctl --user -u katiba-sourcing.service -n 30
```

The timer checks every five minutes; source intervals determine actual HTTP requests.
`Persistent=true` catches a missed calendar tick when the user service manager starts.
User services depend on the user manager staying active: continuous operation after
logout requires host configuration such as lingering, or a production system service.
These units do not alter that host policy. To pause automatic collection:

```bash
systemctl --user disable --now katiba-sourcing.timer
```

## Access and API

Public signup creates Reader group members. The legacy `role` field is retained
for compatibility but grants no access. News access uses Django permissions;
`is_staff` controls Django admin login only. A non-staff Editor can use the API.
Only superusers can change accounts, memberships or Group permissions in admin.

| Group | Permissions |
| --- | --- |
| Reader | No internal sourcing access |
| Author | Read own assigned leads and brief through `/api/news/assignments/` |
| Editor | View/review leads, assign active Authors, group coverage, read source status |
| News Administrator | Editor permissions plus source settings and matching-rule management |

Every API action checks its permission. Direct Django permission grants are also
supported. Author assignment additionally requires active Author membership and
`news.view_assigned_lead`. Removing membership/that permission or deactivating the
account immediately denies assignment access. Existing assignments are preserved
and expose `needs_reassignment=true`; filter `/api/news/leads/?needs_reassignment=true`
to find them. The admin lead list shows the same flag.

Migration `0005_news_groups` creates group grants and maps legacy users once:
AUTHOR → Author; EDITOR with staff approval → Editor; others → Reader.
It does not silently approve staff-less legacy Editors or remove existing grants.
Subsequent role-field edits have no authorization effect. Use group membership.

Browser API requests can use the admin session with CSRF for writes. JWT clients
use access tokens from `/api/users/login/`, refresh them at `/api/users/token/refresh/`,
and revoke all account JWT sessions at `/api/users/logout/`. Older JWTs without the
new session-version claim require a fresh login. See `apps/users/README.md` for
password recovery and request examples.

| Method | Path | Purpose / body |
| --- | --- | --- |
| GET | `/api/news/leads/` | Paginated inbox |
| GET | `/api/news/leads/<id>/` | Lead detail |
| PATCH | `/api/news/leads/<id>/` | `notes`, `tags`, and/or `brief` |
| POST | `/api/news/leads/<id>/select/` | `{}`; clear active assignment |
| POST | `/api/news/leads/<id>/dismiss/` | `{}`; clear active assignment |
| POST | `/api/news/leads/<id>/assign/` | `{"assigned_to": 3, "brief": "Verify and report."}` |
| POST | `/api/news/leads/<id>/feedback/` | `{"relevance": "relevant", "relevance_reason": "Concerns Article 10."}` |
| POST | `/api/news/leads/<id>/acknowledge/` | `{"fingerprint": "<reviewed fingerprint>"}` |
| GET | `/api/news/leads/<id>/revisions/` | Paginated source snapshots/comparisons |
| GET | `/api/news/leads/<id>/history/` | Paginated editorial events |
| GET | `/api/news/leads/<id>/related/` | Confirmed coverage and suggestions |
| POST | `/api/news/leads/<id>/group/` | `{"other": 42}`; confirm grouping |
| POST | `/api/news/leads/<id>/ungroup/` | `{}`; unlink this lead |
| GET | `/api/news/sources/` | Paginated collection status |
| GET | `/api/news/sources/<id>/` | Source status |
| PATCH | `/api/news/sources/<id>/` | `enabled`, `interval_minutes` (15–1440); requires `change_source` |
| GET | `/api/news/authors/` | Eligible authors; requires `assign_lead` |
| GET | `/api/news/assignments/` | Author's own active assignments |
| GET | `/api/news/assignments/<id>/` | Author's own assignment; others return 404 |
| GET/POST | `/api/news/topic-rules/` | View/create matching rules with corresponding model permission |
| GET/PATCH/PUT/DELETE | `/api/news/topic-rules/<id>/` | Manage a rule with corresponding model permission |

Inbox query parameters: `search`, `source` (slug), `status`, `relevance`,
`constitutional=true|false` (automatic hints), `has_update=true|false`, `ordering`
(`discovered_at`, `published_at`, `title`; prefix `-` for descending), `page`,
`page_size` (default 25, maximum 100). Responses contain `count`, `next`, `previous`,
`results`. Relevance values: `unreviewed`, `relevant`, `irrelevant`. Unknown editable
fields are rejected. API requests never trigger collection or send messages.

## Verification and code map

```bash
.venv/bin/python backend/manage.py test apps.news.tests apps.users.tests --settings=apps.news.sourcing_settings
.venv/bin/python backend/manage.py check --settings=apps.news.sourcing_settings
```

- `sourcing.py`, `source_catalog.py`, `topics.py`: HTTP, parsing, upserts, matching.
- `editorial.py`, `related.py`: audit snapshots and confirmed/suggested coverage.
- `api.py`, `serializers.py`: permissions, validation and editorial actions.
- `monitoring.py`, `management/commands/`: local alerts, heartbeat and timer setup.
- `models.py`, `migrations/`: persisted sources, leads, histories, rules and alerts.
- `admin.py`, `presentation.py`: admin review and shared history formatting.

Comments explain ownership boundaries, validation, scheduling and relevance limits.
Further sources need independent identity/access verification. Automated writing,
automatic publishing, outbound alerts and full-archive ingestion remain outside scope.

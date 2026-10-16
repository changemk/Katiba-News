# User identity and newsroom authorization

Django Groups and Permissions are the shared authority for `users` and `news`.
`access.py` checks current database grants without retaining stale permission
caches; tokens carry identity/session version, not permanent permission claims.
The legacy `role` column is read-only in admin and no longer authorizes anything.
It remains for staged migration compatibility and will require a separate schema
migration when existing consumers no longer need it.

## Groups and administration

Run migrations with the sourcing settings to install the news permissions/groups:

```bash
.venv/bin/python backend/manage.py migrate --settings=apps.news.sourcing_settings
```

- **Reader:** public signup; no internal sourcing permissions.
- **Author:** `news.view_assigned_lead`; read only their assigned leads and briefs.
- **Editor:** `view_lead`, `review_lead`, `assign_lead`, `group_lead`; read source
  status and source/editorial history.
- **News Administrator:** Editor grants plus source configuration, matching-rule
  management and viewing collection alerts.
- **Superuser:** account/group/privilege administration and all permissions.

A superuser uses Django admin's User → Groups field to grant membership. Staff
status is needed only for admin access, not API access. Groups are additive; an
Editor can also be an Author. Direct Django permissions are supported for more
specific duties. A newsroom administrator cannot manage users or grant privileges.

The one-time migration maps legacy Authors to Author and legacy Editors with
`is_staff=True` to Editor. Unapproved legacy Editors are mapped to Reader. Existing
memberships/direct permissions are not removed. Review any historic custom grants
separately. The data migration's reverse operation deliberately does not delete
memberships or permissions added by administrators since migration.

Assignment eligibility requires active Author membership plus the assigned-lead
permission. Membership/permission removal or deactivation immediately revokes
access and makes outstanding assignments report `needs_reassignment`. This flag
is computed live, not a signal-maintained field that can become stale. The prior
author and brief remain available to editors for reassignment.

The general sourcing API remains inaccessible to Authors: use `/api/news/assignments/`
and `/api/news/assignments/<id>/`. These omit private editor notes/history and scope
queries by the current author. Editors obtain eligible authors at `/api/news/authors/`.

## Authentication endpoints

All bodies are JSON. Routes are under `/api/users/`.

| Method / endpoint | Body / result |
| --- | --- |
| POST `register/` | `username`, `email`, `password`, optional names; creates Reader membership |
| POST `login/` | `username`, `password`; returns `access` and `refresh` |
| POST `token/refresh/` | `refresh`; returns new access and rotated refresh, blacklisting the old refresh |
| POST `logout/` | Authenticated request; returns 204 and revokes **all JWT sessions** for the account |
| GET `me/` | Current identity, legacy role, authoritative group names and permissions |
| POST `password-reset/` | `email`; generic response regardless of account existence |
| POST `password-reset/confirm/` | `uid`, `token`, `password`; validates recovery and changes password |

Use `Authorization: Bearer <access>` for authenticated requests. Logout increments
`auth_version`, immediately invalidating all previously issued access and refresh
tokens. It is account-wide, not a single-device logout. Browser session logout clears
the current session if one exists; it does not promise deletion of every Django
admin session. Password resets change Django's session authentication hash and
increment JWT version. Tokens issued before versioned JWTs were introduced are
rejected: log in again after deployment.

Passwords are hashed and checked against configured Django validators, including
common/numeric passwords and similarity to the account. Recovery codes are
single-use after a successful reset, expire after one hour, and are never returned
by the request API. Disabled accounts cannot authenticate or recover passwords.
Recovery requests are limited to ten per hour per client IP using DRF's cache-based
throttle; deployed environments should use a shared cache and appropriate edge
abuse controls. This is not a distributed brute-force protection service.

**Development email delivery uses Django's console email backend.** Recovery
messages appear in the server's console; they are not sent to an external mailbox.
Configure a verified email backend before deploying recovery. The backend-only
message supplies an account reference (`uid`) and recovery code (`token`) for the
client to submit to the confirmation API. No password-reset UI was added.

## Tests

```bash
.venv/bin/python backend/manage.py test apps.users.tests apps.news.tests --settings=apps.news.sourcing_settings
```

Tests cover group migration, per-action grants, ownership, membership revocation,
assignment flagging, account/group admin restrictions, weak passwords, JWT
rotation/logout, inactive accounts and recovery-token replay.

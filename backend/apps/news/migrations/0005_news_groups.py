from django.db import migrations


def create_groups(apps, schema_editor):
    """Create explicit grants before post_migrate and map legacy roles once.

    Staff-less legacy Editors were not approved under the old access check, so
    they are not silently promoted. Existing direct permissions are untouched.
    """
    db = schema_editor.connection.alias
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    User = apps.get_model('users', 'User')
    grants = {
        'Author': {'lead': ['view_assigned_lead']},
        'Editor': {'lead': ['view_lead', 'review_lead', 'assign_lead', 'group_lead'],
                   'source': ['view_source'], 'leadrevision': ['view_leadrevision'],
                   'editorialevent': ['view_editorialevent']},
    }
    grants['Reader'] = {}
    grants['News Administrator'] = {**grants['Editor'],
        'source': ['view_source', 'change_source'],
        'topicrule': ['view_topicrule', 'add_topicrule', 'change_topicrule', 'delete_topicrule'],
        'collectionalert': ['view_collectionalert']}
    groups = {}
    for name, models in grants.items():
        group, _ = Group.objects.using(db).get_or_create(name=name)
        groups[name] = group
        for model, codes in models.items():
            content_type, _ = ContentType.objects.using(db).get_or_create(app_label='news', model=model)
            for code in codes:
                permission, _ = Permission.objects.using(db).get_or_create(content_type=content_type,
                    codename=code, defaults={'name': code.replace('_', ' ').capitalize()})
                group.permissions.add(permission)
    for user in User.objects.using(db).all().iterator():
        name = 'Author' if user.role == 'AUTHOR' else 'Editor' if user.role == 'EDITOR' and user.is_staff else 'Reader'
        user.groups.add(groups[name])


class Migration(migrations.Migration):
    dependencies = [
        ('news', '0004_alter_lead_options_alter_lead_assigned_to'),
        ('users', '0002_user_auth_version'),
    ]
    # Do not delete existing memberships/grants on rollback: that could revoke
    # subsequent administrator decisions. Legacy role column remains available.
    operations = [migrations.RunPython(create_groups, migrations.RunPython.noop)]

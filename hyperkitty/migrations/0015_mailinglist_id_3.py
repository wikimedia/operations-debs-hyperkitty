# -*- coding: utf-8 -*-
# flake8: noqa
import django
from django.db import migrations, models, connection


def hotpatch_schema_editor(apps, schema_editor):
    # Patch Django <= 1.8 because it does not know about type
    # conversion in PostgreSQL.
    if django.VERSION < (1, 9) and connection.vendor == "postgresql":
        schema_editor.sql_alter_column_type = \
            "ALTER COLUMN %(column)s TYPE %(type)s USING %(column)s::%(type)s"


class Migration(migrations.Migration):

    dependencies = [
        ('hyperkitty', '0014_mailinglist_id_2'),
    ]

    operations = [
        migrations.RunPython(hotpatch_schema_editor, hotpatch_schema_editor),
        # Restore the constraints on thread.mailinglist_id and
        # email.mailinglist_id
        migrations.AlterField(
            model_name='thread',
            name='mailinglist',
            field=models.ForeignKey(
                related_name='threads',
                to='hyperkitty.MailingList',
                on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='email',
            name='mailinglist',
            field=models.ForeignKey(
                related_name='emails',
                to='hyperkitty.MailingList',
                on_delete=models.CASCADE),
        ),
    ]

# -*- coding: utf-8 -*-
# flake8: noqa
import contextlib
from django.apps.registry import Apps
from django.db import migrations, models


class MailingListPrimaryKey(migrations.AlterField):

    def __init__(self):
        super(MailingListPrimaryKey, self).__init__(
            "mailinglist", "name", field=models.CharField(
                unique=True, max_length=254, serialize=True,
                auto_created=False)
            )

    def state_forwards(self, app_label, state):
        state.models[app_label, self.model_name_lower].fields.insert(0, (
            "id", models.AutoField(
                name="id", auto_created=True, primary_key=True, serialize=False,
                verbose_name='ID')))
        super(MailingListPrimaryKey, self).state_forwards(app_label, state)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        # See django.db.backends.sqlite3.schema:DatabaseSchemaEditor._remake_table()
        old_model = from_state.apps.get_model("hyperkitty", "MailingList")
        new_model = to_state.apps.get_model("hyperkitty", "MailingList")
        old_fields = [schema_editor.quote_name(f.column)
                      for f in old_model._meta.local_fields]
        body = {f.name: f for f in new_model._meta.local_fields}

        # Construct a new model for the new state
        meta_contents = {
            'app_label': old_model._meta.app_label,
            'db_table': old_model._meta.db_table,
            'apps': Apps(),
        }
        meta = type("Meta", tuple(), meta_contents)
        body['Meta'] = meta
        body['__module__'] = old_model.__module__

        temp_model = type(old_model._meta.object_name, old_model.__bases__, body)
        # We need to modify model._meta.db_table, but everything explodes
        # if the change isn't reversed before the end of this method. This
        # context manager helps us avoid that situation.
        @contextlib.contextmanager
        def altered_table_name(model, temporary_table_name):
            original_table_name = model._meta.db_table
            model._meta.db_table = temporary_table_name
            yield
            model._meta.db_table = original_table_name

        with altered_table_name(old_model, old_model._meta.db_table + "__old"):
            schema_editor.alter_db_table(
                old_model, temp_model._meta.db_table, old_model._meta.db_table)

            # Create a new table with the updated schema. We remove things
            # from the deferred SQL that match our table name, too
            schema_editor.deferred_sql = [
                x for x in schema_editor.deferred_sql
                if temp_model._meta.db_table not in x]
            schema_editor.create_model(temp_model)

            # Copy data from the old table into the new table
            schema_editor.execute(
                "INSERT INTO %s (%s) SELECT %s FROM %s ORDER BY name" % (
                schema_editor.quote_name(temp_model._meta.db_table),
                ', '.join(old_fields),
                ', '.join(old_fields),
                schema_editor.quote_name(old_model._meta.db_table),
            ))

            # Delete the old table
            schema_editor.delete_model(old_model)
        # Run deferred SQL on correct table
        for sql in schema_editor.deferred_sql:
            schema_editor.execute(sql)
        schema_editor.deferred_sql = []

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        from_model = from_state.apps.get_model(app_label, self.model_name)
        schema_editor.remove_field(from_model, from_model._meta.get_field("id"))
        super(MailingListPrimaryKey, self).database_forwards(
            app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):

    dependencies = [
        ('hyperkitty', '0012_thread_order_null'),
    ]

    operations = [
        # Drop the constraints on thread.mailinglist_id and email.mailinglist_id
        migrations.AlterField(
            model_name='thread',
            name='mailinglist',
            field=models.CharField(db_column="mailinglist_id", max_length=254),
        ),
        migrations.AlterField(
            model_name='email',
            name='mailinglist',
            field=models.CharField(db_column="mailinglist_id", max_length=254),
        ),
        # Rebuild the mailinglist table with the new primary key.
        MailingListPrimaryKey(),
    ]

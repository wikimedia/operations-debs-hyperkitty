# -*- coding: utf-8 -*-
# flake8: noqa

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hyperkitty', '0011_email_parent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='email',
            name='thread_order',
            field=models.IntegerField(db_index=True, null=True, blank=True),
        ),
    ]

# -*- coding: utf-8 -*-
# flake8: noqa

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hyperkitty', '0005_MailingList_list_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='thread',
            name='category',
            field=models.ForeignKey(related_name='threads', on_delete=django.db.models.deletion.SET_NULL, to='hyperkitty.ThreadCategory', null=True),
        ),
        migrations.AlterField(
            model_name='thread',
            name='starting_email',
            field=models.OneToOneField(related_name='started_thread', null=True, on_delete=django.db.models.deletion.SET_NULL, to='hyperkitty.Email'),
        ),
    ]

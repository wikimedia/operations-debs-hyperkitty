# -*- coding: utf-8 -*-
# flake8: noqa

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hyperkitty', '0010_email_sender_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='email',
            name='parent',
            field=models.ForeignKey(
                related_name='children',
                on_delete=django.db.models.deletion.DO_NOTHING,
                blank=True, to='hyperkitty.Email', null=True),
        ),
    ]

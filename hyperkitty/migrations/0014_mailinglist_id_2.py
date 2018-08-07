# -*- coding: utf-8 -*-

from django.db import migrations, connection


def update_thread_and_email(apps, schema_editor):
    """
    Update Thread & Email tables's mailinglist_id column to the new
    MailingList.id value.
    """
    # import sys
    # print(" Updating thread and email references. This will take a "
    #       "loooooong time, go get a coffee. ", end="")
    # sys.stdout.flush()
    # # This it the version using the models. It is slow.
    # MailingList = apps.get_model("hyperkitty", "MailingList")
    # Thread = apps.get_model("hyperkitty", "Thread")
    # Email = apps.get_model("hyperkitty", "Email")
    # mlists = dict([(ml.name, ml.id) for ml in MailingList.objects.all()])
    # for thread in Thread.objects.all():
    #     thread.mailinglist = mlists[thread.mailinglist]
    #     thread.save()
    # for email in Email.objects.all():
    #     email.mailinglist = mlists[email.mailinglist]
    #     email.save()
    # This is the version using only two queries. It is much faster.
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE hyperkitty_thread SET mailinglist_id = (
                SELECT id FROM hyperkitty_mailinglist
                WHERE name = hyperkitty_thread.mailinglist_id LIMIT 1
            )
            """)
        cursor.execute("""
            UPDATE hyperkitty_email SET mailinglist_id = (
                SELECT id FROM hyperkitty_mailinglist
                WHERE name = hyperkitty_email.mailinglist_id LIMIT 1
            )
            """)


def update_thread_and_email_reverse(apps, schema_editor):
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE hyperkitty_thread SET mailinglist_id = (
                SELECT name FROM hyperkitty_mailinglist
                WHERE id = hyperkitty_thread.mailinglist_id LIMIT 1
            )
            """)
        cursor.execute("""
            UPDATE hyperkitty_email SET mailinglist_id = (
                SELECT name FROM hyperkitty_mailinglist
                WHERE id = hyperkitty_email.mailinglist_id LIMIT 1
            )
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('hyperkitty', '0013_mailinglist_id_1'),
    ]

    operations = [
        migrations.RunPython(update_thread_and_email,
                             update_thread_and_email_reverse),
    ]

Setting up the databases
========================

The HyperKitty database is configured using the ``DATABASE`` setting in
Django's ``settings.py`` file, as usual. The database can be created with the
following command::

    django-admin migrate --pythonpath example_project --settings settings

HyperKitty also uses a fulltext search engine. Thanks to the Django-Haystack
library, the search engine backend is pluggable, refer to the Haystack
documentation on how to install and configure the fulltext search engine
backend.

HyperKitty's default configuration uses the `Whoosh`_ backend, so if you want
to use that you just need to install the ``Whoosh`` Python library.

.. _Whoosh: https://pythonhosted.org/Whoosh/


Importing the current archives
==============================

If you are currently running Mailman 2.1, you can run the ``hyperkitty_import``
management command to import existing archives into the mailman database. This
command will import the Mbox files: if you're installing HyperKitty on the
machine which hosted the previous version of Mailman, those files are available
locally and you can use them directly.

The command's syntax is::

    django-admin hyperkitty_import --pythonpath example_project --settings settings -l ADDRESS mbox_file [mbox_file ...]

where:

* ``ADDRESS`` is the fully-qualified list name (including the ``@`` sign and
  the domain name)
* The ``mbox_file`` arguments are the existing archives to import (in mbox
  format).

The archive mbox file for a list is usually available at the following
location::

    /var/lib/mailman/archives/private/LIST_NAME.mbox/LIST_NAME.mbox

If the previous archives aren't available locally, you need to download them
from your current Mailman 2.1 installation. The file is not web-accessible.

Before importing an archive mbox, it is a good idea to check its integrity
with the hyperkitty/contrib/check_hk_import script and with Mailman 2.1's
bin/cleanarch script.

After importing your existing archives, you must add them to the fulltext
search engine with the following command::

    django-admin update_index --pythonpath example_project --settings settings

Refer to `the command's documentation`_ for available switches.

.. _`the command's documentation`: http://django-haystack.readthedocs.org/en/latest/management_commands.html#update-index


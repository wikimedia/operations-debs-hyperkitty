================
News / Changelog
================


1.3.4
=====

(2021-02-02)

- Sync owners and moderators from Mailman Core for MailingList. (Fixes #302)
- Implemented a new ``HYPERKITTY_JOBS_UPDATE_INDEX_LOCK_LIFE`` setting to set
  the lock lifetime for the ``update_and_clean_index`` job.  (Closes #300)
- Implemented a new ``HYPERKITTY_ALLOW_WEB_POSTING`` that allows disabling the
  web posting feature. (Closes #264)
- Add the ability to disable Gravatar using ``HYPERKITTY_ENABLE_GRAVATAR``
  settings. (Closes #303)
- Replaced deprecated ``ugettext`` functions with ``gettext``. (Closes #310)
- Fix export of Email message where the ``In-Reply-To`` header doesn't include
  the ``<>`` brackets. (Closes #331)
- We now catch a few more exceptions in ``hyperkitty_import`` when getting
  messages from a mbox. (Closes #313 and #314)
- Added a new contrib/check_hk_import script to check mboxes before running
  hyperkitty_import.
- We now ignore a ``ValueError`` in ``hyperkitty_import`` when trying to
  replace a ``Subject:`` header. (Closes #317)
- ``hyperkitty_import`` now includes the mbox name in error messages when
  importing multiple mboxes. (Closes #318)
- `` at `` is now only replaced with ``@`` in ``From:`` header values when
  necessary and not unconditionally. (Closes #320)
- The wildcard notation for any host ``'*'`` is now supported into
  ``MAILMAN_ARCHVER_FROM`` to disable Hyperkitty clients IP checking.
- Join the searchbar and search button  like it was before bootstrap 4 
  migration. (See !301)
- Use the umd builds for popper.js instead of the regular ones. (See !309)
- Exceptions thrown by smtplib in sending replies are now caught and give an
  appropriate error message.  (Closes #309)


1.3.3
=====

(2020-06-01)

- Allow ``SHOW_INACTIVE_LISTS_DEFAULT`` setting to be configurable. (Closes #276)
- Fix a bug where the user couldn't chose the address to send reply or new post
  as. (Closes #288)
- Improve the Django admin command reference from hyperkitty_import.
  (Closes #281)
- Fix ``FILTER_VHOST`` to work with web hosts other than the email host.
  (Closes #254)
- Fixed a bug where ``export`` can fail if certain headers are wrapped.
  (Closes #292)
- Fixed ``hyperkitty_import`` to allow odd line endings in a folded message
  subject.  (Closes #280)
- Fixed a bug that could throw an ``IndexError`` when exporting messages.
  (Closes #293)
- Use ``errors='replace'`` when encoding attachments.  (Closes #294)

1.3.2
=====

(2020-01-12)

- Remove support for Django 1.11. (Closes #273)
- Skip ``Thread.DoesNotExist`` exception when raised within
  ``rebuild_thread_cache_votes``. (Closes #245)
- Send 400 status code for ``ValueError`` when archiving. (Closes #271)
- Fix a bug where exception for elasticsearch backend would not be caught. (Closes #263)

1.3.1
=====

(2019-12-08)

- Add support to delete mailing list. (Closes #3)
- Fix a bug where messages with attachments would skip adding the body when
  exporting the email. (Closes #252)
- Fix a bug where exporting mbox with messages that have attachments saved
  to disk would raise exception and return a corrupt mbox. (Closes #258)
- Fix a bug where downloaded attachments are returned as a memoryview object
  instead of bytes and hence fail to download. (Closes #247)
- Fix a bug where migrations would fail with exceptions on postgresl. (Closes
  #266)
- Add support for Django 3.0.
- Add support for Python 3.8 with Django 2.2.


1.3.0
=====
(2019-09-04)

- Unread messages now have a blue envelope icon, instead of a gray one before to
  to make them more visible.
- Quoted text in emails have different visual background to improve readability.
- Quoted text is now visually quoted to 3 levels of replies with different visual
  background to improve readability.
- Add a new "All Threads" button in MailingList overview page to point to all the
  the threads in reverse date order. This should give a continuous list of threads.
- Fixes a bug where "All Threads" button leads to 500 page if there aren't any
  threads. (Closes #230)
- Add support for Django 2.2.
- Fix a bug where bad Date header could cause ``hyperkitty_import`` to exit with
  ``TypeError`` due to bad date type.
- Change the Overview page to remove the List of months from left side bar and
  convert different thread categories into tabs.
- Replace unmaintained ``lockfile`` dependency with ``flufl.lock``.
- Remove ``SingletonAsync`` implementation of ``AsyncTask`` and use the upstream
  version for better maintenance.
- Run update_index job hourly by default instead of minutely for performance
  reasons of whoosh.
- Email body now preserves leading whitespaces on lines and wraps around line
  boundary. (Closes #239)
- Do not indent replies on small screens. (Closes #224)
- Add a keyboard shortcut ``?`` to bring up list of keyboard shortcuts.
	(Closes #240)

1.2.2
=====
(2019-02-22)

- ``paintstore`` is no longer a dependency of Hyperkitty. This change requires
  that people change their ``settings.py`` and remove ``paintstore`` from
  ``INSTALLED_APPS``. (See #72)
- Folded Message-ID headers will no longer break threading.  (#216)
- MailingList descriptions are no longer a required field. This makes HyperKity
  more aligned with Core. (Closes #211)


1.2.1
=====
(2018-08-30)

- Several message defects that would cause ``hyperkitty_import`` to abort will
  now just cause the message to be skipped and allow importing to continue.
  (#183)
- If an imported message has no Date: header, ``hyperkitty_import`` will now
  look for Resent-Date: and the unixfrom date before archiving the message
  with the current date.  (#184)
- Add support for Django 2.1. Hyperkitty now supports Django 1.11-2.1 (#193)


1.2.0
=====
(2018-07-10)

- Handle email attachments returned by Scrubber as bytes or as strings with
  no specified encoding. (#171)
- Remove robotx.txt from Hyperkitty. It wasn't working correctly anyway.
  If you still need it, serve it from the webserver directly. (#176)
- Add the possibility to store attachments on the filesystem, using the
  ``HYPERKITTY_ATTACHMENT_FOLDER`` config variable.
- If a message in the mbox passed to ``hyperkitty_import`` is missing a
  ``Message-ID``, a generated one will be added. (#180)
- There is a new management command ``update_index_one_list`` to update the
  search index for a single list. (#175)


1.1.4
=====
(2017-10-09)

- Use an auto-incrementing integer for the MailingLists's id.
  **WARNING**: this migration will take a very long time (hours!) if you have
  a lot of emails in your database.
- Protect a couple tasks against thread and email deletion
- Improve performance in the cache rebuilding async task
- Drop the ``mailman2_download`` command. (#148)
- Adapt to the newest mailmanclient version (3.1.1).
- Handle the case when a moderated list is opened and there are pending
  subscriptions. (#152)
- Protect export_mbox against malformed URLs. (#153)


1.1.1
=====
(2017-08-04)

- Fix the Javascript in the overview page
- Make two Django commands compatible with Django >= 1.10
- Fix sorting in the MailingList's cache value
- Don't show emails before they have been analyzed
- Fix slowdown with PostgreSQL on some overview queries


1.1.0
=====
(2017-05-26)

- Add an async task system, check out the installation documentation to run the necessary commands.
- Support Django < 1.11 (support for 1.11 will arrive soon, only a dependency is not compatible).
- Switch to the Allauth login library
- Performance optimizations.
- Better REST API.
- Better handling of email sender names.
- Improve graphic design.


1.0.3
=====
(2015-11-15)

- Switch from LESS to Sass
- Many graphical improvements
- The SSLRedirect middleware is now optional
- Add an "Export to mbox" feature
- Allow choosing the email a reply or a new message will be sent as


0.9.6
=====
(2015-03-16)

* Adapt to the port of Mailman to Python3
* Merge KittyStore into HyperKitty
* Split off the Mailman archiver Plugin in its own module: mailman-hyperkitty
* Compatibility with Django 1.7


0.1.7
=====
(2014-01-30)

Many significant changes, mostly on:
* The caching system
* The user page
* The front page
* The list overview page


0.1.5
=====
(2013-05-18)

Here are the significant changes since 0.1.4:

* Merge and compress static files (CSS and Javascript)
* Django 1.5 compatibility
* Fixed REST API
* Improved RPM packaging
* Auto-subscribe the user to the list when they reply online
* New login providers: generic OpenID and Fedora
* Improved page loading on long threads: the replies are loaded asynchronously
* Replies are dynamically inserted in the thread view


0.1.4
=====
(2013-02-19)

Here are the significant changes:

* Beginning of RPM packaging
* Improved documentation
* Voting and favoriting is more dynamic (no page reload)
* Better emails display (text is wrapped)
* Replies are sorted by thread
* New logo
* DB schema migration with South
* General style update (Boostream, fluid layout)


0.1 (alpha)
===========
(2012-11-22)

Initial release of HyperKitty.

* login using django user account / browserid / google openid / yahoo openid
* use Twitter Bootstrap for stylesheets
* show basic list info and metrics
* show basic user profile
* Add tags to message threads

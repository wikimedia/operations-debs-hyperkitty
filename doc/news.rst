================
News / Changelog
================


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

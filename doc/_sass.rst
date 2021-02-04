You will also need to install the `Sass`_ CSS processor using your package
manager or the project's installation documentation. You can either use the
dart-sass version (`dartsass`_) or the C/C++ version, called `libsass`_
(the binary is ``sassc``). The configuration file in
``example_project/settings.py`` defaults to the ``sassc`` version, but you
just have to edit the ``COMPRESS_PRECOMPILERS`` mapping to switch to the
dart-sass implementation, whose binary is called ``sass`` and which doesn't
recognize the short form of the ``-t/--style`` option.

We no longer recommend ruby-sass as there have been compatibility issues
with recent versions.

Recent Debian and Ubuntu have a ``sassc`` package, which you can install with::

    sudo apt-get install sassc

.. _Sass: http://sass-lang.com
.. _libsass: http://sass-lang.com/libsass
.. _dartsass: https://sass-lang.com/dart-sass


You will also need to install the `Sass`_ CSS processor using your package
manager or the project's installation documentation. You can either use the
default Ruby implementation or the C/C++ version, called `libsass`_ (the binary
is ``sassc``). The configuration file in ``hyperkitty_standalone/settings.py``
defaults to the ``sassc`` version, but you just have to edit the
``COMPRESS_PRECOMPILERS`` mapping to switch to the Ruby implementation, whoose
binary is called ``sass``.

.. _Sass: http://sass-lang.com
.. _libsass: http://sass-lang.com/libsass


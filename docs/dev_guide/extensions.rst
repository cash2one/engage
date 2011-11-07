.._extensions:

Extensions
===========

Extension File Layout
--------------------------
An extension is a directory hierarchy. The top-level directory is the name of the extension (e.g. gfwebsite for the extension named "gfwebsite"). The top directory can contain four subdirectories: metadata, drivers, tests, and packages. When an extension is installed into an Engage distribution, these directories and their contents will be copied into the distribution as follows:

 * metadata => engage/metadata/<extension_name>
 * drivers => engage/python_pkg/engage/drivers/<extension_name>
 * tests => engage/python_pkg/engage/tests/<extension_name>
 * sw_packages => engage/sw_packages (packages are just added to the existing set)

If a sub-directory is not present in the extension, no attempt will be made to copy that directory into the distribution. The remaining directories will be copied as normal.

The top-level directory of an extension should contain a file named "version.txt". This file includes the version number of the extension.

Installing an Extension
------------------------
An extension is installed by the utility ``add_extension.py``, which is available directly under the engage directory (like bootstrap.py). This utility takes as its argument the location of an extension. The extension is installed into the distribution home containing the add_extension.py file. Note that this must be done before running the bootstrap of a deployment home.

If you have already installed an extension in your Engage distribution, you can replace it with a
later version by including the ``--update`` option on the command line of ``add_extension,py``.

Upon installation of an extension, the Python file  engage/python_pkg/engage/extensions.py
is updated with the name and version number of the extension.

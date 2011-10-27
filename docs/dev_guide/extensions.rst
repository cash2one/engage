Extensions
=================

Extension File Layout
--------------------------
An extension is a directory hierarchy. The top-level directory is the name of the extension (e.g. gfwebsite for the extension named "gfwebsite"). The top directory can contain four subdirectories: metadata, drivers, tests, and packages. When an extension is installed into an Engage distribution, these directories and their contents will be copied into the distribution as follows:

 * metadata => engage/metadata/<extension_name>
 * drivers => engage/python_pkg/engage/drivers/<extension_name>
 * tests => engage/python_pkg/engage/tests/<extension_name>
 * packages => engage/sw_packages/<extension_name>

If a sub-directory is not present in the extension, no attempt will be made to copy that directory into the distribution. The remaining directories will be copied as normal.

The top-level directory of an extension should contain a file named "version.txt". This file includes the version number of the extension.

Installing an Extension
------------------------
An extension is installed by the utility add_extension.py, which would be added directly under the engage directory (like bootstrap.py). This utility takes as its argument the location of an extension. The extension is installed into the distribution home containing the add_extension.py file. Note that this must be done before running the bootstrap of a deployment home. No changes need to be made to the bootstrap process - all the files will end up in the right place after bootstrapping.

A file extensions.json will be created under metadata when the first extension is installed in the distribution home. This file will contain a list of installed extensions and their version numbers.

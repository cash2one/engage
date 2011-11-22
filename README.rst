=======
Engage
=======

Engage is an open source platform for deploying and managing
applications, either on your own servers or in the public cloud.
It automates server provisioning, application installation,
configuration, and upgrades.

How Engage Works
=================
Engage works off a simple JSON file, called an *install spec*, that
lists the components you want installed, along with any non-default
configuration parameters. The Engage *deployer* expands this list to
include any required dependencies and computes the configuration
values for each component. This expanded specification is used to
drive the installation, configuration, and startup of your stack.

Engage also provides *installers*, which are simple command-line utilities to 
install a given pre-defined application stack.  Installers have been
created for Django and (basic) Java Web Applications (WAR files). You
can also create an installer for your own application stack.

For both the deployer and installer, the metadata from a deployment is saved on the
target system and
then used to support additional actions including upgrades, backups, and uninstall.

Engage is extensible. You can add individual components by writing
*resource definitions*, metadata describing a component's
configuration and dependencies, and *drivers*, Python classes which
implement the actions for a component (install, start, stop, backup, etc.).

Current Status
--------------
See RELEASE_NOTES.rst for a listing of the currently supported applications
and drivers. Notice of release updates is posted to twitter at http://twitter.com/#!/EngagePlatform.


Installation
===============
Supported Operating Systems
---------------------------
Engage has been tested on the following platforms:
 * MacOSX 10.5 and 10.6
 * Ubuntu Linux 9.10 and 10.04

Requirements
------------
In order to build engage, you need to have the following software pre-installed:

 * The GNU g++ compiler
 * Python 2.6.x or 2.7.x
 * ocaml (http://caml.inria.fr/)
 * zlib header files
 * The following Python packages:

   - virtualenv (http://pypi.python.org/pypi/virtualenv)
   - setuptools (http://pypi.python.org/pypi/setuptools)
   - pycrypto (http://pypi.python.org/pypi/pycrypto)

The following software is only required in some situations:

 * Certain application components on MacOSX require macports
   (http://www.macports.org/).

Building Engage
---------------
From the top level directory of the engage source distribution, type
``make all``. This will build the configuration engine (written in OCaml and
C++) and download some required packages from the internet.

Installing an Application with Engage
--------------------------------------
This section is just an overview, for more details, see the
`Engage Users' Guide <http://beta.genforma.com/engage_users_guide/index.html>`_.

To install an application, you must first create a *deployment home*. This
is a directory under which Engage and most of the application's components
will be installed [1]_. This is done by running the bootstrap.py Python script
in the top level Engage directory. It takes one argument, the name of the
directory to use as a deployment home. This directory will be created, if
necessary.

Django appliations must first be packaged with an command line utility
available at http://pypi.python.org/pypi/engage-django-sdk. This utility
validates the layout and settings of your application and captures some
metadata used in deployment.

Finally, run the Engage installer, which is at
``<deployment home>/engage/bin/install``, where ``<deployment_home>`` is the
directory that you gave to the bootstrap.py script. The installer has one
required argument, the name of the application you wish to install.

.. [1] Components which use a system-wide package manager (apt or macports) will be installed globally. Examples include Apache and MySQL.


Documentation
=================
The following additional documentation is available:
 * The *Engage User's Guide* describes how to run Engage to deploy
   applications. It is available online at
   http://beta.genforma.com/engage_users_guide/index.html. It is also
   included in source form in the Engage distribution at docs/users_guide. See below
   for instuctions on how to build a local copy.
 * The *Engage Architecture Guide* describes the design of Engage and
   documents the representation used for software component
   metadata. This guide is available in the Engage distributation at
   ``docs/Engage_Architecture_Guide.pdf``.
                                                                                         
 * The *Engage Django SDK Reference Manual* describes how to package Django
   applications for Engage. It is available online at
   http://beta.genforma.com/sdk_refman/index.html. It is also available in
   source form with the engage-django-sdk.

Building the User's Guide
----------------------------------------------
The User's Guide is generated from text files using `Sphinx <http://sphinx.pocoo.org>`_, a
Python-based documentation tool. If you wish to build a local copy of the User's Guide, do the following:

 1. Install Sphinx from http://pypi.python.org/pypi/Sphinx/1.0.7. Alternatively, you can use the Python ``easy_install`` utility (e.g. ``easy_install Sphinx``).
 2. From the top level directory of the Engage source distribution, run ``make all``
 3. The User's Guide will be created in the directory ``docs/users_guide/_build/html``. The main page for the guide is at ``docs/users_guide/_build/html/index.html``.


Notice
=========
The Engage software distribution is copyright 2010, 2011 by the genForma
Corporation. It is made available under the `Apache V2.0 license <http://www.apache.org/licenses/LICENSE-2.0>`_.


Authors
===========
The following people contributed to this software:
 * Jay Doane (jay at almery dot com)
 * Jeff Fischer (jeffrey dot fischer at genforma dot com)
 * Rupak Majumdar (rupak at mpi-sws dot org)


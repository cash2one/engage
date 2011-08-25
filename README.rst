=======
Engage
=======

Engage is an open source platform for deploying and managing
applications, either on your own servers or in the public cloud.
It automates server provisioning, application installation,
configuration, and upgrades.

How Engage Works
=================
Engage provides *installers*, which are simple command-line utilities to 
install a given application stack. The possible components used in an
application stack are modeled as *resources*. The metadata for resources is
represented in JSON files and includes constraints on the dependences for
each resource. These dependencies may be libraries, software packages,
application containers, or services (possibly running remotely). When asked
to install an application stack, Engage builds a set of constraints from
its resource database, the user's inputs, and the local machine environment
(operating system, installed software, etc.). These constraints are solved
to provide a compatible set of resources to be installed. Each resource
has an associated *driver*, which knows how to install and manage its resource.
The application is installed by calling the drivers for each of the selected
resources, in dependency order.

The metadata from an installation is saved, including resources, their
configuration values, and resource interrelationships. This data is used to
support additional actions including upgrades, backups, and uninstall.

Current Status
--------------
See RELEASE_NOTES.rst for a listing of the currently supported applications
and drivers.


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
*Engage Users' Guide*.

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
 * The *Engage Users' Guide* describes how to run Engage to deploy applications.
 * The *Engage Django SDK Reference Manual* describes how to package Django
   application for Engage. It is available at
   http://beta.genforma.com/sdk_refman/index.html. It is also available in
   source form with the engage-django-sdk.


Notice
=========
Engage is copyright 2010, 2011 by the genForma
Corporation. It is made available under the Apache V2.0 license.


Authors
===========
The following people contributed to this software:
 * Jay Doane (jay at almery dot com)
 * Jeff Fischer (jeffrey dot fischer at genforma dot com)
 * Rupak Majumdar (rupak at mpi-sws dot org)


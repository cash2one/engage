Introduction
============

Engage is an open source platform for deploying and managing
applications, either on your own servers or in the public cloud.
It automates server provisioning, application installation,
configuration, and upgrades.

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


Engage Documentation
------------------------------
This manual, the *Engage User's Guide*, is intended to help you build
and setup Engage (see :doc:`setup`),  use it to install
applications (see :doc:`installation`), and to manage installed applications (see :doc:`management`).

The *Engage Django SDK Reference Manual* describes how to package Django
applications for Engage. It is available online at
http://beta.genforma.com/sdk_refman/index.html. It is also available in
source form with the engage-django-sdk.

Building the User's Guide
~~~~~~~~~~~~~~~~~~~~~~~~~~
The User's Guide is generated from text files using `Sphinx <http://sphinx.pocoo.org>`_, a
Python-based documentation tool. If you wish to build a local copy of the User's Guide, do the following:

 1. Install Sphinx from http://pypi.python.org/pypi/Sphinx/1.0.7. Alternatively, you can use the Python ``easy_install`` utility (e.g. ``easy_install Sphinx``).
 2. From the top level directory of the Engage source distribution, run ``make all``
 3. The User's Guide will be created in the directory ``docs/users_guide/_build``. The main page for the guide is at ``docs/users_guide/_build/html/index.html``.


Notice
-----------------
The Engage software distribution is copyright 2010, 2011 by the genForma
Corporation. It is made available under the `Apache V2.0 license <http://www.apache.org/licenses/LICENSE-2.0>`_.

The Engage User's Guide (this manual) is copyright 2011 by the genForma Corporation.
It is licensed under a `Creative Commons Attribution-NoDerivs 3.0 Unported License <http://creativecommons.org/licenses/by-nd/3.0>`_.



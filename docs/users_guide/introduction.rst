Introduction
============

What is Engage?
---------------------
Engage is an open source platform for deploying and managing
applications, either on your own servers or in the public cloud.
It automates server provisioning, application installation,
configuration, and upgrades.

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

Overview of this Guide
-----------------------------
This manual, the *Engage User's Guide*, is intended for developers and
operations engineers who wish to use Engage to deploy application
stacks. The overall process for using Engage is:

 1. Download the Engage distribution and build it. This is covered under  :doc:`setup`.
 2. Create a *deployment home* using the Engage ``bootstrap.py``  script. This is covered under :doc:`bootstrapping`.
 3. In some cases (currently, Django applications), you need to package your application using a *packager*. This is covered under :doc:`packaging`.
 4. Run either the *installer* to deploy a pre-defined application stack (covered under :doc:`installer`) or the deployer to deploy a user-defined stack (covered under :doc:`deployer`).
 5. Manage deployed applications using the ``svcctl`` utility. This is covered under :doc:`management`.

The section :doc:`passwords` covers the details of password management
in Engage and the ``password_manager`` utility.

Finally, the section :doc:`resources` contains reference documentation
for the resources supported by this version of Engage.


Other Engage Documentation
-----------------------------------
The *Engage Architecture Guide* describes the design of Engage and
documents the representation used for software component
metadata. This guide is available in the Engage distributation at
``docs/Engage_Architecture_Guide.pdf``.

The *Engage Django SDK Reference Manual* describes how to package Django
applications for Engage. It is available online at
http://beta.genforma.com/sdk_refman/index.html. It is also available in
source form with the engage-django-sdk.

The *Engage Developer's Guide*, describes how to extend Engage. It is
still a work in progress. The current version is included with the
Engage source distribution under ``docs/users_guide``.


Building the User's Guide
~~~~~~~~~~~~~~~~~~~~~~~~~~
The User's Guide is generated from text files using `Sphinx <http://sphinx.pocoo.org>`_, a
Python-based documentation tool. If you wish to build a local copy of
the User's Guide, do the following:                               

 1. Install Sphinx from http://pypi.python.org/pypi/Sphinx/1.0.7. Alternatively, you can use the Python ``easy_install`` utility (e.g. ``easy_install Sphinx``).
 2. From the top level directory of the Engage source distribution, run ``make all``
 3. The User's Guide will be created in the directory ``docs/users_guide/_build``. The main page for the guide is at ``docs/users_guide/_build/html/index.html``.


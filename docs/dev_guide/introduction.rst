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

A developer can extend Engage by creating additional drivers, which
can be used in existing and new installers. Additions to Engage can be
packaged up as *extensions*.

Engage Documentation
------------------------------
This manual, the *Engage Developer's Guide*, is intended to help you
extend Engage with additional drivers and installlers. 
 
The *Engage User's Guide*, describes how to use Engage, rather than
how to extend it.  It describes setup, installation, and management of
installed applications. This guide is available at
http://beta.genforma.com/engage_users_guide/index.html. It is
available in source form with the Engage distribution at ``docs/users_guide``.

The *Engage Architecture Guide* describes the design of Engage and
documents the representation used for software component
metadata. This guide is available in the Engage distributation at
``docs/Engage_Architecture_Guide.pdf``.

The *Engage Django SDK Reference Manual* describes how to package Django
applications for Engage. It is available online at
http://beta.genforma.com/sdk_refman/index.html. It is also available in
source form with the engage-django-sdk.


Building the Developer's Guide
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The Developer's Guide is generated from text files using `Sphinx <http://sphinx.pocoo.org>`_, a
Python-based documentation tool. If you wish to build a local copy of the Developer's Guide, do the following:

 1. Install Sphinx from http://pypi.python.org/pypi/Sphinx/1.0.7. Alternatively, you can use the Python ``easy_install`` utility (e.g. ``easy_install Sphinx``).
 2. From the top level directory of the Engage source distribution, run ``make all``
 3. The Developer's Guide will be created in the directory ``docs/dev_guide/_build``. The main page for the guide is at ``docs/dev_guide/_build/html/index.html``.


File Layout
------------
The Engage distribution is organized as follows::

  engage/
    LICENSE
    Makefile - primary makefile for building Engage and running tests
    README.rst
    RELEASE_NOTES.rst
    bin/ - the build places the binary for the config engine here
    bootstrap.py - this script sets up an Engage deployment home
    buildutils/
      get_platform.sh - used by make scripts to determine the OS and version
      packages.json - metadata describing 3rd-party packages to be included with Engage
      pkgmgr.py - script to download 3rd-party packages
      test_engage.py - runs Engage tests via Nose framework
      valdidate_rdefs.py - script to run validations on Engage resource definintions
    config_src/ - source code for configuration engine (written in ocaml)
    docs/ - users guide's, developer's guide, and architecture guide
    install_extension.py
    metadata/
      bootstrap_package_manifest.txt - used by build system
      django/ - metadata for django installer
      moinmoin/ - metadata for moinmoin installer
      resource_definitions.json - primary file for resource types
      resource_library.json - primary file for resource location pointers
    python_pkg/ - this contains all the python code for engage
      MANIFEST.in
      engage/
        __init__.py
       drivers/ - interact with the components to be installed
       engine/ - frontend and coordination code
       extensions.py - registry of installed extensions
       mgt_backends/ - integration with management tools
       tests/ - unit and regression tests
       utils/ - utility modules
       version.py - defines the Engage version number
       setup.py - used to install Engage package
    upgrade.py - this script upgrades an installed app

The key directories are ``metadata``, which contains the resource
definitions, ``python_pkg``, which contains the Python code, and
``config_src``, which contains the configuration engine. The Python
code has five main modules: ``engage.utils``, ``engage.drivers``, ``engage.mgt_backends``,
``engage.engine``, and ``engage.tests``.  Cross-module dependencies
are enforced as follows:

  * ``utils`` cannot have any external dependencies, other than the Python standard library
  * ``drivers`` may depend only on code in ``utils`` (as well as dependencies within ``drivers`` itself)
  * ``mgt_backends`` may depend on ``utils`` and ``drivers``
  * ``engine`` may depend on ``utils``, ``drivers``, and  ``mgt_backends``
  * ``tests`` may depend on any of the other modules 


Overview of the development process
------------------------------------------------------------------------------------------------
We look into more detail at the steps involved in extending Engage.

Drivers
~~~~~~~~~~~~
First, one determines whether additional drivers will be needed.  This
can be done by reviewing all the components needed for the desired
application stack and mapping them to existing drivers. If any
components do not have existing drivers, new drivers must be created.

Each driver consists of a *resource manager* (a Python class), a
*resource definition* (JSON metadata that described the resource),
and a *resource library entry*
(JSON metadata that describes where to find the resource).
More details on driver development may be found in :ref:`drivers`.

Install Specification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The *install specification*  describes a (partial) set of resources to
be installed. The collection of resources listed in the install
specification can be deployed using the ``deploy-spec`` tool.
This tool expands the set of resources listed in the install spec to
include all required dependencies, computes the values of
configuration properties, and calls the Engage deployment engine to
deploy the requested configuration.
The section :ref:`specs` describes the format for install
specifications and the ``deploy-spec`` tool.

Installer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Optionally, a collection of related  install specifications can be
packaged together in an *installer*. Engage's ``install`` tool
provides a command line interface for selecting from a set of install
specifications (e.g development, test, and production), overriding the
values of selected configuration parameters, and then deploying the
resulting specification.  See the section :ref:`installers` for details.


Extensions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
An *extension* is collection of Engage components, including drivers, appliacation
packages, and installers combined in a specific structure. Engage
provides a tool to add an extension to the Engage distribution,
permitting the newly added components to be seemlessly  included in
any deployments. This enables the independent development and
distribution of content for Engage. Extensions are described in the
section :ref:`extensions`.

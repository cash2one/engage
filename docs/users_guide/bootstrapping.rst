Bootstrapping a Deployment Home
=============================================

How to Run bootstrap.py
-------------------------------------
To install an application, you must first create a *deployment home*. This
is a directory under which Engage and most of the application's components
will be installed [1]_. This is done by running the ``bootstrap.py`` Python script
in the top level Engage directory. It takes one argument, the name of the
directory to use as a deployment home.

This directory will be created, if  necessary.

Note that bootstrap.py  can be run as a normal non-root user. In the event that super-user access is needed
to complete the install (e.g. if a component uses a system-wide package manager), you will be prompted for your password at installation time. This will be used to invoke the ``sudo`` command. 

.. [1] Components which use a system-wide package manager (apt or macports) will be installed globally. Examples include Apache and MySQL.


Deployment Home File Layout
--------------------------------------
The deployment home created by ``bootstrap.py`` contains the following subdirectories:

 * ``config/`` - stores configuration data created during deployment, including metadata for all the deployed components.
 * ``engage/`` - all content specific to Engage
 * ``engage/metadata`` - metadata used for deployment, including resource definitions, installer definitions, and package references.
 * ``engage/bin`` - includes engage-related binaries and scripts, particularly the installer (``install``) and deployer (``deployer``).
 * ``engage/lib`` - Python libraries used by Engage. The Engage Python code is installed into ``engage/lib/python2.x/site-packages/engage-1.y.z-py2.x.egg``, where *2.x* is the Python version and *1.y.z* is the Engage version.
 * ``python`` - Python virtual environment used by any Python components deployed into this deployment home.
 * ``log`` - log files go here by default 


bootstrap.py Command Reference
-------------------------------------------------
Invoke bootstrap as follows::

  bootstrap.py [options] path_to_deployment_home

For example::

  bootstrap.py ~/apps

Options
~~~~~~~~~~~~~~~~~~~~

.. program:: bootstrap.py

.. option:: -h, --help

Print help information and exit.

.. option:: -l LOGLEVEL, --log=LOGLEVEL

Set the log level for messages printed to the console. Options are DEBUG, INFO, WARNING, or ERROR. Default is INFO.

.. option:: -d LOGDIR, --logdir=LOGDIR

Set the master log directory for deployment (defaults to <deployment_home>/log)

.. option:: -x PYTHON_EXE, --python=PYTHON_EXE

Use the specified Python executable as the basis for Python virtual environments

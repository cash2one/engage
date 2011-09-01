Installing Applications via Engage
==================================
After building the Engage distribution, you can now install applications.

Installation steps
---------------------------

1. Creating a deployment home
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
To install an application, you must first create a *deployment home*. This
is a directory under which Engage and most of the application's components
will be installed [1]_. This is done by running the ``bootstrap.py`` Python script
in the top level Engage directory. It takes one argument, the name of the
directory to use as a deployment home.

This directory will be created, if  necessary.

Note that bootstrap.py  can be run as a normal non-root user. In the event that super-user access is needed
to complete the install (e.g. if a component uses a system-wide package manager), you will be prompted for your
password. This will be used to invoke the ``sudo`` command. 

.. [1] Components which use a system-wide package manager (apt or macports) will be installed globally. Examples include Apache and MySQL.

2. Application packaging
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Django appliations must first be packaged with an command line utility
available at http://pypi.python.org/pypi/engage-django-sdk. This utility
validates the layout and settings of your application and captures some
metadata used in deployment.

3. Running the installer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Finally, run the Engage installer, which is at
``<deployment home>/engage/bin/install``, where ``<deployment_home>`` is the
directory that you gave to the bootstrap.py script. The installer has one
required argument, the name of the application you wish to install. You will be prompted for any configuration
choices or values that must be provided to install the application.


.. _password-management:

Password management
----------------------------------
Engage may need to store passwords to install, start, and stop various application components. If necessary,
such passwords are stored in an encrypted file. The key for this file will be based on the user account password.
The password database file will be created if the Engage installer determines that one or more components are
being intalled that 1) need to store a password in the password database, and/or 2) require super-user access.
If the file is created, the user is asked for their password during the installer run and when invoking the ``svcctl``
management tool (see :ref:`svcctl`).

Installation example: MoinMoin
----------------------------------------------
We now walk through an example run of the installer, which illustrates the installation of the
`MoinMoin wiki <http://moinmo.in>`_ on your
local machine. We assume that a deployment home has been bootstrapped at ``~/apps``.

We start by invoking the installer::

  $ ~/apps/engage/bin/install moinmoin

The installer responds as follows::

  Please select a configuration option:
  1  Local Webserver
  2  Apache Server
  configuration option ?

Configuration options represent the different *install specifications* defined for the selected application.
An install specification is a partial listing of the components to be installed for the given app. Any unlisted, but
required components are automatically selected by the configuration engine.
In this case, we can install a configuration that uses MoinMoin's default local webserver or one that will install
Apache and configure it to serve the MoinMoin instance.

For this example, we select option ``1``, the local server. The installer responds with a sequence of configuration
questions. If a default value is available, it is provided in brackets. We can select default values by the hitting
return/enter key
without providing a value. Here are the configuration choices we are presented in our example::

  superuser_name (Wiki user account for superuser access) [root] ? 
  front_page (Page name for wiki front page) [FrontPage] ?

We type return for both cases, selecting the default values of ``root`` and ``FrontPage``. The configuration and
install can then proceed without further user input. We see the following::

  Configuration successful.
  Invoking install engine with arguments ['--no-password-file', '--log=INFO', '--logfile=install.log', '/Users/jfischer/apps/config/install.script']
  Using software library /Users/jfischer/apps/engage/metadata/resource_library.json.
  Processing resource 'jfischer'.
  Resource mac-osx 10.6 (install_target_resource) already installed.
  Processing resource 'moinmoin-webserver-adapter'.
  MoinMoin-localserver-adapter 1.0 (dummy_resouce_manager): validate_pre_install() called
  MoinMoin-localserver-adapter 1.0 (dummy_resouce_manager): install() called
  Install of MoinMoin-localserver-adapter 1.0 (dummy_resouce_manager) successful.
  Processing resource 'python-1'.
  python 2.7: validate_post_install called
  python 2.7 version is 2.7.1
  Resource python 2.7 already installed.
  Processing resource 'moinmoin'.
  downloading http://static.moinmo.in/files/moin-1.9.3.tar.gz via HTTP

At this point, the install will block while the MoinMoin distribution is downloaded from the MoinMoin website.
In general, Engage can download required software packages from the internet when they are not bundled with the
Engage distribution itself. 

After the download completes, the install proceeds as follows::

  Expanding archive 'moin-1.9.3.tar.gz'
  Install of MoinMoin 1.9 successful.
  Service MoinMoin 1.9 started successfully.
  Install completed successfully.

We can now access the MoinMoin wiki at http://localhost:8080.

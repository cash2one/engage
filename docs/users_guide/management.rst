.. _svcctl:

Managing Deployed Applications
===============================

Once an application is installed, the metadata created by Engage can
be used to manage the application. This is accomplished by the
``svcctl`` script, which is installed at ``<deployment_home>/engage/bin/svcctl``. We now describe the commands provided by this utility. A full list of commands and options may be obtained by invoking svcctl with the
``--help`` option.

If any components installed require sudo access (e.g. MySQL or Apache), you will be prompted
for you password. For more details on passwords, see :doc:`passwords`.

All examples in this section assume that the deployment home is ``~/apps``. If you have bootstrapped your
deployment home to another directory, just adjust the example commands accordingly. The ``$`` in examples represents the shell prompt: the rest of the line is input entered by the user. Any lines not beginning with ``$`` are
the output from commands.


Listing resources
-----------------------------
A list of installed *resources* [1]_ may be obtained by invoking ``list`` command of svcctl::

   $  ~/apps/engage/bin/svcctl list

This lists each resource id followed by the resource type (name and version number). If the resource is a *service* [2]_, this is indicated by following the entry with ``[service]``. Here is an example output for a Django application::

  laptop (mac-osx 10.6)
  __GF_inst_11 (macports 1.9)
  django-webserver-config (django-development-webserver 1.0)
  dummy-celery-1 (django-dummy-celery-adapter any)
  dummycache-1 (django-dummy-cache-adapter any)
  python-1 (python 2.7)
  mysql-server (mysql-macports 5.1) [service]
  setuptools-1 (setuptools 0.6)
  __GF_inst_12 (mysql-python 1.2)
  __GF_inst_2 (pip any)
  __GF_inst_3 (gunicorn 0.12)
  __GF_inst_4 (Django 1.2)
  mysql-connector (mysql-connector-for-django 5.1)
  __GF_inst_5 (Django-South 0.7.3)
  django-1 (Django-App 1.0) [service]

.. [1] A *resource* is an application component to be installed and managed by Engage. Examples included libraries, frameworks, web servers, database servers, and caches.

.. [2] A *service* is a resource that must be explictly started before being used. Examples of services include web servers and database servers. A library is an example of a resource that is *not* a service.


Starting services or applications
--------------------------------------------------
The ``start`` command can be used to start either the entire application or a subset of its services. If you run without any options, it will start each service in the application in dependency order. Any services that are already running are
skipped. Thus, if you attempt to start an application after it is running, svcctl will do nothing. Here is an example
where a Django application that uses MySQL is started::

  $ ~/apps/engage/bin/svcctl start
  Password: *****
  mysql-server started.
  django-1 started.

Note that the MySQL server is started before the Django application.

You can also include a specific service id to be started. This will start any dependencies for the required service
and then the service itself. Any services *not* dependent on on the specified service will not be started. Here is an
example where the MySQL server is started, but not the application itself::

  $ ~/apps/engage/bin/svcctl start mysql-server
  Password: *****
  Started mysql-server.

Checking service status
-------------------------------------------
The ``status`` command lists all services and their status (running or stopped)::

  $ ~/apps/engage/bin/svcctl status
  Password: *****
  mysql-server (mysql-macports 5.1) Status: Running
  django-1 (Django-App 1.0) Status: Stopped


Stopping services or applications
--------------------------------------------------------------
The ``stop`` command will stop an individual service or all services. With no additional arguments, it will stop all running services::

  $ ~/apps/engage/bin/svcctl stop
  Password:  ****
  django-1 stopped.
  mysql-server stopped.

If you provide a service id as an argument, it will stop any services dependent on that service and then the service itself. For example, if ``django-1`` depends on ``mysql-server`` and ``mysql-server`` is requested to be stopped,
then ``django-1`` will also be stopped. If ``django-1`` is requested to be stopped, then ``mysql-server`` will
be left running::

  $ ~/apps/engage/bin/svcctl stop django-1
  Password: *****
  django-1 stopped.
 
  $ ~/apps/engage/bin/svcctl status
  Password: *****
  mysql-server (mysql-macports 5.1) Status: Running
  django-1 (Django-App 1.0) Status: Stopped
  
Restarting an application
-------------------------------
In some situtions, it is useful to stop and then restart an application. The ``restart`` command will stop all
services of an application and then start those services again. This is done in dependency order. Here is an example::

  $ svcctl restart
  Password: *****
  django-1 stopped.
  mysql-server stopped.
  Started mysql-server.
  Started django-1.

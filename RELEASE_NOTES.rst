=====================
Engage Release Notes
=====================

Current Status
===============
Engage support installing applications via pre-defined installers or using
the Engage *deployer* tool to install a user-defined set of components.
Multi-node installs are not currently supported but will be available in a
forthcoming release.

Installers
-----------
The following installers are provided with the Engage distribution:
 * django - this installs Django appliations packaged with the engage-django-sdk
 * jasper - this installs the Jasper Reports Server, running with Tomcat and MySQL
 * moinmoin - this installs the MoinMoin wiki
 * tomcat - this installs Java Web Applications (WAR files) using a Tomcat web container


Drivers
--------
The following drivers are supported in the current release:[1]_
 * Apache HTTP Server
 * Apache Tomcat
 * Django
 * Django-south
 * Gunicorn
 * Jasper Reports Server
 * Java Web Applications (WAR files)
 * MySQL
 * SQLite
 * RabbitMQ/Celery


.. [1] Additional drivers are also included to handle dependencies required by the listed drivers. See the *Engage User's Guide* for a complete list of drivers.

What's New for Each Release
============================
 * 1.0.5 - renamed deploy-spec to deployer; added Java support;
           expand user's guide; revamped password handling
 * 1.0.4 - added deploy-spec tool; start of developer docs
 * 1.0.3 - Support for Django 1.3; serve django static files directly
 * 1.0.2 - Added Architecture Guide; bug fixes in build and documentation
 * 1.0.1 - Added User's Guide
 * 1.0.0 - Initial open source release

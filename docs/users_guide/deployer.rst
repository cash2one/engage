Using the Engage Deployer
===============================

Creating an Installation Specification
--------------------------------------
The deployer takes as its input a JSON file containing a
*partial installation specification* ("install spec" for short). This
file tells Engage what components you want installed and the physical
topology of the resulting system (mapping of components to machines,
and how the components are interconnected).  Engage's *configuration
engine* will process this file, adding any required dependencies and
propagating configuration property values across dependency
relationships. As an example of an added dependency, if your install
specification includes Apache Tomcat, but not Java, it will add Java
to the machine that will run Tomcat. As an example of a propagated
configuration property, the hostname and port number of a MySQL
database is set in the configuration of any components that need to
connect to MySQL. The output of Engage's configuration engine is a
*full installation specification*, which is then used to guide the
actual deployment.

The install spec contains a listing of *resource instances*.
A resource instance is a JSON object with the
following information:

 * ``id``, a unique identifying string
 * ``key``, a reference to a *resource type* that defines the  component to be installed and its associated driver. A key has two  properties: ``name`` and ``version``
 * ``config_port``, an optional JSON map that sets values for the resource's configuration properties.
 * ``inside``, ``environment``, and ``peer``, which are optional properties that define relationships with other components.

The ``id`` and ``key`` properties are required for all
resources. The key should correspond to a *resource
definition*. Resource definitions define the names and datatypes of a
component's configuration properties
and its possible relationships with other components. Resource
definitions can be defined globally for Engage (in the file
``metadata/resource_definitions.json``), in an extension, or in an
individual driver. For details on the possible resources to use in an
install spec, see :doc:`resources`.

``config_port`` is only required if you need to override
the default values of configuration property or if a
property does not have a default value. The ``inside`` property must
be defined for any component that runs *inside* another component.
This is everything except for the machine you are deploying to. The
``environment`` and ``peer`` properties only need to be specified when
there is more than one valid candidate for a given inter-component relationship.

An example install spec
-------------------------------------------------
To make things more concrete, let us look at an example installation
specification::

  [
    {"id":"master-host",
       "key": {"name":"dynamic-host", "version":"*"}
    },
    {
      "id": "tomcat",
      "key": {"name":"apache-tomcat", "version":"6.0"},
      "config_port": {
        "manager_port": 8085
      },
      "inside": {
        "id": "master-host",
        "key": {"name":"dynamic-host", "version":"*"},
        "port_mapping": {"host": "host"}
      }
    },
    {
      "id": "hello",
      "key": {"name":"tomcat-war-file", "version":"1.0"},
      "config_port": {
        "war_file_path":"/Users/admin/demos/hello.war"
      },
      "inside": {
        "id": "tomcat",
        "key": {"name":"apache-tomcat", "version":"6.0"},
        "port_mapping": {"tomcat": "tomcat"}
      }
    }
  ]

This file contains three resources: ``master-host``, which represents
the target machine, ``tomcat``, an instance of the Apache Tomcat
server, and ``hello``, which is a Java Web Application.  For target
machines, one can either use specific machine information (if you are
using the install spec for specific machines) or you can use the
generic ``dynamic-host`` resource type, which will be replaced at
runtime with the details of the targets you choose.  The
``master-host`` id should be used for the *controller* host that will
store the deployment metadata (usually the current machine).

The install spec establishes two relationships: ``tomcat`` will
be deployed *inside* ``master-host`` and ``hello`` will be deployed *inside*
``tomcat``. 

The are two configuration properties given values in this spec. The
``manager_port`` property of ``tomcat`` is set to 8085. This overrides
the default value for this property of 8080. The ``war_file_path``
property of ``hello`` is set to /Users/admin/demos/hello.war. This
property has no default value and must be provided, as it indicates
that actual Java WAR file to be deployed.

Running the Deployer
----------------------------------------------------

Prerequisites
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Before running the deployment, you need to first :doc:`build Engage<setup>`,
:doc:`bootstrap <bootstrapping>` a deployment home, and, if you
have a Django application, :doc:`package <packaging>` your application.

The Deploy Program
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The Engage deployer is available at
``<deployment home>/engage/bin/deployer``, where ``<deployment_home>`` is the
directory that you gave to the bootstrap.py script. The deployer has one
required argument, the path to the installation specification file. If
passwords are needed for the deployment, you will be prompted for any
passwords. See :doc:`passwords` for details on how passwords
are handled in Engage.


Deployer Command Line Reference
--------------------------------------------------------------------
Invoke the deployer as follows::

  deployer [options] path_to_install_specification

Options
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. program:: deployer

.. option:: -h, --help

Print help information and exit.

.. option:: --dry-run

Do a dry run of the install. Currently, this creates the full install specification and exits.

.. option:: -g, --generate-password-file

If specified, generate a password file and exit. This password file can be used for future runs of the deployer.

.. option:: -l LOGLEVEL, --log=LOGLEVEL

Set the log level for messages printed to the console. Options are DEBUG, INFO, WARNING, or ERROR. Default is INFO.

.. option:: -p FILE, --master-password-file=FILE

If specified, read the master password from the specified file.



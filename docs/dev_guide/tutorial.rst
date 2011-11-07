Tutorial
===============

In this section, we will walk through the creation of a new driver for
the MongoDb server (http://mongodb.org).

From reading the installation instructions for MongoDb (XXXX), we find
that MongoDb is available as an archive containing pre-compiled
binaries. The installation process to be automated involves
downloading the appropriate archive for the target host's operating
system, extacting the archive, and starting the server.

1. Resource Definition
----------------------
First, we will create a resource definition describing the
dependencies and configuration properties for MongoDb.  The following
JSON object represents our resource definition::

   { "key": { "name": "mongodb", "version": "2.0"},
      "display_name":"MongoDB database server",
      "config_port": {
        "home":{"type":"path", "default":"${input_ports.host.genforma_home}/mongodb-2.0"},
        "port":{"type":"tcp_port", "default":27017},
        "log_file":{"type":"path", "default":"${input_ports.host.log_directory}/mongodb.log"}
      },
      "input_ports": {
        "host": {
          "hostname": {"type": "string"},
          "genforma_home": {"type": "path"},
          "log_directory": {"type": "path"}
        }
      },
      "output_ports": {
        "mongodb": {
            "home":{"type":"path", "source":"config_port.home"},
            "hostname":{"type":"string", "source":"input_ports.host.hostname"},
            "port":{"type":"tcp_port", "source":"config_port.port"}
        }
      },
      "inside": {
        "one-of": [
          { "key": {"name":"mac-osx", "version":{"greater-than-or-equal":"10.5",
                                                 "less-than":"10.7"}},
            "port_mapping": {"host":"host"}},
          { "key": {"name": "ubuntu-linux", "version":"9.10"},
            "port_mapping": {"host":"host"}},
          { "key": {"name": "ubuntu-linux", "version":"10.04"},
            "port_mapping": {"host":"host"}}
        ]
      }
    }

Every resource definition has a *key*, which uniquely defines the
resource. A key consists of two properties: ``name`` and ``version``.
For our resource, we use ``mongodb`` for the name and ``2.0`` for 
the version. Version numbers will be used in dependency contraints to
select ranges of a component that will satisify a dependency. We leave
patch levels off the version number, as we expect the same driver to
work for all patch levels of a given release.

Ports
~~~~~~~~~~~~~~~~~~
Next, we define the *configuration port*. This port defines the set of
properties that must be defined for this resource that are not derived
from dependent resources. This port will contain three properties:
``home``, which represents the directory that will contain MongoDb's
files, ``port``, the TCP/IP port for the MongoDb server, and
``log_file``, which will be used as MongoDb's server log. All three
properties have default values that can be overriden in the install
specification. For ``home`` and ``log_file``, we base our default
values on configuration values supplied by the  ``host`` input
port.

Our resource will have one *input port*: ``host``. This port defines
configuration properties specific to the the machine and user account
into which the MongoDb resource will be deployed. 

There will also be one *output port*: ``mongodb``. This port will
provide any configuration values needed by components that wish to
connect to MongoDb. The ``home`` and ``port`` properties are mapped
from the corresponding properties in the configuration port. The
``hostname`` property is obtained from the ``hostname`` property of
the host port.

Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Our driver will support running on MacOSX and Linux, so we create an
*inside constraint*.

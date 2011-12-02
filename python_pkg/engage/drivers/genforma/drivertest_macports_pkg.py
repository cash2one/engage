"""Test data for macports_pkg driver. Used by engage.tests.driver_tests
"""

resource_id = "zmq-macports"

_install_script = """
[
  {
    "config_port": {},
    "environment": [
      {
        "id": "__macports__1_9__8",
        "key": {
          "name": "macports",
          "version": "1.9"
        },
        "port_mapping": {
          "macports": "macports"
        }
      }
    ],
    "id": "zmq-macports",
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64",
        "genforma_home": "${deployment_home}",
        "hostname": "${hostname}",
        "log_directory": "${deployment_home}/log",
        "os_type": "mac-osx",
        "os_user_name": "${username}",
        "private_ip": null,
        "sudo_password": "GenForma/${username}/sudo_password"
      },
      "macports": {
        "macports_exe": "/opt/local/bin/port"
      }
    },
    "inside": {
      "id": "master-host",
      "key": {
        "name": "mac-osx",
        "version": "10.6"
      },
      "port_mapping": {
        "host": "host"
      }
    },
    "key": {
      "name": "zmq-macports",
      "version": "2.1"
    },
        "output_ports": {
      "port_cfg": {
        "package_name": "zmq"
      }
    }
  }
]
"""

def get_install_script():
    return _install_script

def get_password_data():
    return {}

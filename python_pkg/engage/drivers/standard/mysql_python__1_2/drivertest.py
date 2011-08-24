
"""
Unit test script for mysql-python 1.2 driver.
This script is designed to be run from engage.tests.test_drivers.
"""


# Id for the resource to be tested.
# An instance with this id must be present
# in the install script.
resource_id = "mysql_python"

# The install script should be a json string
# containing a list which includes the
# resource instance for the driver being tested.
# It can use the following substitution variables:
#   deployment_home, hostname, username
_install_script = """
[
  { "id": "mysql_python",
    "key": {"name": "mysql-python", "version": "1.2"},
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
      "mysql_admin": {
        "admin_password": "mysql-server/mysql_admin_password",
        "mysql_client_exe": "/opt/local/bin/mysql5",
        "mysql_config_exe": "/opt/local/lib/mysql5/bin/mysql_config",
        "mysqladmin_exe": "/opt/local/bin/mysqladmin5"
      },
      "python": {
        "PYTHONPATH": "${deployment_home}/python/lib/python2.7/site-packages/",
        "home": "${deployment_home}/python/bin/python",
        "python_bin_dir": "${deployment_home}/python/bin",
        "type": "python",
        "version": "2.7"
      },
      "setuptools": {
        "easy_install": "${deployment_home}/python/bin/easy_install"
      }
    },
    "output_ports": {
      "pkg_info": {
        "provides_pkg": "MySQLdb",
        "test_module": "MySQLdb"
      }
    },
    "inside": {
      "id": "${hostname}",
      "key": {"name": "mac-osx", "version": "10.6"},
      "port_mapping": {
        "host": "host"
      }
    },
    "environment": [
      {
        "id": "mysql-server",
        "key": {"name": "mysql-macports", "version": "5.1"},
        "port_mapping": {
          "mysql": "mysql",
          "mysql_admin": "mysql_admin"
        }
      },
      {
        "id": "python-1",
        "key": {"name": "python", "version": "2.7"},
        "port_mapping": {
          "python": "python"
        }
      },
      {
        "id": "setuptools-1",
        "key": {"name": "setuptools", "version": "0.6"},
        "port_mapping": {
          "setuptools": "setuptools"
        }
      }
    ]
  }
]
"""

def get_install_script():
    return _install_script


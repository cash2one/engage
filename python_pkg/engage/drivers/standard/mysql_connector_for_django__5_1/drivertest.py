
"""
Unit test script for mysql-connector-for-django 5.1 driver.
This script is designed to be run from engage.tests.test_drivers.
"""


# Id for the resource to be tested.
# An instance with this id must be present
# in the install script.
resource_id = "mysql_connector_for_django"

# The install script should be a json string
# containing a list which includes the
# resource instance for the driver being tested.
# It can use the following substitution variables:
# 
_install_script = """
[
  { "id": "mysql_connector_for_django",
    "key": {"name": "mysql-connector-for-django", "version": "5.1"},
    "config_port": {
      "NAME": "django",
      "PASSWORD": "mysql-connector/PASSWORD",
      "USER": "django"
    },
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
      "mysql": {
        "host": "${hostname}",
        "port": 3306
      },
      "mysql_admin": {
        "admin_password": "mysql-server/mysql_admin_password",
        "mysql_client_exe": "/opt/local/bin/mysql5",
        "mysqladmin_exe": "/opt/local/bin/mysqladmin5",
        "mysqldump_exe": "/opt/local/bin/mysqldump5"
      }
    },
    "output_ports": {
      "django_db": {
        "ENGINE": "django.db.backends.mysql",
        "HOST": "${hostname}",
        "NAME": "django",
        "PASSWORD": "mysql-connector/PASSWORD",
        "PORT": 3306,
        "USER": "django"
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
        "id": "__GF_inst_12",
        "key": {"name": "mysql-python", "version": "1.2"}
      },
      {
        "id": "mysql-server",
        "key": {"name": "mysql-macports", "version": "5.1"},
        "port_mapping": {
          "mysql": "mysql",
          "mysql_admin": "mysql_admin"
        }
      }
    ]
  }
]
"""

def get_install_script():
    return _install_script

# If the driver needs access to the password database, either for the sudo
# password or for passwords it maintains in the database, define this function.
# It should return a dict containing an required password entries, except for the
# sudo password which is added by the test driver. If you don't need the password
# database just comment out this function or have it return None.
def get_password_data():
    return {"mysql-server/mysql_admin_password": "test",
            "mysql-connector/PASSWORD": "test"}


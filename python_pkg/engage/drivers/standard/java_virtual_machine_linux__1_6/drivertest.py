
"""
Unit test script for java-virtual-machine-linux 1.6 driver.
This script is designed to be run from engage.tests.test_drivers.
"""


# Id for the resource to be tested.
# An instance with this id must be present
# in the install script.
resource_id = "java_virtual_machine_linux"

# The install script should be a json string
# containing a list which includes the
# resource instance for the driver being tested.
# It can use the following substitution variables:
#   deployment_home, hostname, username
_install_script = """
[
  { "id": "java_virtual_machine_linux",
    "key": {"name": "java-virtual-machine-linux", "version": "1.6"},
    "config_port": {
      "JAVA_HOME": "/usr/lib/jvm/java-6-openjdk/jre"
    },
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64",
        "genforma_home": "${deployment_home}",
        "hostname": "${hostname}",
        "log_directory": "${deployment_home}/log",
        "os_type": "linux",
        "os_user_name": "${username}",
        "private_ip": null,
        "sudo_password": "GenForma/${username}/sudo_password"
      }
    },
    "output_ports": {
      "jvm": {
        "home": "/usr/lib/jvm/java-6-openjdk/jre",
        "type": "jdk"
      }
    },
    "inside": {
      "id": "master-host",
      "key": {"name": "mac-osx", "version": "10.6"},
      "port_mapping": {
        "host": "host"
      }
    }
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
    return {}


"""
Unit test script for apache-tomcat 6.0 driver.
This script is designed to be run from engage.tests.test_drivers.
"""


# Id for the resource to be tested.
# An instance with this id must be present
# in the install script.
resource_id = "apache_tomcat"

# The install script should be a json string
# containing a list which includes the
# resource instance for the driver being tested.
# It can use the following substitution variables:
#   deployment_home, hostname, username
_install_script = """
[
  { "id": "apache_tomcat",
    "key": {"name": "apache-tomcat", "version": "6.0"},
    "config_port": {
      "admin_password": "apache-tomcat/admin_password",
      "admin_user": "admin",
      "gui_admin_password": "apache-tomcat/admin_password",
      "gui_admin_user": "tomcat",
      "home": "${deployment_home}/tomcat-6.0",
      "manager_port": 8080,
      "pid_file":"${deployment_home}/tomcat-6.0/logs/catalina.pid"
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
      "jvm": {
              "home": "/System/Library/Frameworks/JavaVM.framework/Versions/CurrentJDK/Home",
        "type": "jdk"
      }
    },
    "output_ports": {
      "tomcat": {
        "admin_password": "apache-tomcat/admin_password",
        "admin_user": "admin",
        "genforma_home": "${deployment_home}",
        "home": "${deployment_home}/tomcat-6.0",
        "hostname": "${hostname}",
        "manager_port": 8080,
        "os_user_name": "${username}",
        "environment_vars":[],
        "pid_file":"${deployment_home}/tomcat-6.0/logs/catalina.pid"
      }
    },
    "inside": {
      "id": "master-host",
      "key": {"name": "mac-osx", "version": "10.6"},
      "port_mapping": {
        "host": "host"
      }
    },
    "environment": [
      {
        "id": "__java_virtual_machine_abstract__1_6__0",
        "key": {"name": "java-virtual-machine-abstract", "version": "1.6"},
        "port_mapping": {
          "java": "jvm"
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
    return { "apache-tomcat/admin_password": "test"}

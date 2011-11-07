
"""
Unit test script for tomcat-war-file 1.0 driver.
This script is designed to be run from engage.tests.test_drivers.
"""


# Id for the resource to be tested.
# An instance with this id must be present
# in the install script.
resource_id = "tomcat_war_file"

# The install script should be a json string
# containing a list which includes the
# resource instance for the driver being tested.
# It can use the following substitution variables:
#   deployment_home, hostname, username
_install_script = """
[
  { "id": "tomcat_war_file",
    "key": {"name": "tomcat-war-file", "version": "1.0"},
    "config_port": {
      "war_file_path": "/Users/jfischer/demos/hello.war"
    },
    "input_ports": {
      "tomcat": {
        "admin_password": "apache-tomcat/admin_password",
        "admin_user": "manager",
        "environment_vars": [
          
        ],
        "genforma_home": "/Users/jfischer/apps",
        "home": "/Users/jfischer/apps/tomcat-6.0",
        "hostname": "jfischer.local",
        "manager_port": 8080,
        "os_user_name": "jfischer",
        "pid_file":"/Users/jfischer/apps/tomcat-6.0/logs/catalina.pid"
      }
    },
    "inside": {
      "id": "tomcat",
      "key": {"name": "apache-tomcat", "version": "6.0"},
      "port_mapping": {
        "tomcat": "tomcat"
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
    return {
        "apache-tomcat/admin_password": "test"
    }

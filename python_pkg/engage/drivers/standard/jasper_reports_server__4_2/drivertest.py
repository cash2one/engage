
"""
Unit test script for jasper-reports-server 4.2 driver.
This script is designed to be run from engage.tests.test_drivers.
"""


# Id for the resource to be tested.
# An instance with this id must be present
# in the install script.
resource_id = "jasper_reports_server"

# The install script should be a json string
# containing a list which includes the
# resource instance for the driver being tested.
# It can use the following substitution variables:
#   deployment_home, hostname, username
_install_script = """
[
  { "id": "jasper_reports_server",
    "key": {"name": "jasper-reports-server", "version": "4.2"},
    "config_port": {
      "home": "${deployment_home}/jasper_reports_server_4.2"
    },
    "input_ports": {
      "jdbc_driver_file": {
        "extract_path": "${deployment_home}/mysql-connector-java-5.1.18",
        "jar_file_path": "${deployment_home}/mysql-connector-java-5.1.18/mysql-connector-java-5.1.18-bin.jar"
      },
      "mysql": {
        "host": "${hostname}",
        "port": 3306
      },
      "mysql_admin": {
        "admin_password": "mysql-macports/admin_pw",
        "mysql_client_exe": "/opt/local/bin/mysql5",
        "mysql_config_exe": "/opt/local/lib/mysql5/bin/mysql_config",
        "mysql_server_cwd": "/opt/local",
        "mysql_server_script": "/opt/local/lib/mysql5/bin/mysqld_safe",
        "mysql_startup_logfile": "${deployment_home}/log/mysql_startup.log",
        "mysql_user": "_mysql",
        "mysqladmin_exe": "/opt/local/bin/mysqladmin5",
        "mysqldump_exe": "/opt/local/bin/mysqldump5",
        "pid_file_template": "/opt/local/var/db/mysql5/%(hostname)s.pid"
      },
      "tomcat": {
        "admin_password": "apache-tomcat/admin_password",
        "admin_user": "manager",
        "environment_vars": [
          
        ],
        "genforma_home": "${deployment_home}",
        "home": "${deployment_home}/tomcat-6.0",
        "hostname": "${hostname}",
        "manager_port": 8080,
        "os_user_name": "${username}",
        "pid_file": "${deployment_home}/tomcat-6.0/logs/catalina.pid"
      }
    },
    "output_ports": {
      "jasper_server": {
        "url": "http://${hostname}:8080/jasperserver",
        "app_path": "/jasperserver"
      }
    },
    "inside": {
      "id": "tomcat",
      "key": {"name": "apache-tomcat", "version": "6.0"},
      "port_mapping": {
        "tomcat": "tomcat"
      }
    },
    "environment": [
      {
        "id": "__mysql_macports__5_1__2",
        "key": {"name": "mysql-macports", "version": "5.1"},
        "port_mapping": {
          "mysql": "mysql",
          "mysql_admin": "mysql_admin"
        }
      },
      {
        "id": "__mysql_jdbc_driver_jarfile__5_1__1",
        "key": {"name": "mysql-jdbc-driver-jarfile", "version": "5.1"},
        "port_mapping": {
          "jdbc_driver_file": "archive_info"
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
    return { "mysql-macports/admin_pw": "test",
             "apache-tomcat/admin_password": "test"}


resource_id = "mysql-server"

_install_script = """
[
  { "id": "mysql-server",
    "key": {"name": "mysql-apt", "version": "5.1"},
    "config_port": {
      "mysql_admin_password": "mysql-server/mysql_admin_password"
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
      "mysql": {
        "host": "${hostname}",
        "port": 3306
      },
      "mysql_admin": {
        "admin_password": "mysql-server/mysql_admin_password",
        "mysql_client_exe": "/usr/bin/mysql",
        "mysqladmin_exe": "/usr/bin/mysqladmin",
        "mysqldump_exe": "/usr/bin/mysqldump",
        "mysql_user":"mysql",
        "mysql_server_script": "/usr/bin/mysqld_safe",
        "mysql_config_exe": "/usr/bin/mysql_config",
        "pid_file_template":"/var/lib/mysql/${hostname}.pid"
      }
    },
    "inside": {
      "id": "${hostname}",
      "key": {"name": "ubuntu-linux", "version": "10.04"},
      "port_mapping": {
        "host": "host"
      }
    }
  }
]
"""

def get_install_script():
    return _install_script

def get_password_data():
    return {"mysql-server/mysql_admin_password": "test"}

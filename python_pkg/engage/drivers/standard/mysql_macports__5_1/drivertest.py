
resource_id = "mysql-server"

_install_script = """
[
  { "id": "mysql-server",
    "key": {"name": "mysql-macports", "version": "5.1"},
    "config_port": {
      "mysql_admin_password": "mysql-server/mysql_admin_password",
      "startup_on_boot": "no"
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
      "macports": {
        "macports_exe": "/opt/local/bin/port"
      }
    },
    "output_ports": {
      "mysql": {
        "host": "${hostname}",
        "port": 3306
      },
      "mysql_admin": {
        "admin_password": "mysql-server/mysql_admin_password",
        "mysql_client_exe": "/opt/local/bin/mysql5",
        "mysqladmin_exe": "/opt/local/bin/mysqladmin5",
        "mysql_user":"_mysql",
        "mysql_server_script": "/opt/local/bin/mysqld_safe5",
        "mysql_startup_logfile":"${deployment_home}/log/mysql_startup.log",
        "mysql_server_cwd":"/opt/local",
        "pid_file_template":"/opt/local/var/db/mysql5/${hostname}.pid"
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
        "id": "__GF_inst_9",
        "key": {"name": "macports", "version": "1.9"},
        "port_mapping": {
          "macports": "macports"
        }
      }
    ]
  }
]
"""

def get_install_script():
    return _install_script

def get_password_data():
    return {"mysql-server/mysql_admin_password": "test"}

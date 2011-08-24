"""Unit test for apache macports
"""

resource_id = "apache"

_install_script = """
[
  { "id": "apache",
    "key": {"name": "apache-macports", "version": "2.2"},
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64",
        "genforma_home": "${deployment_home}",
        "hostname": "${hostname}",
        "log_directory": "${deployment_home}/log",
        "os_type": "mac-osx",
        "os_user_name": "${username}",
        "private_ip": null,
        "sudo_password": "GenForma/jfischer/sudo_password"
      },
      "macports": {
        "macports_exe": "/opt/local/bin/port"
      }
    },
    "output_ports": {
      "apache": {
        "additional_config_dir": "/opt/local/apache2/conf/engage_extra",
        "apache_group": "_www",
        "apache_user": "_www",
        "cgi_dir": "/opt/local/apache2/cgi-bin",
        "config_file": "/opt/local/apache2/conf/httpd.conf",
        "controller_exe": "/opt/local/apache2/bin/apachectl",
        "htpasswd_exe": "/opt/local/apache2/bin/htpasswd",
        "module_config_dir": "/opt/local/apache2/conf/engage_modules"
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
        "id": "__GF_inst_10",
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
    return {}

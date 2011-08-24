
resource_id = "moinmoin"

_install_script = """
[
  { "id": "moinmoin",
    "key": {"name": "MoinMoin", "version": "1.9"},
    "config_port": {
      "front_page": "FrontPage",
      "home": "${deployment_home}/moin-1.9",
      "superuser_name": "root",
      "use_apache_authentication": "yes"
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
      "python": {
        "PYTHONPATH": "${deployment_home}/python/lib/python2.7/site-packages/",
        "home": "${deployment_home}/python/bin/python",
        "python_bin_dir": "${deployment_home}/python/bin",
        "type": "python",
        "version": "2.7"
      },
      "webserver_adapter": {
        "additional_config_dir": "/opt/local/apache2/conf/engage_extra",
        "config_file": "/opt/local/apache2/conf/httpd.conf",
        "controller_exe": "/opt/local/apache2/bin/apachectl",
        "group": "_www",
        "htpasswd_exe": "/opt/local/apache2/bin/htpasswd",
        "type": "apache"
      }
    },
    "output_ports": {
      "moinmoin": {
        "log_directory": "${deployment_home}/log/moin"
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
        "id": "moinmoin-webserver-adapter",
        "key": {"name": "MoinMoin-apache-adapter", "version": "2.2"},
        "port_mapping": {
          "webserver_adapter": "webserver_adapter"
        }
      },
      {
        "id": "python-1",
        "key": {"name": "python", "version": "2.7"},
        "port_mapping": {
          "python": "python"
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

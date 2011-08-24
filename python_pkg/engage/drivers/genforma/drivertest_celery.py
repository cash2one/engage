resource_id = "celery-1"

_install_script = """
 [ { "id": "celery-1",
    "key": {"name": "Celery", "version": "2.3"},
    "config_port": {
      "password": "engage_129",
      "username": "engage_celery",
      "vhost": "engage_celery_vhost"
    },
    "input_ports": {
      "broker": {
        "BROKER_HOST": "${hostname}",
        "BROKER_PORT": "5672",
        "broker": "rabbitmqctl"
      },
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
      "pip": {
        "pipbin": "${deployment_home}/python/bin/pip"
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
      "celery": {
        "broker": "rabbitmqctl",
        "password": "engage_129",
        "username": "engage_celery",
        "vhost": "engage_celery_vhost"
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
        "id": "rabbitmq-1",
        "key": {"name": "rabbitmq", "version": "2.4"},
        "port_mapping": {
          "broker": "broker"
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
        "id": "__GF_inst_2",
        "key": {"name": "pip", "version": "any"},
        "port_mapping": {
          "pip": "pip"
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

def get_password_data():
    return {}

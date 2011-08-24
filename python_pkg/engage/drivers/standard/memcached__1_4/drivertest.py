import os
resource_id = "memcached"

_install_script_mac = """
[
  { "id": "memcached",
    "key": {"name": "memcached", "version": "1.4"},
    "config_port": {
      "host": "localhost",
      "port": 11211
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
      }
    },
    "output_ports": {
      "cache": {
        "home": "${deployment_home}/memcached-1.4.5",
        "host": "localhost",
        "port": 11211,
        "provider": "memcached"
      }
    },
    "inside": {
      "id": "${hostname}",
      "key": {"name": "mac-osx", "version": "10.6"},
      "port_mapping": {
        "host": "host"
      }
    }
  }
]
"""

_install_script_linux = """
  [{ "id": "memcached",
    "key": {"name": "memcached", "version": "1.4"},
    "config_port": {
      "host": "localhost",
      "port": 11211
    },
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64",
        "genforma_home": "${deployment_home}",
        "hostname": "${hostname}",
        "log_directory": "${deployment_home}/log",
        "os_type": "linux",
        "os_user_name": "${username}",
        "private_ip": "10.177.32.230",
        "sudo_password": "GenForma/${username}/sudo_password"
      }
    },
    "output_ports": {
      "cache": {
        "home": "${deployment_home}/memcached-1.4.5",
        "host": "localhost",
        "port": 11211,
        "provider": "memcached"
      }
    },
    "inside": {
      "id": "${hostname}",
      "key": {"name": "ubuntu-linux", "version": "10.04"},
      "port_mapping": {
        "host": "host"
      }
    }
  },
  { "id": "rabbitmq-1",
    "key": {"name": "rabbitmq", "version": "2.4"},
    "config_port": {
      "host": "${hostname}",
      "port": "5672"
    },
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64",
        "genforma_home": "${deployment_home}",
        "hostname": "${hostname}",
        "log_directory": "${deployment_home}/log",
        "os_type": "linux",
        "os_user_name": "${username}",
        "private_ip": "10.177.32.230",
        "sudo_password": "GenForma/${username}/sudo_password"
      }
    },
    "output_ports": {
      "broker": {
        "BROKER_HOST": "${hostname}",
        "BROKER_PORT": "5672",
        "broker": "rabbitmqctl"
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
    if os.uname()[0]=="Linux":
        return _install_script_linux
    else:
        return _install_script_mac

def get_password_data():
    return {}

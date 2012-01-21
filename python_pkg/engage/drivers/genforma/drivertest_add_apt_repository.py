"""Test data for add_apt_repository package driver (in add_apt_repository.py). Used by
engage.tests.driver_tests.

We test using a specific resource that is installed via pip.
"""

resource_id = "__zeromq_apt_ppa__any__15"


_install_script = """
[
  { "id": "__zeromq_apt_ppa__any__15",
    "key": {"name": "zeromq-apt-ppa", "version": "any"},
    "input_ports": {
      "add_rep_exe_info": {
        "add_apt_repository_exe": "/usr/bin/add-apt-repository"
      },
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
      "repository": {
        "repo_name": "ppa:chris-lea/zeromq"
      }
    },
    "inside": {
      "id": "master-host",
      "key": {"name": "ubuntu-linux", "version": "10.04"},
      "port_mapping": {
        "host": "host"
      }
    },
    "environment": [
      {
        "id": "__python_software_properties__any__16",
        "key": {"name": "python-software-properties", "version": "any"},
        "port_mapping": {
          "add_rep_exe_info": "exe_info"
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

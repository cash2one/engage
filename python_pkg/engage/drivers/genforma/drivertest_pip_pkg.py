"""Test data for pip package driver (in pip.py). Used by
engage.tests.driver_tests.

We test using a specific resource that is installed via pip.
"""

resource_id = "pip_pkg"


_install_script = """
[
  { "id": "pip_pkg",
    "key": {"name": "lxml", "version": "2.3"},
    "input_ports": {
      "pip": {
        "pipbin": "${deployment_home}/python/bin/pip"
      },
      "python": {
        "PYTHONPATH": "${deployment_home}/python/lib/python2.7/site-packages/",
        "home": "${deployment_home}/python/bin/python",
        "python_bin_dir": "${deployment_home}/python/bin",
        "type": "python",
        "version": "2.7"
      }
    },
    "output_ports": {
      "pkg_info": {
        "provides_pkg": "lxml",
        "test_module": "lxml"
      }
    },
    "inside": {
      "id": "master-host",
      "key": {"name": "mac-osx", "version": "10.6"}
    },
    "environment": [
      {
        "id": "_python-master-host",
        "key": {"name": "python", "version": "2.7"},
        "port_mapping": {
          "python": "python"
        }
      },
      {
        "id": "__pip__any__0",
        "key": {"name": "pip", "version": "any"},
        "port_mapping": {
          "pip": "pip"
        }
      }
    ]
  }
]
"""

def get_install_script():
    return _install_script

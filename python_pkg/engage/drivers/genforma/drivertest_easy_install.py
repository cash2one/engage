"""Test data for easy_install driver. Used by engage.tests.driver_tests
"""

resource_id = "easy_install"

_install_script = """
[
  { "id": "easy_install",
    "key": {"name": "pycrypto", "version":"2.3"},
    "input_ports": {
      "python": {
        "home": "${deployment_home}/python/bin/python"
      },
      "setuptools": {
        "easy_install": "${deployment_home}/python/bin/easy_install"
      },
      "host": {
        "genforma_home": "${deployment_home}"
      }
    },
    "output_ports": {
      "pkg_info": {
        "provides_pkg": "Crypto",
        "test_module": "Crypto.Cipher.AES"
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

def get_install_script():
    return _install_script

"""Tests for preprocess_resources.py
"""

import sys
import os
import os.path
import unittest
import json
import logging
logger = logging.getLogger(__name__)
import copy

import fixup_python_path
import engage_file_layout
from engage.utils.file import mangle_resource_key, TempDir, NamedTempFile
from engage.utils.rdef import create_resource_graph
from preprocess_resources import *

_test_resources_1 = [
    {"key":{"name":"test_r1", "version":"1.0"}},
    {"key":{"name":"test_r1_additional", "version":"1.1"}}
]

_test_resources_2 = [
    {"key":{"name":"test_r2", "version":"1.0"}},
]

_test_resources_3 = [
    {"key":{"name":"test_r3", "version":"1.0"}},
]

class ResKeySet(object):
    """Maintains a set of resource keys.
    """
    def __init__(self):
        self.key_map = {}
    def add_key(self, key):
        """Add the key and return true if the key was new,
        false otherwise.
        """
        mangled_name = mangle_resource_key(key)
        if self.key_map.has_key(mangled_name):
            key_list = self.key_map[mangled_name]
            for k in key_list:
                if k==key:
                    return False
            key_list.append(key)
            return True
        else:
            self.key_map[mangled_name] = [key,]
            return True

    def has_key(self, key):
        mangled_name = mangle_resource_key(key)
        if self.key_map.has_key(mangled_name):
            key_list = self.key_map[mangled_name]
            for k in key_list:
                if k==key:
                    return True
            return False
        else:
            return False

    def is_empty(self):
        return len(self.key_map)==0

    def all_keys(self):
        for mk in self.key_map.keys():
            for k in self.key_map[mk]:
                yield k
                
    def __str__(self):
        return '[' + \
               ', '.join("%s %s" % (k['name'], k['version']) for k in self.all_keys()) + ']'

_test_install_spec = """[
  { "id": "master-host",
     "key": {"name":"dynamic-host", "version":"*"}
  },
  { "id": "python-master",
    "key": { "name": "python", "version": "*" },
    "inside": {
      "id": "master-host",
      "key": {"name":"dynamic-host", "version":"*"}
    }
  },
  { "id": "database-host",
     "key": {"name":"dynamic-host", "version":"*"}
  },
 {
    "id": "mysql-server",
    "key": {
      "version": "5.1",
      "name": "mysql-macports"
    },
    "inside": {
      "id": "database-host",
      "key": {"name":"dynamic-host", "version":"*"},
      "port_mapping": {
        "host": "host"
      }
    }
  },  
  { "id": "django-webserver-config",
    "key": {"name": "django-development-webserver", "version": "1.0"},
    "inside": {
      "id": "master-host",
      "key": {"name":"dynamic-host", "version":"*"},
      "port_mapping": {"host": "host"}
    }
  },
  {
    "inside": {
      "port_mapping": {
        "host": "host"
      },
      "id": "master-host",
      "key": {"name":"dynamic-host", "version":"*"}
    },
    "id": "mysql-connector",
    "key": {
      "version": "5.1",
      "name": "mysql-connector-for-django"
    }
  },  
  {
    "id": "django-1",
    "key": {"name": "Django-App", "version": "1.0"},
    "inside": {
      "id": "master-host",
      "key": {"name":"dynamic-host", "version":"*"},
      "port_mapping": {"host": "host"}
    },
    "environment": [
      {
        "id": "python-master",
        "key": { "name": "python", "version": "*" }
      }
    ],
    "properties": {
      "app_short_name": "django"
    }
  }
]
"""

_expected_output_install_spec = """
[
  {
    "id": "master-host", 
    "key": {
      "version": "10.6", 
      "name": "mac-osx"
    }
  }, 
  {
    "inside": {
      "id": "master-host", 
      "key": {
        "version": "10.6", 
        "name": "mac-osx"
      }
    }, 
    "id": "python-master", 
    "key": {
      "version": "2.6", 
      "name": "python"
    }
  }, 
  {
    "id": "database-host", 
    "key": {
      "version": "10.6", 
      "name": "mac-osx"
    }
  }, 
  {
    "inside": {
      "port_mapping": {
        "host": "host"
      }, 
      "id": "database-host", 
      "key": {
        "version": "10.6", 
        "name": "mac-osx"
      }
    }, 
    "id": "mysql-server", 
    "key": {
      "version": "5.1", 
      "name": "mysql-macports"
    }
  }, 
  {
    "inside": {
      "port_mapping": {
        "host": "host"
      }, 
      "id": "master-host", 
      "key": {
        "version": "10.6", 
        "name": "mac-osx"
      }
    }, 
    "id": "django-webserver-config", 
    "key": {
      "version": "1.0", 
      "name": "django-development-webserver"
    }
  }, 
  {
    "inside": {
      "port_mapping": {
        "host": "host"
      }, 
      "id": "master-host", 
      "key": {
        "version": "10.6", 
        "name": "mac-osx"
      }
    }, 
    "id": "mysql-connector", 
    "key": {
      "version": "5.1", 
      "name": "mysql-connector-for-django"
    }
  }, 
  {
    "environment": [
      {
        "id": "python-master", 
        "key": {
          "version": "2.6", 
          "name": "python"
        }
      }
    ], 
    "inside": {
      "port_mapping": {
        "host": "host"
      }, 
      "id": "master-host", 
      "key": {
        "version": "10.6", 
        "name": "mac-osx"
      }
    }, 
    "id": "django-1", 
    "key": {
      "version": "1.0", 
      "name": "Django-App"
    }, 
    "properties": {
      "app_short_name": "django"
    }
  }
]
"""
class TestPreprocessResources(unittest.TestCase):
    def setUp(self):
        self.layout_mgr = engage_file_layout.get_engine_layout_mgr()

    def _write_driver(self, key, json_data, extn_dir):
        driver_dir = os.path.join(extn_dir, mangle_resource_key(key))
        os.mkdir(driver_dir)
        with open(os.path.join(driver_dir, "resources.json"), "wb") as f:
            json.dump(json_data, f)

    def _get_resource_keys(self, filepath):
        """Return two sets of keys: the set of all keys in the resource def
        file and a set of duplicate keys
        """
        all_keys = ResKeySet()
        duplicates = ResKeySet()
        with open(filepath, "rb") as f:
            rdefs = json.load(f)
        for r in rdefs['resource_definitions']:
            k = r['key']
            if not all_keys.add_key(k):
                duplicates.add_key(k)
        return (all_keys, duplicates)
        
    def test_preprocess_resources(self):
        with TempDir() as td:
            extn_dir = os.path.join(td.name, "my_extn")
            os.mkdir(extn_dir)
            self._write_driver(_test_resources_1[0]["key"],
                               _test_resources_1,
                               extn_dir)
            self._write_driver(_test_resources_2[0]["key"],
                               _test_resources_2,
                               extn_dir)
            extn_resource_file = os.path.join(extn_dir, "resources.json")
            with open(extn_resource_file, "wb") as rf:
                json.dump(_test_resources_3, rf)
            target_resource_file = os.path.join(td.name, "target_resources.json")
            preprocess_resource_file(self.layout_mgr.get_resource_def_file(),
                                     [extn_resource_file,],
                                     target_resource_file, logger,
                                     drivers_dir=td.name)
            (all_keys, dups) = self._get_resource_keys(target_resource_file)
            self.assertTrue(all_keys.has_key(_test_resources_1[0]["key"]))
            self.assertTrue(all_keys.has_key(_test_resources_1[1]["key"]))
            self.assertTrue(all_keys.has_key(_test_resources_2[0]["key"]))
            self.assertTrue(all_keys.has_key(_test_resources_3[0]["key"]))
            self.assertTrue(dups.is_empty())

    def test_for_duplicate_resource_keys(self):
        """This test does the preprocessing for the actual drivers and
        checks for duplicate resource keys.
        """
        preprocess_resource_file(self.layout_mgr.get_resource_def_file(),
                                 self.layout_mgr.get_extension_resource_files(),
                                 self.layout_mgr.get_preprocessed_resource_file(),
                                 logger)
        (all_keys, dups) = \
            self._get_resource_keys(self.layout_mgr.get_preprocessed_resource_file())
        self.assertTrue(dups.is_empty(), "The following resources have duplicate definitions: %s" % dups.__str__())

    def test_resource_validation(self):
        """Validate the preprocessed resource definitions.
        """
        preprocess_resource_file(self.layout_mgr.get_resource_def_file(),
                                 self.layout_mgr.get_extension_resource_files(),
                                 self.layout_mgr.get_preprocessed_resource_file(),
                                 logger)
        with open(self.layout_mgr.get_preprocessed_resource_file(), "rb") as f:
            (errors, warnings) = create_resource_graph(json.load(f)).validate()
        self.assertTrue(errors==0, "%d errors in resource validation" % errors)


    def test_install_spec_preprocessing(self):
        with NamedTempFile(_test_install_spec) as f:
            spec = parse_raw_install_spec_file(f.name)
            dynamic_hosts = query_install_spec(spec, name="dynamic-host",
                                               version='*')
            machine_key = {"name":"mac-osx", "version":"10.6"}
            fixup_resources = []
            for host_inst in dynamic_hosts:
                new_inst = copy.deepcopy(host_inst)
                new_inst["key"] = machine_key
                fixup_resources.append(new_inst)
            python_resources = query_install_spec(spec, name="python")
            python_key = {"name":"python", "version":"2.6"}
            for py_res in python_resources:
                new_inst = copy.deepcopy(py_res)
                new_inst["key"] = python_key
                fixup_resources.append(new_inst)
            spec = fixup_installed_resources_in_install_spec(spec, fixup_resources)
            #print json.dumps(spec, indent=2)
            expected_output = json.loads(_expected_output_install_spec)
            self.assertEqual(spec, expected_output)

_old_installed_resources = """
[
  {
    "config_port": {
      "cpu_arch": "x86_64", 
      "genforma_home": "/Users/jfischer/apps", 
      "hostname": "jfischer", 
      "log_directory": "/Users/jfischer/apps/log", 
      "os_user_name": "jfischer", 
      "private_ip": null, 
      "sudo_password": "GenForma/jfischer/sudo_password"
    }, 
    "environment": [], 
    "id": "master-host", 
    "input_ports": {}, 
    "key": {
      "name": "mac-osx", 
      "version": "10.6"
    }, 
    "output_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true, 
      "use_as_install_target": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [], 
    "id": "__g++__4_2__15", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "g++", 
      "version": "4.2"
    }, 
    "output_ports": {}, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {
      "JAVA_HOME": "/System/Library/Frameworks/JavaVM.framework/Versions/CurrentJDK/Home"
    }, 
    "environment": [], 
    "id": "__java_virtual_machine_macosx__1_6__6", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "java-virtual-machine-macosx", 
      "version": "1.6"
    }, 
    "output_ports": {
      "jvm": {
        "home": "/System/Library/Frameworks/JavaVM.framework/Versions/CurrentJDK/Home", 
        "java_exe": "/usr/bin/java", 
        "type": "jdk"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [], 
    "id": "__macports__1_9__17", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "macports", 
      "version": "1.9"
    }, 
    "output_ports": {
      "macports": {
        "macports_exe": "/opt/local/bin/port"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [], 
    "id": "__solr_block_schema_file__1_0__5", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "solr-block-schema-file", 
      "version": "1.0"
    }, 
    "output_ports": {
      "file_info": {
        "file_path": "/Users/jfischer/apps/solr_schema.xml"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {
      "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
      "PYTHON_BIN_DIR": "/Users/jfischer/apps/python/bin", 
      "PYTHON_HOME": "/Users/jfischer/apps/python/bin/python"
    }, 
    "environment": [], 
    "id": "_python-master-host", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "python", 
      "version": "2.7"
    }, 
    "output_ports": {
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "__java_virtual_machine_macosx__1_6__6", 
        "key": {
          "name": "java-virtual-machine-macosx", 
          "version": "1.6"
        }, 
        "port_mapping": {
          "jvm": "jvm"
        }
      }
    ], 
    "id": "__java_virtual_machine_abstract__1_6__4", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }, 
      "jvm": {
        "home": "/System/Library/Frameworks/JavaVM.framework/Versions/CurrentJDK/Home", 
        "java_exe": "/usr/bin/java", 
        "type": "jdk"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "java-virtual-machine-abstract", 
      "version": "1.6"
    }, 
    "output_ports": {
      "jvm": {
        "home": "/System/Library/Frameworks/JavaVM.framework/Versions/CurrentJDK/Home", 
        "java_exe": "/usr/bin/java", 
        "type": "jdk"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "__macports__1_9__17", 
        "key": {
          "name": "macports", 
          "version": "1.9"
        }, 
        "port_mapping": {
          "macports": "macports"
        }
      }
    ], 
    "id": "__zmq_macports__2_1__16", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }, 
      "macports": {
        "macports_exe": "/opt/local/bin/port"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "zmq-macports", 
      "version": "2.1"
    }, 
    "output_ports": {
      "port_cfg": {
        "package_name": "zmq"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "_python-master-host", 
        "key": {
          "name": "python", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "python": "python"
        }
      }
    ], 
    "id": "_setuptools-master-host", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }, 
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "setuptools", 
      "version": "0.6"
    }, 
    "output_ports": {
      "setuptools": {
        "easy_install": "/Users/jfischer/apps/python/bin/easy_install"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "__solr_block_schema_file__1_0__5", 
        "key": {
          "name": "solr-block-schema-file", 
          "version": "1.0"
        }, 
        "port_mapping": {
          "schema_file": "file_info"
        }
      }, 
      {
        "id": "__java_virtual_machine_abstract__1_6__4", 
        "key": {
          "name": "java-virtual-machine-abstract", 
          "version": "1.6"
        }, 
        "port_mapping": {
          "jvm": "jvm"
        }
      }
    ], 
    "id": "__apache_solr_jetty_server__4_1__0", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }, 
      "jvm": {
        "home": "/System/Library/Frameworks/JavaVM.framework/Versions/CurrentJDK/Home", 
        "java_exe": "/usr/bin/java", 
        "type": "jdk"
      }, 
      "schema_file": {
        "file_path": "/Users/jfischer/apps/solr_schema.xml"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "apache-solr-jetty-server", 
      "version": "4.1"
    }, 
    "output_ports": {
      "solr": {
        "home": "/Users/jfischer/apps/solr"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "_python-master-host", 
        "key": {
          "name": "python", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "python": "python"
        }
      }, 
      {
        "id": "_setuptools-master-host", 
        "key": {
          "name": "setuptools", 
          "version": "0.6"
        }, 
        "port_mapping": {
          "setuptools": "setuptools"
        }
      }
    ], 
    "id": "__gunicorn__0_14__5", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }, 
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }, 
      "setuptools": {
        "easy_install": "/Users/jfischer/apps/python/bin/easy_install"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "gunicorn", 
      "version": "0.14"
    }, 
    "output_ports": {
      "gunicorn": {
        "gunicorn_django_exe": "/Users/jfischer/apps/python/bin/gunicorn_django", 
        "gunicorn_exe": "/Users/jfischer/apps/python/bin/gunicorn"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "__g++__4_2__15", 
        "key": {
          "name": "g++", 
          "version": "4.2"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "_python-master-host", 
        "key": {
          "name": "python", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "python": "python"
        }
      }, 
      {
        "id": "_setuptools-master-host", 
        "key": {
          "name": "setuptools", 
          "version": "0.6"
        }, 
        "port_mapping": {
          "setuptools": "setuptools"
        }
      }
    ], 
    "id": "__pycrypto__2_3__10", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }, 
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }, 
      "setuptools": {
        "easy_install": "/Users/jfischer/apps/python/bin/easy_install"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "pycrypto", 
      "version": "2.3"
    }, 
    "output_ports": {
      "pkg_info": {
        "provides_pkg": "Crypto", 
        "test_module": "Crypto.Cipher.AES"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "_python-master-host", 
        "key": {
          "name": "python", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "python": "python"
        }
      }, 
      {
        "id": "_setuptools-master-host", 
        "key": {
          "name": "setuptools", 
          "version": "0.6"
        }, 
        "port_mapping": {
          "setuptools": "setuptools"
        }
      }
    ], 
    "id": "__pymongo__2_1__0", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }, 
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }, 
      "setuptools": {
        "easy_install": "/Users/jfischer/apps/python/bin/easy_install"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "pymongo", 
      "version": "2.1"
    }, 
    "output_ports": {
      "pkg_info": {
        "test_module": "pymongo"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "__macports__1_9__17", 
        "key": {
          "name": "macports", 
          "version": "1.9"
        }, 
        "port_mapping": {
          "macports": "macports"
        }
      }, 
      {
        "id": "__zmq_macports__2_1__16", 
        "key": {
          "name": "zmq-macports", 
          "version": "2.1"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "_setuptools-master-host", 
        "key": {
          "name": "setuptools", 
          "version": "0.6"
        }, 
        "port_mapping": {
          "setuptools": "setuptools"
        }
      }, 
      {
        "id": "_python-master-host", 
        "key": {
          "name": "python", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "python": "python"
        }
      }
    ], 
    "id": "__pyzmq_macports__2_7__13", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }, 
      "macports": {
        "macports_exe": "/opt/local/bin/port"
      }, 
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }, 
      "setuptools": {
        "easy_install": "/Users/jfischer/apps/python/bin/easy_install"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "pyzmq-macports", 
      "version": "2.7"
    }, 
    "output_ports": {
      "port_cfg": {
        "package_name": "py27-zmq"
      }, 
      "zeromq": {}
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "_python-master-host", 
        "key": {
          "name": "python", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "python": "python"
        }
      }, 
      {
        "id": "_setuptools-master-host", 
        "key": {
          "name": "setuptools", 
          "version": "0.6"
        }, 
        "port_mapping": {
          "setuptools": "setuptools"
        }
      }
    ], 
    "id": "_pip-master-host", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }, 
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }, 
      "setuptools": {
        "easy_install": "/Users/jfischer/apps/python/bin/easy_install"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "pip", 
      "version": "any"
    }, 
    "output_ports": {
      "pip": {
        "pipbin": "/Users/jfischer/apps/python/bin/pip"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {
      "home": "/Users/jfischer/apps/mongodb-2.0", 
      "log_file": "/Users/jfischer/apps/log/mongodb.log", 
      "port": 27017
    }, 
    "environment": [
      {
        "id": "_python-master-host", 
        "key": {
          "name": "python", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "python": "python"
        }
      }, 
      {
        "id": "__pymongo__2_1__0", 
        "key": {
          "name": "pymongo", 
          "version": "2.1"
        }, 
        "port_mapping": {}
      }
    ], 
    "id": "__mongodb__2_0__1", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }, 
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "mongodb", 
      "version": "2.0"
    }, 
    "output_ports": {
      "mongodb": {
        "home": "/Users/jfischer/apps/mongodb-2.0", 
        "hostname": "localhost", 
        "port": 27017
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "__pyzmq_macports__2_7__13", 
        "key": {
          "name": "pyzmq-macports", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "zeromq": "zeromq"
        }
      }, 
      {
        "id": "_python-master-host", 
        "key": {
          "name": "python", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "python": "python"
        }
      }
    ], 
    "id": "__pyzmq_abstract__2_1__9", 
    "input_ports": {
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }, 
      "zeromq": {}
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {}
    }, 
    "key": {
      "name": "pyzmq-abstract", 
      "version": "2.1"
    }, 
    "output_ports": {}, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "_pip-master-host", 
        "key": {
          "name": "pip", 
          "version": "any"
        }, 
        "port_mapping": {
          "pip": "pip"
        }
      }, 
      {
        "id": "_python-master-host", 
        "key": {
          "name": "python", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "python": "python"
        }
      }
    ], 
    "id": "__distributed_job_manager__0_1__3", 
    "input_ports": {
      "pip": {
        "pipbin": "/Users/jfischer/apps/python/bin/pip"
      }, 
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {}
    }, 
    "key": {
      "name": "distributed-job-manager", 
      "version": "0.1"
    }, 
    "output_ports": {
      "pkg_info": {
        "provides_pkg": "dist_job_mgr", 
        "test_module": "dist_job_mgr.version", 
        "version": "0.1.0"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "_python-master-host", 
        "key": {
          "name": "python", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "python": "python"
        }
      }, 
      {
        "id": "_pip-master-host", 
        "key": {
          "name": "pip", 
          "version": "any"
        }, 
        "port_mapping": {
          "pip": "pip"
        }
      }
    ], 
    "id": "__engage_utils__1_0__12", 
    "input_ports": {
      "pip": {
        "pipbin": "/Users/jfischer/apps/python/bin/pip"
      }, 
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {}
    }, 
    "key": {
      "name": "engage_utils", 
      "version": "1.0"
    }, 
    "output_ports": {
      "pkg_info": {
        "provides_pkg": "engage_utils", 
        "test_module": "engage_utils.process"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "__pycrypto__2_3__10", 
        "key": {
          "name": "pycrypto", 
          "version": "2.3"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "_pip-master-host", 
        "key": {
          "name": "pip", 
          "version": "any"
        }, 
        "port_mapping": {
          "pip": "pip"
        }
      }, 
      {
        "id": "_python-master-host", 
        "key": {
          "name": "python", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "python": "python"
        }
      }
    ], 
    "id": "__fabric__1_4__11", 
    "input_ports": {
      "pip": {
        "pipbin": "/Users/jfischer/apps/python/bin/pip"
      }, 
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {}
    }, 
    "key": {
      "name": "fabric", 
      "version": "1.4"
    }, 
    "output_ports": {
      "pkg_info": {
        "provides_pkg": "fabric", 
        "test_module": "fabric.api"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "_pip-master-host", 
        "key": {
          "name": "pip", 
          "version": "any"
        }, 
        "port_mapping": {
          "pip": "pip"
        }
      }, 
      {
        "id": "_python-master-host", 
        "key": {
          "name": "python", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "python": "python"
        }
      }
    ], 
    "id": "__psutil__0_6__2", 
    "input_ports": {
      "pip": {
        "pipbin": "/Users/jfischer/apps/python/bin/pip"
      }, 
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {}
    }, 
    "key": {
      "name": "psutil", 
      "version": "0.6"
    }, 
    "output_ports": {
      "pkg_info": {
        "provides_pkg": "psutil", 
        "test_module": "psutil"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "_python-master-host", 
        "key": {
          "name": "python", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "python": "python"
        }
      }, 
      {
        "id": "_pip-master-host", 
        "key": {
          "name": "pip", 
          "version": "any"
        }, 
        "port_mapping": {
          "pip": "pip"
        }
      }
    ], 
    "id": "__urllib3__1_5__8", 
    "input_ports": {
      "pip": {
        "pipbin": "/Users/jfischer/apps/python/bin/pip"
      }, 
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {}
    }, 
    "key": {
      "name": "urllib3", 
      "version": "1.5"
    }, 
    "output_ports": {
      "pkg_info": {
        "provides_pkg": "urllib3", 
        "test_module": "urllib3"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "__distributed_job_manager__0_1__3", 
        "key": {
          "name": "distributed-job-manager", 
          "version": "0.1"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "__pyzmq_abstract__2_1__9", 
        "key": {
          "name": "pyzmq-abstract", 
          "version": "2.1"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "_setuptools-master-host", 
        "key": {
          "name": "setuptools", 
          "version": "0.6"
        }, 
        "port_mapping": {
          "setuptools": "setuptools"
        }
      }, 
      {
        "id": "_python-master-host", 
        "key": {
          "name": "python", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "python": "python"
        }
      }
    ], 
    "id": "__datablox_engage_adapter__1_0__1", 
    "input_ports": {
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }, 
      "setuptools": {
        "easy_install": "/Users/jfischer/apps/python/bin/easy_install"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {}
    }, 
    "key": {
      "name": "datablox-engage-adapter", 
      "version": "1.0"
    }, 
    "output_ports": {
      "pkg_info": {
        "test_module": "datablox_engage_adapter"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "__distributed_job_manager__0_1__3", 
        "key": {
          "name": "distributed-job-manager", 
          "version": "0.1"
        }, 
        "port_mapping": {
          "pkg_info": "pkg_info"
        }
      }
    ], 
    "id": "djm-server", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }, 
      "pkg_info": {
        "provides_pkg": "dist_job_mgr", 
        "test_module": "dist_job_mgr.version", 
        "version": "0.1.0"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "djm-server-config", 
      "version": "0.1"
    }, 
    "output_ports": {
      "djm_server": {
        "server_config_dir": "/Users/jfischer/apps/djm"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "__engage_utils__1_0__12", 
        "key": {
          "name": "engage_utils", 
          "version": "1.0"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "__fabric__1_4__11", 
        "key": {
          "name": "fabric", 
          "version": "1.4"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "__pycrypto__2_3__10", 
        "key": {
          "name": "pycrypto", 
          "version": "2.3"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "__pyzmq_abstract__2_1__9", 
        "key": {
          "name": "pyzmq-abstract", 
          "version": "2.1"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "_setuptools-master-host", 
        "key": {
          "name": "setuptools", 
          "version": "0.6"
        }, 
        "port_mapping": {
          "setuptools": "setuptools"
        }
      }, 
      {
        "id": "_python-master-host", 
        "key": {
          "name": "python", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "python": "python"
        }
      }
    ], 
    "id": "__datablox_framework__1_0__0", 
    "input_ports": {
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }, 
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }, 
      "setuptools": {
        "easy_install": "/Users/jfischer/apps/python/bin/easy_install"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "datablox-framework", 
      "version": "1.0"
    }, 
    "output_ports": {
      "datablox_framework": {
        "BLOXPATH": "/Users/jfischer/apps/blox", 
        "caretaker_exe": "/Users/jfischer/apps/python/bin/datablox-caretaker", 
        "loader_exe": "/Users/jfischer/apps/python/bin/datablox-loader"
      }, 
      "pkg_info": {
        "test_module": "datablox_framework"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "__urllib3__1_5__8", 
        "key": {
          "name": "urllib3", 
          "version": "1.5"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "_pip-master-host", 
        "key": {
          "name": "pip", 
          "version": "any"
        }, 
        "port_mapping": {
          "pip": "pip"
        }
      }, 
      {
        "id": "_python-master-host", 
        "key": {
          "name": "python", 
          "version": "2.7"
        }, 
        "port_mapping": {
          "python": "python"
        }
      }
    ], 
    "id": "__si_utils__1_0__1", 
    "input_ports": {
      "pip": {
        "pipbin": "/Users/jfischer/apps/python/bin/pip"
      }, 
      "python": {
        "PYTHONPATH": "/Users/jfischer/apps/python/lib/python2.7/site-packages/", 
        "home": "/Users/jfischer/apps/python/bin/python", 
        "python_bin_dir": "/Users/jfischer/apps/python/bin", 
        "type": "python", 
        "version": "2.7"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {}
    }, 
    "key": {
      "name": "si_utils", 
      "version": "1.0"
    }, 
    "output_ports": {
      "pkg_info": {
        "provides_pkg": "si_utils", 
        "test_module": "si_utils.pathutils"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {
      "config_dir": "/Users/jfischer/apps/datablox_fileserver", 
      "log_file": "/Users/jfischer/apps/log/datablox_fileserver.log", 
      "pid_file": "/Users/jfischer/apps/datablox_fileserver/fileserver.pid"
    }, 
    "environment": [
      {
        "id": "__gunicorn__0_14__5", 
        "key": {
          "name": "gunicorn", 
          "version": "0.14"
        }, 
        "port_mapping": {
          "gunicorn": "gunicorn"
        }
      }, 
      {
        "id": "__datablox_engage_adapter__1_0__1", 
        "key": {
          "name": "datablox-engage-adapter", 
          "version": "1.0"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "__datablox_framework__1_0__0", 
        "key": {
          "name": "datablox-framework", 
          "version": "1.0"
        }, 
        "port_mapping": {
          "datablox_framework": "datablox_framework"
        }
      }
    ], 
    "id": "__datablox_fileserver__1_0__0", 
    "input_ports": {
      "datablox_framework": {
        "BLOXPATH": "/Users/jfischer/apps/blox", 
        "caretaker_exe": "/Users/jfischer/apps/python/bin/datablox-caretaker", 
        "loader_exe": "/Users/jfischer/apps/python/bin/datablox-loader"
      }, 
      "gunicorn": {
        "gunicorn_django_exe": "/Users/jfischer/apps/python/bin/gunicorn_django", 
        "gunicorn_exe": "/Users/jfischer/apps/python/bin/gunicorn"
      }, 
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "datablox-fileserver", 
      "version": "1.0"
    }, 
    "output_ports": {}, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {
      "config_dir": "/Users/jfischer/apps/datablox_caretaker", 
      "log_file": "/Users/jfischer/apps/log/datablox_caretaker.log", 
      "pid_file": "/Users/jfischer/apps/datablox_caretaker/caretaker.pid"
    }, 
    "environment": [
      {
        "id": "__psutil__0_6__2", 
        "key": {
          "name": "psutil", 
          "version": "0.6"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "__datablox_engage_adapter__1_0__1", 
        "key": {
          "name": "datablox-engage-adapter", 
          "version": "1.0"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "__datablox_framework__1_0__0", 
        "key": {
          "name": "datablox-framework", 
          "version": "1.0"
        }, 
        "port_mapping": {
          "datablox_framework": "datablox_framework"
        }
      }
    ], 
    "id": "caretaker", 
    "input_ports": {
      "datablox_framework": {
        "BLOXPATH": "/Users/jfischer/apps/blox", 
        "caretaker_exe": "/Users/jfischer/apps/python/bin/datablox-caretaker", 
        "loader_exe": "/Users/jfischer/apps/python/bin/datablox-loader"
      }, 
      "host": {
        "cpu_arch": "x86_64", 
        "genforma_home": "/Users/jfischer/apps", 
        "hostname": "jfischer", 
        "log_directory": "/Users/jfischer/apps/log", 
        "os_type": "mac-osx", 
        "os_user_name": "jfischer", 
        "private_ip": null, 
        "sudo_password": "GenForma/jfischer/sudo_password"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "datablox-caretaker", 
      "version": "1.0"
    }, 
    "output_ports": {}, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "__si_utils__1_0__1", 
        "key": {
          "name": "si_utils", 
          "version": "1.0"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "__mongodb__2_0__1", 
        "key": {
          "name": "mongodb", 
          "version": "2.0"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "__pymongo__2_1__0", 
        "key": {
          "name": "pymongo", 
          "version": "2.1"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "__datablox_framework__1_0__0", 
        "key": {
          "name": "datablox-framework", 
          "version": "1.0"
        }, 
        "port_mapping": {
          "datablox_framework": "datablox_framework"
        }
      }
    ], 
    "id": "si-file-mongo", 
    "input_ports": {
      "datablox_framework": {
        "BLOXPATH": "/Users/jfischer/apps/blox", 
        "caretaker_exe": "/Users/jfischer/apps/python/bin/datablox-caretaker", 
        "loader_exe": "/Users/jfischer/apps/python/bin/datablox-loader"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "si-file-mongo", 
      "version": "1.0"
    }, 
    "output_ports": {
      "block_info": {
        "home": "/Users/jfischer/apps/blox/si_file_mongo__1_0"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "__apache_solr_jetty_server__4_1__0", 
        "key": {
          "name": "apache-solr-jetty-server", 
          "version": "4.1"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "__si_utils__1_0__1", 
        "key": {
          "name": "si_utils", 
          "version": "1.0"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "__datablox_framework__1_0__0", 
        "key": {
          "name": "datablox-framework", 
          "version": "1.0"
        }, 
        "port_mapping": {
          "datablox_framework": "datablox_framework"
        }
      }
    ], 
    "id": "si-solr-index", 
    "input_ports": {
      "datablox_framework": {
        "BLOXPATH": "/Users/jfischer/apps/blox", 
        "caretaker_exe": "/Users/jfischer/apps/python/bin/datablox-caretaker", 
        "loader_exe": "/Users/jfischer/apps/python/bin/datablox-loader"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "si-solr-index", 
      "version": "1.0"
    }, 
    "output_ports": {
      "block_info": {
        "home": "/Users/jfischer/apps/blox/si_solr_index__1_0"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }, 
  {
    "config_port": {}, 
    "environment": [
      {
        "id": "__si_utils__1_0__1", 
        "key": {
          "name": "si_utils", 
          "version": "1.0"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "__datablox_fileserver__1_0__0", 
        "key": {
          "name": "datablox-fileserver", 
          "version": "1.0"
        }, 
        "port_mapping": {}
      }, 
      {
        "id": "__datablox_framework__1_0__0", 
        "key": {
          "name": "datablox-framework", 
          "version": "1.0"
        }, 
        "port_mapping": {
          "datablox_framework": "datablox_framework"
        }
      }
    ], 
    "id": "si-file-crawler", 
    "input_ports": {
      "datablox_framework": {
        "BLOXPATH": "/Users/jfischer/apps/blox", 
        "caretaker_exe": "/Users/jfischer/apps/python/bin/datablox-caretaker", 
        "loader_exe": "/Users/jfischer/apps/python/bin/datablox-loader"
      }
    }, 
    "inside": {
      "id": "master-host", 
      "key": {
        "name": "mac-osx", 
        "version": "10.6"
      }, 
      "port_mapping": {
        "host": "host"
      }
    }, 
    "key": {
      "name": "si-file-crawler", 
      "version": "1.0"
    }, 
    "output_ports": {
      "block_info": {
        "home": "/Users/jfischer/apps/blox/si_file_crawler__1_0"
      }
    }, 
    "peers": [], 
    "properties": {
      "installed": true
    }
  }
]
"""

_requested_new_resources = """
[
  {"id":"master-host",
     "key": {"name":"dynamic-host", "version":"*"}
  },
  {
    "id": "apache-tomcat",
    "key": {"name":"apache-tomcat", "version":"6.0"},
    "config_port": {
      "manager_port": 8080
    },
    "inside": {
      "id": "master-host",
      "key": {"name":"dynamic-host", "version":"*"},
      "port_mapping": {"host": "host"}
    }
  },
  {
    "id": "jasper",
    "key": {"name":"jasper-reports-server", "version":"4.2"},
    "inside": {
      "id": "apache-tomcat",
      "key": {"name":"apache-tomcat", "version":"6.0"},
      "port_mapping": {"tomcat": "tomcat"}
    }
  },
  {
    "config_port": {
      "JAVA_HOME": "/System/Library/Frameworks/JavaVM.framework/Versions/CurrentJDK/Home"
    }, 
    "id": "java_virtual_machine_macosx__1_6__6", 
    "inside": {
      "id": "master-host", 
      "key": {"name":"dynamic-host", "version":"*"},
      "port_mapping": {"host": "host"}
      },
    "key": {
      "name": "java-virtual-machine-macosx", 
      "version": "1.6"
    } 
  }  
]
"""
class TestMerge(unittest.TestCase):
    def test_merge_new_install_spec(self):
        """Test the merging of an existing install with new resources.
        """
        old_installed_resources = json.loads(_old_installed_resources)
        requested_new_resources = json.loads(_requested_new_resources)
        old_resources_by_id = {}
        for ri in old_installed_resources:
            ri_id = ri['id']
            old_resources_by_id[ri_id] = ri
        merged_spec = merge_new_install_spec_into_existing(requested_new_resources,
                                                           old_installed_resources,
                                                           logging.getLogger())
        new_resources_by_id = {}
        for ri in merged_spec:
            ri_id = ri['id']
            self.assertFalse(new_resources_by_id.has_key(ri_id), "multiple resources with id %s" % ri_id)
            new_resources_by_id[ri_id] = ri
        # check that master host resource was left unchanged
        self.assertTrue(new_resources_by_id.has_key('master-host'))
        mh_new = new_resources_by_id['master-host']
        mh_old = old_resources_by_id['master-host']
        self.assertEqual(mh_old, mh_new)
        # check that apache tomcat was added and points to master host
        self.assertTrue(new_resources_by_id.has_key('apache-tomcat'))
        tomcat = new_resources_by_id['apache-tomcat']
        self.assertEqual(tomcat['key'], {"name":"apache-tomcat", "version":"6.0"})
        self.assertEqual(tomcat['inside']['id'], 'master-host')
        self.assertEqual(tomcat['inside']['key'], mh_old['key'])
        # check that jasper was added
        self.assertTrue(new_resources_by_id.has_key('jasper'))
        # check that jvm id was renamed
        self.assertTrue(new_resources_by_id.has_key('java_virtual_machine_macosx__1_6__6'))
        old_jvm = old_resources_by_id['__java_virtual_machine_macosx__1_6__6']
        new_jvm = new_resources_by_id['java_virtual_machine_macosx__1_6__6']
        self.assertEqual(old_jvm['key'], new_jvm['key'])
        self.assertEqual(old_jvm['inside'], new_jvm['inside'])
        self.assertEqual(old_jvm['output_ports'], new_jvm['output_ports'])
        self.assertEqual(old_jvm['peers'], new_jvm['peers'])
        self.assertEqual(old_jvm['properties'], new_jvm['properties'])
        # check that the reference to the jvm was changed
        abstract_jvm = new_resources_by_id["__java_virtual_machine_abstract__1_6__4"]
        jvm_ref = abstract_jvm['environment'][0]
        self.assertEqual(jvm_ref['id'], 'java_virtual_machine_macosx__1_6__6')
        
        

if __name__ == '__main__':
    formatter = logging.Formatter("[%(levelname)s][%(name)s] %(message)s")
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    unittest.main()

"""Tests for preprocess_resources.py
"""

import sys
import os
import os.path
import unittest
import json
import logging
logger = logging.getLogger(__name__)

import fixup_python_path
import engage_file_layout
from engage.utils.file import mangle_resource_key, TempDir
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


if __name__ == '__main__':
    formatter = logging.Formatter("[%(levelname)s][%(name)s] %(message)s")
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    unittest.main()

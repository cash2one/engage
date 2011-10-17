import os.path
import json
import unittest
from django_file_layout import *

class TestDjangoFileLayout(unittest.TestCase):
    def setUp(self):
        from engage_django_sdk.version import VERSION
        from engage_django_sdk.packager.django_config import DjangoConfig
        self.dc = DjangoConfig({"product":"test app", "product_version":"v1",
                                "django_settings_module":"test_app.settings",
                                "python_path_subdirectory":"",
                                "version":VERSION,
                                "media_root_subdir":"/media",
                                "media_url_path":"/media",
                                "static_url_path":"/static"})
        self.fl = create_file_layout(self.dc, "test_app", "/home/test",
                                     "/home/python/bin/django_admin.py",
                                     "localhost", "8002")

    def test_construction(self):
        self.assertEqual(self.fl.get_app_dir_path(), "/home/test/test_app")
        self.assertEqual(self.fl.get_deployed_settings_module(),
                         "test_app.deployed_settings")
        self.assertEqual(self.fl.get_app_settings_module(),
                         "test_app.settings")
        self.assertEqual(self.fl.get_settings_file_directory(),
                         "/home/test/test_app")
        self.assertEqual(self.fl.get_python_path(),
                         "/home/test:/home/test/test_app")
        self.assertEqual(self.fl.get_django_admin_py(),
                         "/home/python/bin/django_admin.py")

    def test_json_roundtrip(self):
        json = self.fl.to_json()
        fl2 = create_file_layout_from_json(json)


if __name__ == '__main__':
    unittest.main()

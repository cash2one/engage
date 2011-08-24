import unittest
import os
import os.path
import sys

from generate_settings import *

class TestGenerateSettings(unittest.TestCase):
    """Unit tests for the generate_settings function.
    """
    def _make_py_file(self, parent_dir, name, contents="# \n"):
        with open(os.path.join(parent_dir, name), "w") as f:
            f.write(contents)

    def setUp(self):
        """We set up a sample application directory layout in a temp directory.
        This temp directory is deleted in the tearDown method so that we don't
        leave a mess around.
        """
        import tempfile
        self.temp_dir = tempfile.mkdtemp()
        self.app_dir_path = os.path.join(self.temp_dir, "app_dir")
        os.mkdir(self.app_dir_path)
        self.settings_file_dir = os.path.join(self.app_dir_path, "settings_file_dir")
        os.mkdir(self.settings_file_dir)
        self._make_py_file(self.settings_file_dir, "__init__.py")
        self._make_py_file(self.settings_file_dir, "settings.py")
        self.django_settings_module = "settings_file_dir.settings"
        self.saved_sys_path = sys.path

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
        sys.path = self.saved_sys_path

    def assertFileExists(self, filepath):
        self.assertTrue(os.path.exists(filepath), "%s is missing" % filepath)

    def assertModuleHasSetting(self, module, setting):
        self.assertTrue(hasattr(module, setting), "Module missing setting %s" % setting)

    def test_generate_settings(self):
        ops = generate_settings_file(self.app_dir_path, self.django_settings_module, [])
        self.assertFileExists(os.path.join(self.settings_file_dir, "engage_settings.py"))
        self.assertFileExists(os.path.join(self.settings_file_dir, "deployed_settings.py"))
        sys.path = [self.app_dir_path] + sys.path
        settings_module = __import__("settings_file_dir.deployed_settings")
        self.assertModuleHasSetting(settings_module.deployed_settings, "DATABASES")


if __name__ == '__main__':
    unittest.main()


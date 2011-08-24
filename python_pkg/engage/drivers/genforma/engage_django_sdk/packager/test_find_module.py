import unittest
import os
import os.path

from find_module import *


class TestFindPythonModule(unittest.TestCase):
    def _make_py_file(self, parent_dir, name):
        with open(os.path.join(parent_dir, name), "w") as f:
            f.write("# \n")

    def setUp(self):
        import tempfile
        self.temp_dir = tempfile.mkdtemp()
        self.w_dir = os.path.join(self.temp_dir, "w")
        os.mkdir(self.w_dir)
        self.x_dir = os.path.join(self.w_dir, "x")
        os.mkdir(self.x_dir)
        self._make_py_file(self.x_dir, "__init__.py")
        self.y_dir = os.path.join(self.x_dir, "y")
        os.mkdir(self.y_dir)
        self._make_py_file(self.y_dir, "__init__.py")
        self._make_py_file(self.y_dir, "z.py")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_find_from_temp_dir(self):
        """Check for x.y.z from temp_dir. This should return tmpdir/w.
        """
        res = find_python_module("x.y.z", self.temp_dir)
        self.assertEqual(res, self.w_dir)

    def test_find_from_w(self):
        """Check for x.y.z from w. This should return tmpdir/w.
        """
        res = find_python_module("x.y.z", self.w_dir)
        self.assertEqual(res, self.w_dir)

    def test_find_from_x(self):
        """Check for x.y.z from x. This should return tmpdir/w
        """
        res = find_python_module("x.y.z", self.x_dir)
        self.assertEqual(res, self.w_dir)

    def test_find_z_from_y(self):
        """Check for z from y. This should return tmpdir/w/x/y.
        """
        res = find_python_module("z", self.y_dir)
        self.assertEqual(res, self.y_dir)

    def test_find_from_y(self):
        """Check for x.y.z from y. This should return None.
        """
        res = find_python_module("x.y.z", self.y_dir)
        self.assertEqual(res, None)

    def test_find_bogus_from_w(self):
        """Check for a.b.c from temp_dir. This should return None"""
        res = find_python_module("a.b.c", self.temp_dir)
        self.assertEqual(res, None)


if __name__ == '__main__':
    unittest.main()


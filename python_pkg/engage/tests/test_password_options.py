"""Test the handling of password command line options and the password db.
"""
import os
import os.path
import sys
import tempfile
import logging
import unittest


import test_common as tc

join = os.path.join

logger = logging.getLogger(__name__)

install_spec = """
[
  {"id":"master-host",
     "key": {"name":"dynamic-host", "version":"*"}
  },
  {"id":"test",
   "key":{"name":"test-resource", "version":"1.0"},
   "inside": {
     "id":"master-host",
     "key": {"name":"dynamic-host", "version":"*"},
     "port_mapping":{"host":"host"}
   }
 }
]
"""

def _assert(cond, msg):
    if not cond:
        raise Exception(msg)

def setup_environment():
    deploy_dir = tc.get_randomized_deploy_dir('test_password_')
    rc = tc.bootstrap(deploy_dir)
    _assert(rc==0, "Bootstrap of %s failed" % deploy_dir)
    install_spec_file = join(deploy_dir, "install_spec.json")
    with open(install_spec_file, "wb") as f:
        f.write(install_spec)
    return deploy_dir


def _cleanup_files(deploy_dir):
    def rm(subpath):
        path = join(deploy_dir, subpath)
        if os.path.exists(path):
            os.remove(path)
    rm("config/installed_resources.json")
    rm("config/master.pw")
    rm("config/input_password.txt")
    rm("config/pw_repository")
    rm("config/pw_salt")

        
class TestPasswordOptions(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        unittest.TestCase.__init__(self, *args, **kwargs)
        self.dd = None # deployment directectory
        self.isf = None # install script file
        self.master_pw_file = None # the official master password file
        self.input_pw_file = None # alternative place for pw file

    def setUp(self):
        if not self.dd:
            logger.info("Bootstrapping deployment directory")
            self.dd = setup_environment()
            self.isf = join(self.dd, "install_spec.json")
            self.master_pw_file = join(self.dd, "config/master.pw")
            self.input_pw_file = join(self.dd, "config/input_password.txt")
            self.svcctl_exe = join(self.dd, "engage/bin/svcctl")
            logger.info("Deployment directory is at %s" % self.dd)
        else:
            logger.info("Reusing existing deployment directory")

    def tearDown(self):
        if self.dd:
            _cleanup_files(self.dd)

    def test_master_file_generation(self):
        dd = self.dd; isf = self.isf; master_pw_file = self.master_pw_file
        input_pw_file = self.input_pw_file; assertTrue=self.assertTrue
        svcctl_exe = self.svcctl_exe
        
        with open(self.input_pw_file, "w") as f:
            f.write("test")
        opts="--generate-random-passwords --master-password-file=%s" % \
              input_pw_file
        logger.info("Testing deployer with options %s" % opts)
        rc = tc.deployer(dd, isf, opts=opts)
        assertTrue(rc==0, "Deployer failed, return code was %d" % rc)
        assertTrue(os.path.exists(master_pw_file),
                   "Deployer ran, but did not generate master password file %s" %
                   master_pw_file)
        rc = tc.shell("%s status" % svcctl_exe)
        _assert(rc==0, "svcctl failed, return code was %d" % rc)

    def test_suppress_master_password_file(self):
        dd = self.dd; isf = self.isf; master_pw_file = self.master_pw_file
        input_pw_file = self.input_pw_file; assertTrue=self.assertTrue
        svcctl_exe = self.svcctl_exe
        
        with open(input_pw_file, "w") as f:
            f.write("test2")
        opts="--generate-random-passwords --suppress-master-password-file --master-password-file=%s" % \
              input_pw_file
        logger.info("Testing deployer with options %s" % opts)
        rc = tc.deployer(dd, isf, opts=opts)
        assertTrue(rc==0, "Deployer failed, return code was %d" % rc)
        assertTrue(not os.path.exists(master_pw_file),
               "Deployer ran, but generated master password file %s even when --suppress-master-password-file was set" %
               master_pw_file)
        rc = tc.shell("%s --master-password-file=%s status" %
                      (svcctl_exe, input_pw_file))
        assertTrue(rc==0, "svcctl failed, return code was %d" % rc)
        assertTrue(not os.path.exists(master_pw_file),
                "svcctl seems to have created a master password file at %s" %
                master_pw_file)
        
    def test_master_file_use(self):
        """If the master password file already exists, it should be
        used by the deployer.
        """
        dd = self.dd; isf = self.isf; master_pw_file = self.master_pw_file
        assertTrue=self.assertTrue
        svcctl_exe = self.svcctl_exe
        
        with open(master_pw_file, "w") as f:
            f.write("test3")
        opts="--generate-random-passwords"
        logger.info("Testing deployer with options %s" % opts)    
        rc = tc.deployer(dd, isf, opts=opts)
        assertTrue(rc==0, "Deployer failed, return code was %d" % rc)
        assertTrue(os.path.exists(master_pw_file),
                   "Deployer ran, but master password file is not at %s" %
                   master_pw_file)
        rc = tc.shell("%s status" % svcctl_exe)
        assertTrue(rc==0, "svcctl failed, return code was %d" % rc)
        assertTrue(os.path.exists(master_pw_file),
                   "after svcctl run, no longer a master password file at %s" %
                   master_pw_file)

    def test_master_file_overwrite(self):
        """Test the case where the master password file already exists,
        but contains a stale value. Should be overwritten during the deployment
        with the current value.
        """
        dd = self.dd; isf = self.isf; master_pw_file = self.master_pw_file
        input_pw_file = self.input_pw_file; assertTrue=self.assertTrue
        svcctl_exe = self.svcctl_exe
        
        with open(master_pw_file, "w") as f:
            f.write("test3") # bogus old file
        with open(input_pw_file, "w") as f:
            f.write("test4")
        opts="--generate-random-passwords --master-password-file=%s" % \
              input_pw_file
        logger.info("Testing deployer with options %s" % opts)
        rc = tc.deployer(dd, isf, opts=opts)
        assertTrue(rc==0, "Deployer failed, return code was %d" % rc)
        assertTrue(os.path.exists(master_pw_file),
                   "Deployer ran, but master password file is not at %s" %
                   master_pw_file)
        with open(master_pw_file, "r") as f:
            new_pw_data = f.read().rstrip()
        self.assertEqual("test4", new_pw_data,
                         "Password file %s should have been overwritten, but wasn't"%
                         master_pw_file)
        rc = tc.shell("%s status" % svcctl_exe)
        assertTrue(rc==0, "svcctl failed, return code was %d" % rc)
    
    
if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    h = logging.StreamHandler(sys.stdout)
    h.setLevel(logging.DEBUG)
    formatter = logging.Formatter("[%(name)s] %(message)s")
    h.setFormatter(formatter)
    logger.addHandler(h)
    unittest.main()

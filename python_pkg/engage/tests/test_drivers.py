import os
import os.path
import sys
import re
import imp
import string
import logging
import getpass

try:
    import engage
except:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    import engage

import engage.tests.test_common as tc
import engage.drivers
import engage.engine.cmdline_install as cmdline_install
import engage.utils.system_info as system_info
import engage.utils.log_setup as log_setup
import engage.engine.run_driver as run_driver

DRIVER_TEST_PREFIX = "drivertest"

def driver_filename_to_tst_name(filepath):
    filename = os.path.basename(filepath)
    m = driver_re.match(filename)
    if m:
        return m.group(1)
    else:
        return os.path.basename(os.path.dirname(filepath))


class DriverTestError(Exception):
    def __init__(self, testfile, msg):
        test = driver_filename_to_tst_name(testfile)
        Exception.__init__(self, "%s (at %s): %s" % (test, testfile, msg))


def find_driver_tsts(basedir):
    matches = []
    for (dirpath, dirnames, filenames) in os.walk(basedir):
        for f in filenames:
            if f.startswith(DRIVER_TEST_PREFIX) and f.endswith(".py"):
                matches.append(os.path.join(dirpath, f))
    return matches

driver_re = re.compile(re.escape(DRIVER_TEST_PREFIX) + "_*([A-Za-z0-9][_A-Za-z0-9]*)" + re.escape(".py"))


def get_module(test_path):
    module_name = os.path.basename(test_path)[0:-3]
    target_name = DRIVER_TEST_PREFIX + "_" + driver_filename_to_tst_name(test_path)
    (file, pathname, description) = imp.find_module(module_name,
                                                    [os.path.dirname(test_path)])
    try:
        return imp.load_module(target_name, file, pathname, description)
    finally:
        file.close()


def run_driver_tst(testfile, dh, hostname, username, logger, dry_run=True,
                   sudo_password=None):
    test = driver_filename_to_tst_name(testfile)
    if dry_run:
        logger.info("Testing driver %s" % test)
    else:
        logger.info("Running driver %s" % test)
    tm = get_module(testfile)
    if hasattr(tm, "get_install_script"):
        install_script_tmpl = string.Template(tm.get_install_script())
    elif hasattr(tm, "get_install_script_file"):
        install_script_tmpl_file = tm.get_install_script_file()
        if not os.path.exists(install_script_tmpl_file):
            raise DriverTestError(testfile,
                                  "Install script file %s does not exist" %
                                  install_script_tmpl_file)
        with open(install_script_tmpl_file) as itf:
            install_script_tmpl = string.Template(itf.read())
    else:
        raise DriverTestError(testfile,
                              "neither get_install_script() nor get_install_script_file() functions were defined")
    if not hasattr(tm, "resource_id"):
        raise DriverTestError(testfile,
                              "could not find resource_id property")
    config_dir = os.path.join(dh, "config")
    install_script_file = os.path.join(config_dir, "%s.install.script" % test)
    data = install_script_tmpl.substitute({"deployment_home": dh,
                                           "hostname": hostname,
                                           "username": username})
    with open(install_script_file, "wb") as of:
        of.write(data)
    if hasattr(tm, "get_password_data") and tm.get_password_data()!=None:
        import engage.utils.pw_repository as pwr
        pw_dict = tm.get_password_data()
        if not sudo_password:
            assert dry_run, "No sudo password, but in real install mode"
            sudo_password = "sudo_password_value" # make up a value
        pw_dict["GenForma/%s/sudo_password" % username] = sudo_password
        pw_repos = pwr.PasswordRepository("", data=pw_dict)
    else:
        pw_repos = None
    test_request = run_driver.TestRequest()
    args = ["--install-script-file=%s" % install_script_file,
            dh, tm.resource_id]
    if dry_run:
        args.insert(0, "--dry-run")
    test_request.process_args(args, pw_repos)
    (mgr, package) = test_request.setup()
    if dry_run:
        test_request.dry_run_test(mgr, package)
    else:
        test_request.run_test(mgr, package)
    logger.info("test %s successful" % test)


class TestRequest(object):
    def __init__(self):
        self.dh = None
        self.test_base_dir = None
        self.tests = None
        self.hostname = None
        self.username = None
        self.dry_run = True
        self.sudo_password = None
        
    def process_args(self, argv):
        from optparse import OptionParser
        parser = OptionParser()
        self.test_base_dir = os.path.dirname(engage.drivers.__file__)
        parser.add_option("--test-base-dir", dest="test_base_dir", default=None,
                          help="Base directory for test discovery (defaults to %s)" %
                                self.test_base_dir)
        parser.add_option("-l", "--list-tests", dest="list_tests", default=False,
                          action="store_true",
                          help="list driver tests that were found, but do not run them")
        parser.add_option("-t", "--tests", dest="tests", default=None,
                          help="List of tests to run (defaults to all)")
        parser.add_option("--deployment-home", dest="deployment_home", default=None,
                          help="Directory for deployment home (defaults to random)")
        parser.add_option("-r", "--run-driver", dest="run_driver", default=False,
                          action="store_true",
                          help="run the driver(s) in real install mode instead of dry_run mode")
        (opts, args) = parser.parse_args(argv)
        if opts.test_base_dir:
            self.test_base_dir = opts.test_base_dir
        self.test_base_dir = os.path.abspath(os.path.expanduser(self.test_base_dir))
        all_tests = find_driver_tsts(self.test_base_dir)
        if len(all_tests)==0:
            raise Exception("No driver tests found, discovery base directory was %s"
                            % self.test_base_dir)
        if opts.tests:
            test_names_to_files = {}
            for testfile in all_tests:
                test_names_to_files[driver_filename_to_tst_name(testfile)] = testfile
            self.tests = []
            for test in opts.tests.split(","):
                if not test_names_to_files.has_key(test):
                    raise Exception("Requested test %s not found" % test)
                self.tests.append(test_names_to_files[test])
        else:
            self.tests = all_tests
                
        if opts.deployment_home:
            self.dh = os.path.abspath(os.path.expanduser(ops.deployment_home))
        else:
            self.dh = tc.get_randomized_deploy_dir("test_drivers_")


        sys_info = system_info.get_machine_info(cmdline_install.os_choices)
        self.hostname = sys_info['hostname']
        self.username = sys_info['username']
        
        if opts.list_tests:
            print [driver_filename_to_tst_name(test) for test in self.tests]
            sys.exit(0)

        if opts.run_driver:
            self.dry_run = False
            self.sudo_password = getpass.getpass("Sudo password:")

    def setup(self):
        tc.bootstrap(self.dh)

    def run(self, testfile, logger):
        logger.debug("Deployment home is %s" % self.dh)
        run_driver_tst(testfile, self.dh, self.hostname, self.username, logger, dry_run=self.dry_run,
                       sudo_password=self.sudo_password)

## def make_tst_generator():
##     req = TestRequest()
##     logger = logging.getLogger("test_drivers")
##     def generator():
##         for testfile in req.tests:
##             fn = lambda tf: req.run(tf, logger)
##             fn.description = driver_filename_to_tst_name(testfile)
##             yield fn, testfile
##     def setup():
##         req.process_args([])
##         req.setup()
##     generator.setup = setup
##     def teardown():
##         pass
##     generator.teardown = teardown
##     return generator
##
## test_drivers_generator = make_tst_generator()


def test_drivers_generator():
    logger = log_setup.logger_for_repl("driver_test")
    #logger = logging.getLogger("test_drivers")
    req = TestRequest()
    req.process_args([])
    req.setup()
    for testfile in req.tests:
        fn = lambda tf: req.run(tf, logger)
        fn.description = "driver:" + driver_filename_to_tst_name(testfile)
        yield fn, testfile

    
# if running from command line, we give the user more options
if __name__ == "__main__":
    req = TestRequest()
    req.process_args(sys.argv[1:])
    logger = log_setup.logger_for_repl("driver_test")
    req.setup()
    for testfile in req.tests:
        req.run(testfile, logger)
    sys.exit(0)

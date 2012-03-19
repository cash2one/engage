"""Tests for sudo handling of engage.utils.process and engage.drivers.action.
There are three modes that we can be running in:
 1. If running as root, sudo actions will be transparently run directly
 2. If running as normal user, but no password is needed for sudo access,
    process utilities will call sudo -n.
 3. If running as normal user, and a sudo password is neeed, process
    utilities will call sudo -p "" -S and provide the password via stdin.

If an sudo password is required, the tests cannon be run under Nose - they will
only be available as a command line script. For the other two cases, the tests
will be run.
"""

import sys
import os.path
import getpass
import logging
import time
import optparse
import tempfile

try:
    import engage
except:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    import engage

import engage.utils.process as process
import engage.drivers.action as action
from engage.drivers.action import _check_file_exists
import engage.tests.test_common as tc

logger = logging.getLogger()

class TestError(Exception):
    pass

def _assert(pred, msg):
    if not pred:
        raise TestError(msg)

server_log_dir = None

def tst_run_program(sudo_password):
    logger.debug("tst_run_program() Starting")
    process.run_sudo_program(["/bin/ls", "/"], sudo_password,
                             logger)
    process.run_sudo_program(["/bin/ls", "/"], sudo_password,
                             logger, user=getpass.getuser())
    logger.debug("tst_run_program() Successful")

def tst_cat_file(sudo_password):
    """This test relies on the fact that sudo_cat_file() doesn't actually
    check the file permissions, but just returns it"""
    logger.debug("tst_cat_file() Starting")
    data = process.sudo_cat_file(__file__, logger, sudo_password)
    _assert(len(data)>0,
            "Should have gotten length of this test file, instead got 0")
    logger.debug("tst_cat_file() Successful")

def tst_run_sudo_program_and_scan_results(sudo_password):
    logger.debug("tst_run_sudo_program_and_scan_results() Starting")
    cmd = ["/bin/ls", "/"]
    re_map={"bin_dir":"^bin$"}
    (rc, result_map) = process.run_sudo_program_and_scan_results(cmd, re_map,
                                                                 logger,
                                                                 sudo_password,
                                                                 log_output=True)
    _assert(rc==0, "Return code of /bin/ls was %d" % rc)
    _assert(result_map["bin_dir"]==True,
            "Expecting bin_dir regexp to be found, got %s" %
            result_map["bin_dir"])
    logger.debug("tst_run_sudo_program_and_scan_results() Successful")

def tst_sudo_run_server(sudo_password):
    """Tests of sudo_run_server(), sudo_check_server_status,
       and sudo_stop_server_process()
    """
    logger.debug("tst_sudo_run_server() Starting")
    if server_log_dir:
        td = server_log_dir
        if not os.path.exists(server_log_dir):
            os.makedirs(server_log_dir)
    else:
        td = tempfile.mkdtemp(prefix="test_sudo")
    try:
        pidfile = os.path.join(td, "server.pid")
        logger.debug("pidfile=%s" % pidfile)
        cwd = os.path.abspath(os.path.dirname(__file__))
        process.sudo_run_server([sys.executable,
                                 os.path.abspath(__file__), "--run-server",
                                 pidfile],
                                {}, os.path.join(td, "server.log"),
                                logger, sudo_password,
                                cwd=cwd)
        found = False
        for i in range(5):
            pid = process.sudo_check_server_status(pidfile, logger,
                                                   sudo_password)
            if pid!=None:
                logger.info("Verified that server started. Pid is %d" % pid)
                found = True
                break
            else:
                time.sleep(5)
        _assert(found, "Test server processs not found after 25 seconds")
        process.sudo_stop_server_process(pidfile, logger, "test",
                                         sudo_password)
        found = True
        for i in range(5):
            pid = process.sudo_check_server_status(pidfile, logger,
                                                   sudo_password)
            if pid==None:
                logger.info("Verified that server stopped")
                found = False
                break
            else:
                time.sleep(5)
        _assert(not found, "Test server processs not stopped after 25 seconds")
            
    finally:
        if not server_log_dir:
            process.sudo_rm(td, sudo_password, logger)
    logger.debug("tst_sudo_run_server() Successful")

class LsAction(action.SudoAction):
    """This is a test action that just runs /bin/ls under the regular user
    or super user.
    """
    NAME="LsAction"
    def __init__(self, ctx):
        super(LsAction, self).__init__(ctx)

    def run(self, path):
        rc = process.run_and_log_program(["/bin/ls", path],
                                         {}, self.ctx.logger)
        if rc!=0:
            raise Exception("Bad rc from /bin/ls: %d" % rc)

    def dry_run(self, path):
        pass

    def sudo_run(self, path):
        process.run_sudo_program(["/bin/ls", path],
                                  self.ctx._get_sudo_password(self),
                                  self.ctx.logger)

class CatValueAction(action.SudoValueAction):
    NAME = "CatValueAction"
    def __init__(self, ctx):
        super(CatValueAction, self).__init__(ctx)

    def run(self, path, mode="b"):
        _check_file_exists(path, self)
        with open(path, "r" + mode) as f:
            data = f.read()
        return data

    def sudo_run(self, path, mode="b"):
        return process.sudo_cat_file(path, self.ctx.logger,
                                     self.ctx._get_sudo_password(self))

    def dry_run(self, path, mode="b"):
        pass


def _make_context(testname, sudo_password):
    ctx = action.Context({"id": testname}, logger, __file__,
                         lambda : sudo_password,
                         dry_run=False)
    return ctx

def tst_r_su(sudo_password):
    """Test the r_su() method of the action module's Context object
    """
    ctx = _make_context("tst_r_su", sudo_password)
    ctx.r(LsAction, "/")
    ctx.r_su(LsAction, "/")

def tst_rv_su(sudo_password):
    ctx = _make_context("tst_rv_su", sudo_password)
    d1 = ctx.rv(CatValueAction, __file__)
    d2 = ctx.rv_su(CatValueAction, __file__)
    _assert(d1 == d2, "Data from su and regular file reading are different")
    

ALL_TESTS = [tst_run_program, tst_cat_file,
             tst_run_sudo_program_and_scan_results,
             tst_sudo_run_server, tst_r_su, tst_rv_su]


def test_sudo_generator():
    """Generate sudo tests for Nose. If a pasword is required (meaning we cannot
    run non-interactively), don't generate any tests.
    """
    if process.SUDO_PASSWORD_REQUIRED==True:
        tests = []
    else:
        tests = ALL_TESTS
    for test in tests:
        yield test, None


def run_server(pidfile):
    logger.info("Starting server")
    with open(pidfile, "w") as f:
        f.write("%d" % os.getpid())
    logger.debug("Wrote pidfile %s" % pidfile)
    while True:
        time.sleep(5)
        logger.debug("Server woke up")
    return 0

if __name__ == "__main__":
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    h = logging.StreamHandler(sys.stdout)
    h.setLevel(logging.DEBUG)
    root_logger.addHandler(h)

    usage = "%prog [options] test1 test2...\n  If not tests specified, all are run"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("--run-server", default=False, action="store_true",
                      help="If specified, start a test server instead of running the tests")
    parser.add_option("--server-log-dir", default=None,
                      help="If specified, use the directory for server logfiles rather than a temporary directory")
    (options, args) = parser.parse_args()
    if options.run_server and options.server_log_dir!=None:
        parser.error("Option --server-log-dir not valid with --run-server")
    if options.run_server:
        if len(args)!=1:
            parser.error("Need to specify pidfile")
        sys.exit(run_server(args[0]))

    if options.server_log_dir:
        server_log_dir = os.path.abspath(os.path.expanduser(options.server_log_dir))
        
    if len(args)==0:
        tests = ALL_TESTS
    else:
        test_names_to_functions = {}
        for tf in ALL_TESTS:
            test_names_to_functions[tf.__name__] = tf
        tests = []
        all_test_names = [t.__name__ for t in ALL_TESTS]
        for test in args:
            if not test_names_to_functions.has_key(test):
                parser.error("Unknown test %s. Valid tests are: %s" %
                             (test, ', '.join(all_test_names)))
            tests.append(test_names_to_functions[test])
    
    if process.SUDO_PASSWORD_REQUIRED==True:
        sudo_password = getpass.getpass("Sudo Password:")
    else:
        sudo_password = None

    logger.info("Starting sudo tests, SUDO_PASSWORD_REQUIRED=%s" %
                process.SUDO_PASSWORD_REQUIRED)
    for test in tests:
        test(sudo_password)
    logger.info("sudo tests successful")
    sys.exit(0)

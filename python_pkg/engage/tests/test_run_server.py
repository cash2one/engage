"""
Tests server start and stop functionality.
"""

import sys
import os.path
import getpass
import logging
import time
import optparse
import tempfile
import shutil

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


def test_run_server():
    """Tests of run_server(), check_server_status,
       and stop_server_process()
    """
    logger.debug("test_run_server() Starting")
    if server_log_dir:
        td = server_log_dir
        if not os.path.exists(server_log_dir):
            os.makedirs(server_log_dir)
    else:
        td = tempfile.mkdtemp(prefix="test_run_server")
    try:
        pidfile = os.path.join(td, "server.pid")
        logger.debug("pidfile=%s" % pidfile)
        cwd = os.path.abspath(os.path.dirname(__file__))
        process.run_server([sys.executable,
                            os.path.abspath(__file__), "--run-server"],
                           {}, os.path.join(td, "server.log"),
                           logger, pidfile,
                           cwd=cwd)
        found = False
        for i in range(5):
            pid = process.check_server_status(pidfile, logger, "test")
            if pid!=None:
                logger.info("Verified that server started. Pid is %d" % pid)
                found = True
                break
            else:
                time.sleep(5)
        _assert(found, "Test server processs not found after 25 seconds")
        process.stop_server_process(pidfile, logger, "test")
        found = True
        for i in range(5):
            pid = process.check_server_status(pidfile, logger, "test")
            if pid==None:
                logger.info("Verified that server stopped")
                found = False
                break
            else:
                time.sleep(5)
        _assert(not found, "Test server processs not stopped after 25 seconds")
            
    finally:
        if not server_log_dir:
            shutil.rmtree(td)
    logger.debug("test_run_server() Successful")



def _make_context(testname):
    ctx = action.Context({"id": testname}, logger, __file__,
                         sudo_password_fn=None,
                         dry_run=False)
    return ctx

def test_start_server_actions():
    logger.debug("test_start_server_actions() Starting")
    ctx = _make_context("test_start_server_actions")
    if server_log_dir:
        td = server_log_dir
        if not os.path.exists(server_log_dir):
            os.makedirs(server_log_dir)
    else:
        td = tempfile.mkdtemp(prefix="test_start_server_actions")
    try:
        pidfile = os.path.join(td, "server.pid")
        logfile = os.path.join(td, "server.log")
        ctx.r(action.start_server,
              [sys.executable, os.path.abspath(__file__),
               "--run-server"], logfile, pidfile)
        ctx.check_poll(5, 2.0, lambda is_running: is_running,
                       action.get_server_status, pidfile)
        ctx.r(action.stop_server, pidfile)
        ctx.check_poll(5, 2.0, lambda is_running: not is_running,
                       action.get_server_status, pidfile)
            
    finally:
        if not server_log_dir:
            shutil.rmtree(td)
    logger.debug("test_start_server_actions() Successful")
        
          


ALL_TESTS = [test_run_server,test_start_server_actions]



def run_server():
    logger.info("Starting server")
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
        if len(args)!=0:
            parser.error("run_server does not take any args")
        sys.exit(run_server())

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
    

    logger.info("Starting run_server tests")
    for test in tests:
        test()
    logger.info("run_server tests successful")
    sys.exit(0)

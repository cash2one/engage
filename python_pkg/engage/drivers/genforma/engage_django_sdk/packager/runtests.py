#! /usr/bin/env python

import sys
import os
import os.path
from subprocess import Popen
import traceback
from optparse import OptionParser
import tempfile
import shutil
import json
import logging

from generate_settings import simulated_install
from validation_results import SETTINGS_VALIDATION_ERROR_RC, SUCCESS_RC
from __init__ import run_installed_tests_as_subprocess


logger = logging.getLogger()

verbose = False

class TestException(Exception):
    pass


def system(command):
    """Run a command in the shell. If the command fails, we thow an
    exception.
    """
    p = Popen(command, shell=True)
    (pid, exit_status) = os.waitpid(p.pid, 0)
    rc = exit_status >> 8 # the low byte is the signal ending the proc
    if rc != 0:
        raise TestException("Command execution failed: '%s'" % command)


PACKAGE_MAIN=os.path.abspath(os.path.dirname(__file__))
PYTHON_EXE=sys.executable

def run_packager(args, expected_rc=0, package_cache_dir=None):
    """Run the packager in a subprocess. If the command does not exit with the
       expected return code, we thow an exception.
    """
    opts = []
    if verbose:
        opts.append("-v")
    if package_cache_dir:
        opts.append("--package-cache-dir=%s" % package_cache_dir)
    command = "%s %s %s" % (PYTHON_EXE, PACKAGE_MAIN, " ".join(opts+args))
    p = Popen(command, shell=True)
    (pid, exit_status) = os.waitpid(p.pid, 0)
    rc = exit_status >> 8 # the low byte is the signal ending the proc
    if rc != expected_rc:
        raise TestException("Packager execution failed: '%s', rc was %s, expecting %s" % (command, rc, expected_rc))


def _run_validation_tests(archive_file, app_module_name, tmpdir,
                          package_cache_dir=None):
        run_packager(["validate-safe", archive_file],
                     package_cache_dir=package_cache_dir)
        run_packager(["validate-full", archive_file],
                     package_cache_dir=package_cache_dir)
    
def test_directory(dir_path, app_module_name, options):
    tmpdir = tempfile.mkdtemp(suffix="-engage-test")
    try:
        archive_file = os.path.join(tmpdir, "test_archive.tgz")
        if options.prepare_negative_test:
            run_packager(["prepare-dir", dir_path, app_module_name, archive_file],
                         expected_rc=SETTINGS_VALIDATION_ERROR_RC,
                         package_cache_dir=options.package_cache_dir)
            logger.info("Negative tests for prepare-dir successful.")
        else:
            run_packager(["prepare-dir", dir_path, app_module_name, archive_file],
                         package_cache_dir=options.package_cache_dir)
            _run_validation_tests(archive_file, app_module_name, tmpdir,
                                  package_cache_dir=options.package_cache_dir)
            logger.info("Tests for prepare-dir successful.")
        return 0
    finally:
        shutil.rmtree(tmpdir)


def test_archive(archive_file, app_module_name, options):
    tmpdir = tempfile.mkdtemp(suffix="-engage-test")
    try:
        if options.prepare_negative_test:
            run_packager(["prepare-archive", archive_file, app_module_name],
                         expected_rc=SETTINGS_VALIDATION_ERROR_RC,
                         package_cache_dir=options.package_cache_dir)
            logger.info("Negative tests for prepare-archive successful.")
        else:
            run_packager(["prepare-archive", archive_file, app_module_name],
                         package_cache_dir=options.package_cache_dir)
            _run_validation_tests(archive_file, app_module_name, tmpdir,
                                  package_cache_dir=options.package_cache_dir)
            logger.info("Tests for prepare-archive successful.")
        return 0
    finally:
        shutil.rmtree(tmpdir)



def main(argv):
    try:
        parser = OptionParser(usage="%prog [options] django_archive_file django_settings_module\n%prog [options] django_app_directory django_settings_module")
        parser.add_option("-n", "--prepare-negative-test", action="store_true",
                          dest="prepare_negative_test", default=False,
                          help="Prepare validation checks should fail")
        parser.add_option("-v", "--verbose", action="store_true",
                          dest="verbose", default=False,
                          help="Print debug output for packager")
        parser.add_option("--package-cache-dir", dest="package_cache_dir",
                          default=None,
                          help="Directory to check for local copies of packages")
        (options, args) = parser.parse_args()
        if len(args)!=2:
            parser.error("Expecting two arguments")
        global verbose
        verbose = options.verbose
        if verbose:
            LOG_LEVEL = logging.DEBUG
        else:
            LOG_LEVEL = logging.INFO

        logger.setLevel(LOG_LEVEL)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(LOG_LEVEL)
        logger.addHandler(handler)

        if os.path.isdir(args[0]):
            rc = test_directory(args[0], args[1], options)
        elif os.path.exists(args[0]):
            rc = test_archive(args[0], args[1], options)
        else:
            parser.error("File or directory %s does not exist" % args[0])
        return rc
    except TestException:
        (exc_type, exc_value, exc_traceback) = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, None, file=sys.stderr)
        logger.error("Tests failed due to TestException")
        return 1
    except SystemExit, c:
        sys.exit(c)
    except:
        (exc_type, exc_value, exc_traceback) = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stderr)
        logger.error("Tests failed due to unexpected exception of type %s, value was %s" % (exc_type, exc_value))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

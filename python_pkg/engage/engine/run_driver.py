"""Test a driver by itself.
"""
import sys
import os
import os.path
from optparse import OptionParser
import json
from itertools import ifilter

import fixup_python_path

import engage.utils.log_setup as log_setup
from engage.engine.engage_file_layout import get_engine_layout_mgr
from engage.engine.library import parse_library_files
from engage.drivers.resource_metadata import parse_resource_from_json
import engage.utils.file as fileutils

def _format_res_type(mgr):
    return "%s %s" % (mgr.metadata.key['name'], mgr.metadata.key['version'])

class TestRequest(object):
    def __init__(self):
        self.logger = log_setup.logger_for_repl("driver_test")
        self.options = None
        self.deployment_home = None
        self.file_layout = None
        self.install_script_file = None
        self.resource_id = None
        self.has_pw_file = None
        self.pw_database = None

    def process_args(self, argv, pw_database=None):
        usage = "usage: %prog [options] deployment_home resource_id"
        parser = OptionParser(usage=usage)
        parser.add_option("--dry-run", dest="dry_run",
                          default=False, action="store_true",
                          help="If specified, do a dry run of the resource.")
        parser.add_option("--install-script-file", dest="install_script_file",
                          default=None,
                          help="Name of install script file (defaults to <dh>/config/install.script)")
        (self.options, args) = parser.parse_args(args=argv)
        if len(args) != 2:
            parser.error("Expecting two arguments: deployment_home resource_id")
        self.deployment_home = os.path.abspath(os.path.expanduser(args[0]))
        if not os.path.exists(self.deployment_home):
            parser.error("Deployment home %s does not exist" % self.deployment_home)
        if self.options.install_script_file:
            self.install_script_file = self.options.install_script_file
        else:
            self.install_script_file = os.path.join(self.deployment_home,
                                                    "config/install.script")
        if not os.path.exists(self.install_script_file):
            parser.error("Install script file %s does not exist" %
                         self.install_script_file)
        self.resource_id = args[1]
        self.file_layout = get_engine_layout_mgr()
        if pw_database:
            self.pw_database = pw_database
        else:
            pw_file = os.path.join(self.deployment_home, "config/pw_repository")
            self.has_pw_file = os.path.exists(pw_file)
            if self.has_pw_file:
                self.logger.info("Found password repository at %s" % pw_file)
            else:
                self.logger.info("No password repository at %s" % pw_file)

    def setup(self):
        library = parse_library_files(self.file_layout)
        if self.pw_database:
            pw_database = self.pw_database
        elif not self.has_pw_file:
            import engage.utils.pw_repository as pw_repository
            pw_database = pw_repository.PasswordRepository("")
        else:
            pw_database = None # setup_context() will read the db
        import install_context
        install_context.setup_context(os.path.join(self.deployment_home,
                                                   "config"),
                                      False, library, pw_database)
        with open(self.install_script_file, "rb") as f:
            resource_list_json = json.load(f)
        rlist = [r for r in ifilter(lambda res: res["id"]==self.resource_id,
                                    resource_list_json)]
        if len(rlist)==0:
            raise Exception("Resource %s not found" % self.resource_id)
        if len(rlist)>1:
            raise Exception("Multiple instances of resource %s!" %
                            self.resource_id)
        resource = parse_resource_from_json(rlist[0])
        entry = library.get_entry(resource)
        resource_manager_class = entry.get_manager_class()
        if self.options.dry_run:
            mgr = resource_manager_class(resource, dry_run=True)
        else:
            mgr = resource_manager_class(resource)
        mgr.install_context = install_context
        return (mgr, entry.get_package())

    def run_test(self, mgr, package):
        """Do the real test"""
        self.logger.info("Running tests for resource %s, %s" % (mgr.id, _format_res_type(mgr)))
        if mgr.is_installed():
            self.logger.info("Resource %s already installed, running post-install validation" % mgr.id)
            mgr.validate_post_install()
        else:
            self.logger.info("Running preinstall validation for resource %s" % mgr.id)
            mgr.validate_pre_install()
            self.logger.info("Installing resource %s" % mgr.id)
            mgr.install(package)

        if mgr.is_service():
            if mgr.is_running():
                self.logger.info("Service %s already running" % mgr.id)
            else:
                self.logger.info("Starting service %s" % mgr.id)
                mgr.start()
                if not mgr.is_running():
                    raise Exception("Service %s was started but is_running() returns False" % mgr.id)
            self.logger.info("Stopping service %s" % mgr.id)
            mgr.stop()
            if mgr.is_running():
                raise Exception("Service %s was stopped but is_running() still returns True" % mgr.id)
        self.logger.info("Tests for resource %s completed successfully" % mgr.id)

    def dry_run_test(self, mgr, package):
        """Just call everything assuming dry run mode. Since we aren't actually making changes,
        we cannot rely on the maintainance of state across calls (e.g. whether a service is running).
        """
        self.logger.info("Running Dry Run tests for resource %s, %s" % (mgr.id, _format_res_type(mgr)))
        self.logger.info("[Dry Run] Calling resource %s, validate_pre_install()" % mgr.id)
        mgr.validate_pre_install()
        self.logger.info("[Dry Run] Calling resource %s, is_installed()" % mgr.id)
        mgr.is_installed()
        self.logger.info("[Dry Run] Calling resource %s, install()" % mgr.id)
        mgr.install(package)
        self.logger.info("[Dry Run] Calling resource %s, validate_post_install()" % mgr.id)
        mgr.validate_post_install()
        if mgr.is_service():
            self.logger.info("[Dry Run] Calling service %s, is_running()" % mgr.id)
            mgr.is_running()
            self.logger.info("[Dry Run] Calling service %s, start()" % mgr.id)
            mgr.start()
            self.logger.info("[Dry Run] Calling service %s, stop()" % mgr.id)
            mgr.stop()
        with fileutils.TempDir(dir=self.deployment_home) as td:
            self.logger.info("[Dry Run] Calling service %s, backup()" % mgr.id)
            mgr.backup(td.name)
            self.logger.info("[Dry Run] Calling service %s, restore()" % mgr.id)
            mgr.restore(td.name, package)
        with fileutils.TempDir(dir=self.deployment_home) as td:
            self.logger.info("[Dry Run] Calling service %s, uninstall()" % mgr.id)
            mgr.uninstall(td.name)
            
        self.logger.info("[Dry Run] Tests for resource %s completed successfully" % mgr.id)


def main(argv):
    test_request = TestRequest()
    test_request.process_args(argv)
    (mgr, package) = test_request.setup()
    if test_request.options.dry_run:
        test_request.dry_run_test(mgr, package)
    else:
        test_request.run_test(mgr, package)
    return 0

def call_from_console_script():
    sys.exit(main(sys.argv[1:]))

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python
import os
import os.path
import sys
from optparse import OptionParser
import shutil
import getpass

if sys.version_info[0]!=2 or sys.version_info[1]<6:
    raise Exception("Engage requires Python version 2.6 or 2.7, but upgrade was started with Python %d.%d (at %s)" %
                    (sys.version_info[0], sys.version_info[1], sys.executable))
import bootstrap
from engage.utils.log_setup import setup_engage_logger, parse_log_options, add_log_option
from engage.utils.process import run_and_log_program, run_sudo_program
import engage.engine.backup as backup

class UpgradeRequest(object):
    def __init__(self):
        self.options = None
        self.deployment_home = None
        self.config_dir = None
        self.engage_home = None
        self.engage_bin_dir = None
        self.log_directory = None
        self.application_archive = None
        self.master_pw = None
        
    def process_args(self, argv):
        usage = "usage: %prog [options] deployment_home"
        parser = OptionParser(usage=usage)
        add_log_option(parser)
        parser.add_option("--application-archive", "-a", dest="application_archive", action="store",
                          default=None,
                          help="If specified, override the application_archive property in config choices file with this value")        
        parser.add_option("-s", "--subproc", action="store_true", dest="subproc",
                          default=False, help="Run in subprocess mode, getting master password from standard input")
        parser.add_option("-p", "--python",
                          default=None,
                          help="Use the specified python executable as basis for Python virtual environments",
                          dest="python_exe")

        (self.options, args) = parser.parse_args(args=argv)
        if len(args) != 1:
            parser.error("Expecting exactly one argument, the deployment's home directory")
        self.deployment_home = os.path.abspath(os.path.expanduser(args[0]))
        if not os.path.exists(self.deployment_home):
            parser.error("Deployment home %s not found" % self.deployment_home)

        self.config_dir = os.path.join(self.deployment_home, "config")
        if not os.path.exists(self.config_dir):
            parser.error("Configuration directory %s does not exist" % self.config_dir)
        log_directory_file = os.path.join(self.config_dir, "log_directory.txt")
        if not os.path.exists(log_directory_file):
            parser.error("Log directory pointer file %s does not exit" % log_directory_file)
        with open(log_directory_file, "r") as f:
            self.log_directory = f.read().rstrip()
        parse_log_options(self.options, self.log_directory)
        if self.options.python_exe:
            if not os.path.exists(self.options.python_exe):
                parser.error("Python executable %s does not exist" % self.options.python_exe)

        self.engage_home = os.path.join(self.deployment_home, "engage")
        if not os.path.isdir(self.engage_home):
            parser.error("Engage home %s does not exist" % self.engage_home)
        self.engage_bin_dir = os.path.join(self.engage_home, "bin")
        if not os.path.isdir(self.engage_bin_dir):
            parser.error("Engage binary directory %s does not exist" % self.engage_bin_dir)

        if self.options.application_archive:
            self.application_archive = os.path.abspath(os.path.expanduser(self.options.application_archive))
            if not os.path.exists(self.application_archive):
                parser.error("Application archive file %s does not exist" % self.application_archive)

        if os.path.exists(os.path.join(self.config_dir, "pw_repository")):
            if self.options.subproc:
                self.master_pw = sys.stdin.read().rstrip()
            else:
                while True:
                    self.master_pw = getpass.getpass("Sudo password:")
                    extra_pw = getpass.getpass("Re-enter sudo password:")
                    if self.master_pw==extra_pw:
                        break
                    else:
                        print "Passwords do not match, try again."                


def _remove_engage_files(req):
    shutil.rmtree(req.config_dir)
    shutil.rmtree(req.engage_home)
    shutil.rmtree(os.path.join(req.deployment_home, "python"))

def _run_engage_command(req, command_name, command_args, logger, valid_rcs=[0]):
    command = os.path.join(req.engage_bin_dir, command_name)
    if not os.path.exists(command):
        raise Exception("Engage command script %s not found" % command)
    args = [command]
    if req.master_pw:
        args.append("-s")
    else:
        args.append("-n")
    args.append("--log=%s" % req.options.loglevel)
    args.extend(command_args)
    rc = run_and_log_program(args, None, logger, req.engage_bin_dir,
                             req.master_pw, hide_input=True)
    if rc not in valid_rcs:
        raise Exception("Execution of engage command '%s' failed, return code was %d" %
                        (args, rc))
    return rc


def rollback_upgrade(req, prev_version_dir, logger):
    # first, get rid of the engage files from the failed install
    # and replace with the files from the previous version
    _remove_engage_files(req)
    backup.restore_engage_files(prev_version_dir, False)
    # we've restored engage, now restore the app
    _run_engage_command(req, "backup", ["restore", prev_version_dir], logger)
    logger.info("Restore of previous app version successful")
    _run_engage_command(req, "svcctl", ["start", "all"], logger)
    logger.info("Start of previous version successful after rollback")
    
    
def run(req, logger):
    # Do a sanity check of the sudo password before we do anything
    # destructive.
    if req.master_pw:
        try:
            logger.debug("Test the sudo password by running an ls")
            run_sudo_program(["/bin/ls", "/"], req.master_pw, logger)
        except:
            logger.exception("Unable to run sudo commands with provided password")
            raise Exception("Unable to run sudo commands with provided password")
    
    # create directory for previous version
    prev_version_dir = os.path.join(req.deployment_home, "prev_version")
    if os.path.exists(prev_version_dir):
        logger.info("Removing old uninstall at %s" % prev_version_dir)
        shutil.rmtree(prev_version_dir)
    os.makedirs(prev_version_dir)

    # run the uninstall
    logger.info("Uninstalling old application version to %s" % prev_version_dir)
    # TODO: We should make the uninstall command atomic: if it fails, we should
    # restore the original state.
    _run_engage_command(req, "backup", ["uninstall", prev_version_dir], logger)
    # If present, move the password database to the backup dir until we finish the boostrap
    pw_repository_path = os.path.join(req.config_dir, "pw_repository")
    pw_salt_path = os.path.join(req.config_dir, "pw_salt")
    pw_repository_save_path = os.path.join(prev_version_dir, "pw_repository")
    pw_salt_save_path = os.path.join(prev_version_dir, "pw_salt")
    if os.path.exists(pw_repository_path):
        os.rename(pw_repository_path, pw_repository_save_path)
        os.rename(pw_salt_path, pw_salt_save_path)
    # remove engage files from the old version
    logger.info("Removing old version files")
    _remove_engage_files(req)

    # bootstrap the new engage
    logger.info("Boot strapping new engage environment")
    boot_cmd = ["-d", req.log_directory, req.deployment_home]
    if req.options.python_exe:
        boot_cmd = ["-p", req.options.python_exe] + boot_cmd
    rc = bootstrap.main(boot_cmd)
    if rc != 0:
        raise Exception("Bootstrap of new engage into %s failed" % req.deployment_home)

    # move the password database back, if present
    if os.path.exists(pw_repository_save_path):
        os.rename(pw_repository_save_path, pw_repository_path)
        os.rename(pw_salt_save_path, pw_salt_path)

    # run the upgrade
    install_script = os.path.join(req.engage_bin_dir, "install")
    upgrade_args = ["-u", prev_version_dir, "-f", "upgrade_subprocess.log",
                    "--config-choices-file=%s" % os.path.join(prev_version_dir, "config_choices.json")]
    if req.application_archive:
        upgrade_args.append("--application-archive=%s" % req.application_archive)
        logger.info("Running upgrade to new application at %s" % req.application_archive)
    else:
        logger.info("Running upgrade to new application")
    rc = _run_engage_command(req, "install", upgrade_args, logger, valid_rcs=[0,3])
    if rc == 3:
        logger.info("Upgrade failed, starting rollback to previous version")
        rollback_upgrade(req, prev_version_dir, logger)
        logger.info("Upgrade failed, rollback to previous version successfull.")
        return 3

    logger.info("Upgrade successful.")
    return 0
    
def main(argv):
    req = UpgradeRequest()
    req.process_args(argv)
    logger = setup_engage_logger(__name__)
    upgrade_error_file = os.path.join(req.log_directory, "upgrade_error.json")
    if os.path.exists(upgrade_error_file):
        os.remove(upgrade_error_file)        
    return run(req, logger)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""
Backup utility for applications
"""

import os
import os.path
import sys
import json
import shutil

import fixup_python_path

import engage.utils.log_setup as log_setup
import engage.utils.backup as backup
import cmdline_script_utils

from engage.utils.user_error import UserError, EngageErrInf

import gettext
_ = gettext.gettext

# Where we store the errors
errors = { }

def define_error(error_code, msg):
    global errors
    # instantiate an ErrorInfo object
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

ENGAGE_BACKUP_NOT_FOUND = 1

# here is where we define the actual error messages
define_error(ENGAGE_BACKUP_NOT_FOUND,
             _("Unable to find backup file for Engage, tried '%(file)s' and '%(compressed_file)s'"))


def _ends_with(s, suffix):
    if s[0-len(suffix):]==suffix:
        return True
    else:
        return False

def backup_resources(backup_directory, mgr_pkg_list, logger, compress):
    for (m, p) in mgr_pkg_list:
        logger.debug("backing up resource %s" % m.id)
        m.backup(backup_directory, compress)
    logger.info("Backup of deployed resources to %s completed successfully" % backup_directory)

def uninstall_resources(mgr_pkg_list, logger):
    for (m, p) in mgr_pkg_list:
        logger.debug("uninstalling resource %s" % m.id)
        m.uninstall(incomplete_install=False)
    logger.info("Uninstall of deployed resources completed successfully")


def save_engage_files(backup_directory, deployment_home, logger, compress):
    # Save all of engage's directories.
    # These are always copied rather than moved, as the backup
    # utility itself is run from one of these directories.
    files = [os.path.join(deployment_home, subdir) for subdir in ["config", "engage", "python"]]
    if compress:
        backup_archive = os.path.join(backup_directory, "engage_files.tar.gz")
    else:
        backup_archive = os.path.join(backup_directory, "engage_files.tar")
    logger.info("Saving engage files to %s" % backup_archive)
    backup.save(files, backup_archive, move=False)
    # installed resources and config choices are used in upgrade,
    # so have convenience copies that aren't tarred
    installed_resources_file = os.path.join(deployment_home, "config/installed_resources.json")
    shutil.copyfile(installed_resources_file, os.path.join(backup_directory, "installed_resources.json"))
    config_choices_file = os.path.join(deployment_home, "config/config_choices.json")
    if os.path.exists(config_choices_file):
        shutil.copyfile(config_choices_file, os.path.join(backup_directory, "config_choices.json"))


def restore_resources(backup_directory, mgr_pkg_list, logger, move=False):
    logger.info("Initiating restore of backed up resources from %s" % backup_directory)
    for (m, p) in mgr_pkg_list:
        m.restore(backup_directory, p)
    logger.info("Restore of backed up resources from %s completed successfully" % backup_directory)

def restore_engage_files(backup_directory, move=False):
    backup_archive = os.path.join(backup_directory, "engage_files.tar")
    if not os.path.exists(backup_archive):
        compressed_backup_archive = os.path.join(backup_directory, "engage_files.tar.gz")
        if not os.path.exists(compressed_backup_archive):
            raise UserError(errors[ENGAGE_BACKUP_NOT_FOUND],
                            msg_args={"file":backup_archive,"compressed_file":compressed_backup_archive})
        backup_archive = compressed_backup_archive
    backup.restore(backup_archive, move)
    

def main(argv):
    from optparse import OptionParser
    parser = OptionParser(usage="%prog [options] backup|uninstall|restore|restore-engage [backup_directory]")

    parser.add_option("--compress", "-c", action="store_true", dest="compress",
                      default=False, help="If specified, compress backup files")
    cmdline_script_utils.add_standard_cmdline_options(parser)
    (options, args) = parser.parse_args()
    if not (len(args)==2 or (len(args)==1 and args[0]=="uninstall")):
        parser.error("Wrong number of args, expecting 1 or 2")
    cmd = args[0]
    valid_commands = ["backup", "uninstall", "restore", "restore-engage"]
    if not (cmd in valid_commands):
        parser.error("Command must be one of %s" % valid_commands)

    (file_layout, dh) = cmdline_script_utils.process_standard_options(options, parser)

    if cmd != "uninstall":
        backup_directory = os.path.abspath(os.path.expanduser(args[1]))
    if cmd=="backup":
        if not os.path.isdir(backup_directory):
            os.makedirs(backup_directory)
    elif (cmd=="restore") or (cmd=="restore-engage"):
        if not os.path.isdir(backup_directory):
            parser.error("Backup directory %s does not exist" % backup_directory)

    if cmd == "restore-engage":
        # for restore engage, we don't try to get resources, as they aren't there yet
        restore_engage_files(backup_directory)
        return 0 # skip the rest

    mgr_pkg_list = cmdline_script_utils.get_mgrs_and_pkgs(file_layout, dh, options)

    logger = log_setup.setup_engine_logger(__name__)

    if cmd=="backup":
        for (m, p) in reversed(mgr_pkg_list):
            if m.is_service() and m.is_running():
                logger.info("stopping resource %s" % m.id)
                m.stop()
        backup_resources(backup_directory, mgr_pkg_list, logger, options.compress)
        save_engage_files(backup_directory, dh, logger, options.compress)
    elif cmd=="uninstall":
        for (m, p) in reversed(mgr_pkg_list):
            if m.is_service() and m.is_running():
                logger.info("stopping resource %s" % m.id)
                m.stop()
        uninstall_resources(mgr_pkg_list, logger)
    else: # command == restore
        restore_resources(backup_directory, mgr_pkg_list, logger)
    return 0

def call_from_console_script():
    main(sys.argv[1:])

if __name__ == "__main__":
    main(sys.argv[1:])

import sys
import tarfile
import os
import os.path
from optparse import OptionParser

import fixup_python_path

from engage.engine.engage_file_layout import get_engine_layout_mgr
from engage.engine.cmdline_script_utils import add_standard_cmdline_options, process_standard_options


from engage.utils.log_setup import setup_engage_logger
logger = setup_engage_logger(__name__)

from engage.utils.system_info import SUPPORTED_PLATFORMS

def _validate_dir_exists(dirname):
    if not os.path.isdir(dirname):
        raise Exception("Directory %s does not exist, your deployment home does not appear to be set up properly" % dirname)

def get_distribution_archive_filename(deployment_home):
    return os.path.join(os.path.join(deployment_home, "engage"), "engage-dist.tar.gz")

def create_distribution_from_deployment_home(deployment_home, archive_name=None):
    dh = os.path.abspath(os.path.expanduser(deployment_home))
    if not os.path.isdir(dh):
        raise Exception("Deployment home %s does not exist" % dh)
    engage_home = os.path.join(dh, "engage")
    _validate_dir_exists(engage_home)
    if not archive_name:
        archive_name = get_distribution_archive_filename(dh)
    if os.path.exists(archive_name):
        logger.debug("Deleting old distribution archive file")
        os.remove(archive_name)
    logger.debug("Creating distribution archive at %s" % archive_name)
    tf = tarfile.open(archive_name, "w:gz")
    try:
        sw_packages = os.path.join(engage_home, "sw_packages")
        _validate_dir_exists(sw_packages)
        tf.add(sw_packages, "engage/sw_packages")
        metadata = os.path.join(engage_home, "metadata")
        _validate_dir_exists(metadata)
        tf.add(metadata, "engage/metadata")
        python_pkg_dir = os.path.join(engage_home, "python_pkg")
        _validate_dir_exists(python_pkg_dir)
        tf.add(python_pkg_dir, "engage/python_pkg")
        bootstrap_file = os.path.join(engage_home, "bootstrap.py")
        tf.add(bootstrap_file, "engage/bootstrap.py")
        upgrade_file = os.path.join(engage_home, "upgrade.py")
        tf.add(upgrade_file, "engage/upgrade.py")
        found_cfg_exe = False
        for platform in SUPPORTED_PLATFORMS:
            cfg_exe_src = os.path.join(engage_home, "bin/configurator-%s" % platform)
            cfg_exe_dst = "engage/bin/configurator-%s" % platform
            if os.path.exists(cfg_exe_src):
                logger.debug("Copying configurator executable for %s" % platform)
                tf.add(cfg_exe_src, cfg_exe_dst)
                found_cfg_exe = True
        if not found_cfg_exe:
            raise Exception("Cound not find a configurator executable")
    finally:
        tf.close()


def main(argv):
    usage = "usage: %prog [options]"
    parser = OptionParser(usage=usage)
    parser.add_option("--archive-name", "-a", dest="archive_name",
                      default=None,
                      help="Full path of generated archive file (defaults to <deployment_home>/engage/engage-dist.tar.gz)")
    add_standard_cmdline_options(parser, uses_pw_file=False)
    (options, args) = parser.parse_args(args=argv)
    (file_layout, dh) = process_standard_options(options, parser, allow_overrides_of_dh=True)
    if options.archive_name:
        archive_name = options.archive_name
    else:
        archive_name = get_distribution_archive_filename(dh)
    create_distribution_from_deployment_home(dh, archive_name)
    print "Distribution successfully created at %s" % archive_name
    return 0
    


def call_from_console_script():
    sys.exit(main(sys.argv[1:]))

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))



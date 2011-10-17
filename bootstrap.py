#!/usr/bin/env python
import os
import os.path
import sys
from optparse import OptionParser
import shutil

if sys.version_info[0]!=2 or sys.version_info[1]<6:
    raise Exception("Engage requires Python version 2.6 or 2.7, but bootstrap was started with Python %d.%d (at %s)" %
                    (sys.version_info[0], sys.version_info[1], sys.executable))
# enable importing from the python_pkg sub-directory
base_src_dir=os.path.abspath(os.path.dirname(__file__))
python_pkg_dir = os.path.join(base_src_dir, "python_pkg")
assert os.path.exists(python_pkg_dir), "Python package directory %s does not exist" % python_pkg_dir
sys.path.append(python_pkg_dir)

# now do the required engage imports
from engage.utils.find_exe import find_executable, find_python_executable, get_python_search_paths
from engage.utils.process import system
from engage.utils.log_setup import setup_logger, parse_log_options, add_log_option
from engage.utils.system_info import get_platform
from engage.engine.create_distribution import create_distribution_from_deployment_home


def create_virtualenv(desired_python_dir, logger, base_python_exe=None):
    virtualenv_search_dirs = get_python_search_paths()
    python_exe = find_python_executable(logger, explicit_path=base_python_exe)
    # we start our virtualenv executable search at the same place as where we have
    # the python executable. Then, we check a bunch of well-known places to stick
    # virtualenv
    virtualenv_search_dirs = [os.path.dirname(python_exe)] + get_python_search_paths()
    virtualenv = find_executable("virtualenv", virtualenv_search_dirs, logger)
        
    if not os.path.exists(desired_python_dir):
        os.makedirs(desired_python_dir)
    # JF 6/7/2011: removed --no-site-packages command line option, as it makes
    # it hard to use pre-built packages installed by the package manager,
    # like py-mysql
    cmd = "%s --python=%s %s" % (virtualenv, python_exe,
                                 desired_python_dir)
    rc = system(cmd, logger, cwd=desired_python_dir)
    if rc != 0:
        raise Exception("Execution of '%s' failed, rc was %d" % (cmd, rc))

def is_package_installed(engage_bin_dir, package_name, logger):
    rc = system('%s -c "import %s"' %
                (os.path.join(engage_bin_dir, "python"),
                 package_name), logger)
    if rc == 0:
        logger.debug("Package '%s' already installed" %
                     package_name)
        return True
    else:
        logger.debug("Package '%s' not already installed" %
                     package_name)
        return False


def run_easy_install(engage_bin_dir, sw_packages_dir, package_file_list, logger, alternative_package_name=None):
    """Does an easy install into the engage virtualenv. See if there is a
    matching package in the sw_packages_dir from the package file list. If so,
    install it. Otherwise, use the alternative package name (if one was provided).
    """
    easy_install_exe = os.path.join(engage_bin_dir, "easy_install")
    assert os.path.exists(easy_install_exe), "Cound not find easy_install executable at %s" % easy_install_exe
    package_file_or_name = alternative_package_name
    for package_file in package_file_list:
        package_path = os.path.join(sw_packages_dir, package_file)
        if os.path.exists(package_path):
            package_file_or_name = package_path
            break
    if not package_file_or_name:
        raise Exception("Unable to find required python package %s" % package_path)
                
    logger.info("Installing bootstrap python package %s using easy_install" % package_file_or_name)
    rc = system("%s %s" % (easy_install_exe, package_file_or_name), logger)
    if rc != 0:
        raise Exception("Easy install for %s failed" % package_file_or_name)
    logger.info("easy_install successful")


def main(argv):
    usage = "usage: %prog [options] deployment_home"
    parser = OptionParser(usage=usage)
    add_log_option(parser)
    parser.add_option("-d", "--logdir", action="store",
                      type="string",
                      help="master log directory for deployment (defaults to <deployment_home>/log)",
                      dest="logdir", default=None)
    parser.add_option("-c", "--create-dist-archive",
                      action="store_true",
                      help="create a distribution archive",
                      dest="create_dist_archive", default=False)
    parser.add_option("-p", "--python",
                      default=None,
                      help="Use the specified python executable as basis for Python virtual environments",
                      dest="python_exe")
    (options, args) = parser.parse_args(args=argv)
    if len(args) != 1:
        parser.error("Expecting exactly one argument, the deployment's home directory")
        
    logger = setup_logger("Bootstrap", __name__)

    if options.python_exe:
        options.python_exe = os.path.abspath(os.path.expanduser(options.python_exe))
        if not os.path.exists(options.python_exe):
            parser.error("Python executable %s does not exist" %
                         options.python_exe)
        if not os.access(options.python_exe, os.X_OK):
            parser.error("Python executable file %s is not an executable" %
                         options.python_exe)
    
    deployment_home = os.path.abspath(os.path.expanduser(args[0]))
    if os.path.exists(deployment_home):
        sentry_file = os.path.join(deployment_home, "config/installed_resources.json")
        if os.path.exists(sentry_file):
            raise Exception("Deployment home directory %s exists and contains the file %s. Cannot overwrite an existing install." %
                            (deployment_home, sentry_file))
    else:
        os.makedirs(deployment_home)

    if options.logdir:
        log_dir = os.path.abspath(os.path.expanduser(options.logdir))
    else:
        log_dir = os.path.join(deployment_home, "log")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    parse_log_options(options, log_dir)
    logger.info("Running bootstrap under Python executable %s" % sys.executable)

    # the engage home is just a python virtual environment
    engage_home = os.path.join(deployment_home, "engage")
    create_virtualenv(engage_home, logger, options.python_exe)
    logger.info("Created python virtualenv for engage")

    # copy this bootstrap script and the upgrade script
    bootstrap_py_dst = os.path.join(engage_home, "bootstrap.py")
    shutil.copyfile(os.path.join(base_src_dir, "bootstrap.py"), bootstrap_py_dst)
    os.chmod(bootstrap_py_dst, 0755)
    upgrade_py_src = os.path.join(base_src_dir, "upgrade.py")
    upgrade_py_dst = os.path.join(engage_home, "upgrade.py")
    shutil.copyfile(upgrade_py_src, upgrade_py_dst)
    os.chmod(upgrade_py_dst, 0755)
               
    # we also copy the python_pkg directory to the distribution home for use in creating
    # future distributions
    python_pkg_dst_dir = os.path.join(engage_home, "python_pkg")
    logger.action("cp -r %s %s" % (python_pkg_dir, python_pkg_dst_dir))
    shutil.copytree(python_pkg_dir, python_pkg_dst_dir)

    # we need to run the setup.py script for the python_pkg
    engage_bin_dir = os.path.join(engage_home, "bin")
    engage_python_exe = os.path.join(engage_bin_dir, "python")
    assert os.path.exists(engage_python_exe), "Python executable at %s missing" % engage_python_exe
    setup_py_file = os.path.join(python_pkg_dir, "setup.py")
    assert os.path.exists(setup_py_file), "Missing %s" % setup_py_file
    cmd = "%s %s install" % (engage_python_exe, setup_py_file)
    rc = system(cmd, logger, cwd=python_pkg_dir)
    if rc != 0:
        raise Exception("Install of engage python packages failed: '%s' failed, rc was %d" % (cmd, rc))
    logger.info("Installed python packages")

    platform = get_platform()

    # copy the configurator binary
    config_exe_src_loc = os.path.join(base_src_dir, "bin/configurator-%s" % platform)
    assert os.path.exists(config_exe_src_loc), "Configurator executable missing at %s" % config_exe_src_loc
    config_exe_dst_loc = os.path.join(engage_bin_dir, "configurator-%s" % platform)
    logger.action("cp %s %s" % (config_exe_src_loc, config_exe_dst_loc))
    shutil.copyfile(config_exe_src_loc, config_exe_dst_loc)
    os.chmod(config_exe_dst_loc, 0755)
    symlink_loc = os.path.join(engage_bin_dir, "configurator")
    logger.action("ln -s %s %s" % (config_exe_dst_loc, symlink_loc))
    os.symlink(config_exe_dst_loc, symlink_loc)

    # copy the metadata files
    metadata_files_src_loc = os.path.join(base_src_dir, "metadata")
    metadata_files_dst_loc = os.path.join(engage_home, "metadata")
    logger.action("cp -r %s %s" % (metadata_files_src_loc, metadata_files_dst_loc))
    shutil.copytree(metadata_files_src_loc, metadata_files_dst_loc)

    # copy the sw_packages directory
    sw_packages_src_loc = os.path.join(base_src_dir, "sw_packages")
    sw_packages_dst_loc = os.path.join(engage_home, "sw_packages")
    logger.action("cp -r %s %s" % (sw_packages_src_loc, sw_packages_dst_loc))
    shutil.copytree(sw_packages_src_loc, sw_packages_dst_loc)

    if not is_package_installed(engage_bin_dir, "Crypto.Cipher.AES",
				logger):
        # Pycrypto may be preinstalled on the machine.
        # If so, we don't install our local copy, as installation
        # can be expensive (involves a g++ compile).
        run_easy_install(engage_bin_dir, sw_packages_src_log,
                         (["pycrypto-2.3-%s.tar.gz" % platform,
                           "pycrypto-2.3.tar.gz"],
                          "pycrypto"))

    bootstrap_packages = [(["paramiko-1.7.6.zip"], "paramiko"),
                          (["apache-libcloud-0.5.2.tar.bz2"], None),
                          (["python-cloudfiles-1.7.9.1.tar.gz"], "python-cloudfiles"),
                          (["argparse-1.2.1.tar.gz"], "argparse"),
                          (["provision-0.9.3-dev.tar.gz"], None),
                          (["nose-1.0.0.tar.gz"], "nose")]
    # run easy_install for all of the bootstrap packages
    for (package_file_list, alternate) in bootstrap_packages:
        run_easy_install(engage_bin_dir, sw_packages_src_loc,
                         package_file_list,
                         logger, alternate)
    
    # create a virtualenv for the deployed apps
    deployed_virtualenv = os.path.join(deployment_home, "python")
    create_virtualenv(deployed_virtualenv, logger, options.python_exe)
    logger.info("Created a virtualenv for deployed apps")

    deployed_config_dir = os.path.join(deployment_home, "config")
    os.makedirs(deployed_config_dir)
    # don't use "with" as this should be python 2.5 compatible
    f = open(os.path.join(deployed_config_dir, "log_directory.txt"), "wb")
    try:
        f.write(log_dir)
    finally:
        f.close()

    if options.create_dist_archive:
        logger.info("Creating a distribution")
        create_distribution_from_deployment_home(deployment_home)
        
    logger.info("Engage environment bootstrapped successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

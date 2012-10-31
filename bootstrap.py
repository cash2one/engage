#!/usr/bin/env python
import os
import os.path
import sys
from optparse import OptionParser
import shutil
import subprocess

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


def compare_versions(vstr1, vstr2):
    """Return:
    -1 if vstr1 > vstr2
     0 if vstr1 = vstr2
     1 if vstr1 < vstr2
    """
    def normalize_version(vstr):
        v = vstr.split(".")
        return [int(subv) for subv in v]
    v1 = normalize_version(vstr1)
    v2 = normalize_version(vstr2)
    for i in range(len(v1)):
        if (len(v2)==i) or v1[i]>v2[i]:
            return -1
        elif v1[i]<v2[i]:
            return 1
    if len(v2)>len(v1):
        return 1
    else:
        return 0

def get_virtualenv_version(exe_path):
    subproc = subprocess.Popen([exe_path, "--version"],
                               shell=False, stdout=subprocess.PIPE,
                               cwd=os.path.dirname(exe_path),
                               stderr=subprocess.STDOUT)
    ver_string = (subproc.communicate()[0]).rstrip()
    return ver_string
    ## return [int(component) if component.isdigit() else component
    ##         for component in ver_string.split(".")]

def create_virtualenv(desired_python_dir, logger, package_dir,
                      base_python_exe=None,
                      never_download=False):
    virtualenv_search_dirs = get_python_search_paths()
    python_exe = find_python_executable(logger, explicit_path=base_python_exe)
    # we start our virtualenv executable search at the same place as where we have
    # the python executable. Then, we check a bunch of well-known places to stick
    # virtualenv
    virtualenv_search_dirs = [os.path.dirname(python_exe)] + get_python_search_paths()
    virtualenv = find_executable("virtualenv", virtualenv_search_dirs, logger)
    version = get_virtualenv_version(virtualenv)
    if compare_versions("1.6.1", version)>=0:
        # --never-download and --extra-search-dir were added in 1.6.1
        has_options = True
    else:
        has_options = False
    if compare_versions("1.7", version)>=0:
        site_packages_opt = True
    else:
        site_packages_opt = False
        
    if not os.path.exists(desired_python_dir):
        os.makedirs(desired_python_dir)
    opts = ["--python=%s" % python_exe,]
    if site_packages_opt:
        opts.append("--system-site-packages")
    if has_options:
        opts.append("--extra-search-dir=%s" % package_dir)
        if never_download:
            opts.append("--never-download")
    elif never_download:
        raise Exception("--never-download option requires virtualenv 1.6.1 or later")
    # JF 6/7/2011: removed --no-site-packages command line option, as it makes
    # it hard to use pre-built packages installed by the package manager,
    # like py-mysql
    cmd = "%s %s %s" % (virtualenv, ' '.join(opts), desired_python_dir)
    logger.info('create virtualenv running command: %s' % cmd)
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


def copy_tree(src, dest, logger):
    logger.debug("cp -r %s %s" % (src, dest))
    shutil.copytree(src, dest)


def run_install(engage_bin_dir, sw_packages_dir, package_file_list,
                logger, alternative_package_name=None,
                never_download=False):
    """Does an install into the engage virtualenv. See if there is a
    matching package in the sw_packages_dir from the package file list. If so,
    install it. Otherwise, use the alternative package name (if one was provided).
    """
    install_exe = os.path.join(engage_bin_dir, "pip")
    assert os.path.exists(install_exe), "Cound not find pip executable at %s" % install_exe
    package_file_or_name = alternative_package_name
    is_local_file = False
    for package_file in package_file_list:
        package_path = os.path.join(sw_packages_dir, package_file)
        if os.path.exists(package_path):
            package_file_or_name = package_path
            is_local_file = True
            break
    if not package_file_or_name:
        raise Exception("Unable to find required python package %s" % package_path)
    elif never_download and (not is_local_file):
        raise Exception("Unable to find local copy of package and --never-download was specified. Package list was %s" % package_file_list)
                
    logger.info("Installing bootstrap python package: %s install %s" % (
            install_exe, package_file_or_name))
    rc = system("%s install %s" % (install_exe, package_file_or_name), logger)
    if rc != 0:
        raise Exception("pip install for %s failed" % package_file_or_name)
    logger.info("pip install successful")


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
    parser.add_option("-x", "--python",
                      default=None,
                      help="Use the specified python executable as basis for Python virtual environments",
                      dest="python_exe")
    parser.add_option("--never-download",
                      default=False,
                      action="store_true",
                      help="If specified, never try to download packages during bootstrap. If a package is required, exit with an error.",
                      dest="never_download")
    parser.add_option("--include-test-data",
                      default=False,
                      action="store_true",
                      help="If specified, copy test data into the deployment home. Otherwise, tests requiring data will be skipped.")
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

    test_data_src = os.path.join(base_src_dir, "test_data")
    if options.include_test_data and not os.path.isdir(test_data_src):
        parser.error("--include-test-data specified, but test data directory %s does not exist" % test_data_src)
        
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

    sw_packages_src_loc = os.path.join(base_src_dir, "sw_packages")
    sw_packages_dst_loc = os.path.join(engage_home, "sw_packages")

    create_virtualenv(engage_home, logger,
                      sw_packages_src_loc,
                      base_python_exe=options.python_exe,
                      never_download=options.never_download)
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
    copy_tree(python_pkg_dir, python_pkg_dst_dir, logger)

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
    copy_tree(metadata_files_src_loc, metadata_files_dst_loc, logger)

    # copy the sw_packages directory
    copy_tree(sw_packages_src_loc, sw_packages_dst_loc, logger)

    if not is_package_installed(engage_bin_dir, "Crypto.Cipher.AES", logger):
        # Pycrypto may be preinstalled on the machine.
        # If so, we don't install our local copy, as installation
        # can be expensive (involves a g++ compile).
        run_install(engage_bin_dir, sw_packages_src_loc,
                    ["pycrypto-2.3-%s.tar.gz" % platform, "pycrypto-2.3.tar.gz"],
                    logger, "pycrypto",
                    never_download=options.never_download)

    bootstrap_packages = [# JF 2012-05-11: Don't install provision and its
                          # dependencies - moving down to DJM level.
                          #(["paramiko-1.7.6.zip"], "paramiko"),
                          #(["apache-libcloud-0.6.2.tar.bz2"], None),
                          #(["argparse-1.2.1.tar.gz"], "argparse"),
                          #(["provision-0.9.3-dev.tar.gz"], None),
                          (["nose-1.0.0.tar.gz"], "nose"),
                          (["engage_utils-1.0.tar.gz"], "git+git://github.com/genforma/engage-utils.git")]
    # run install for all of the bootstrap packages
    for (package_file_list, alternate) in bootstrap_packages:
        run_install(engage_bin_dir, sw_packages_src_loc,
                    package_file_list,
                    logger, alternate,
                    never_download=options.never_download)
    
    # create a virtualenv for the deployed apps
    deployed_virtualenv = os.path.join(deployment_home, "python")
    create_virtualenv(deployed_virtualenv, logger,
                      sw_packages_src_loc,
                      base_python_exe=options.python_exe,
                      never_download=options.never_download)
    logger.info("Created a virtualenv for deployed apps")

    deployed_config_dir = os.path.join(deployment_home, "config")
    os.makedirs(deployed_config_dir)
    # don't use "with" as this should be python 2.5 compatible
    f = open(os.path.join(deployed_config_dir, "log_directory.txt"), "wb")
    try:
        f.write(log_dir)
    finally:
        f.close()

    # copy the test data if requested
    if options.include_test_data:
        test_data_dest = os.path.join(engage_home, "test_data")
        copy_tree(test_data_src, test_data_dest, logger)

    if options.create_dist_archive:
        logger.info("Creating a distribution")
        import engage.engine.create_distribution
        engage.engine.create_distribution.create_distribution_from_deployment_home(deployment_home, include_test_data=options.include_test_data)
        
    logger.info("Engage environment bootstrapped successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

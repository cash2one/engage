# Python-related install utilities

import os
import re
from engage.utils.process import run_and_log_program


def is_python_package_installed(site_packages_dir, package_file_regexp,
                                package_name, logger):
    """Check to see if a component is installed by looking for a matching
    file/directory name in the site-packages directory.
    """
    files = os.listdir(site_packages_dir)
    for f in files:
        if re.match(package_file_regexp, f) != None:
            logger.debug("Found the %s installation" % package_name)
            return True
    logger.debug("Did not find the %s installation" % package_name)
    return False


class CompileAllError(Exception):
    pass


def run_compileall(python_exe, directory, logger):
    """(re-)compile all the python files under the specified directory
    """
    rc = run_and_log_program([python_exe, "-mcompileall", directory],
                             {}, logger)
    if rc != 0:
        raise CompileAllError("Python compile-all packages failed for directory '%s'" % directory)

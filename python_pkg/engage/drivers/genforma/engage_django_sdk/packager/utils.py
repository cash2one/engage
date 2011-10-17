"""Miscellaneous utility functions"""

import os
import os.path
import sys
import json
import re
import subprocess
import traceback
import logging
import copy

logger = logging.getLogger(__name__)

from parse_requirements import parse,  get_local_files_matching_requirements
from engage_django_components import get_additional_requirements
import package_data
from errors import RequestedPackageError, PipError

def app_module_name_to_dir(app_directory_path, app_module_name, check_for_init_pys=True):
    """The application module could be a submodule, so we may need to split each level"""
    dirs = app_module_name.split(".")
    dirpath = app_directory_path
    module_name = None
    for dirname in dirs:
        if module_name:
            module_name = module_name + "." + dirname
        else:
            module_name = dirname
        dirpath = os.path.join(dirpath, dirname)
        init_file = os.path.join(dirpath, "__init__.py")
        if check_for_init_pys and not os.path.exists(init_file):
            raise ValidationError("Missing __init__.py file for module %s" % module_name)
    return dirpath


def write_json(json_obj, filename):
    with open(filename, 'wb') as f:
        json.dump(json_obj, f)


def find_files(directory, filename_re_pattern, operation_function):
    """Find all the files recursively under directory whose names contain the specified pattern
       and run the operation_function on the fileame.
    """
    regexp = re.compile(filename_re_pattern)
    directory = os.path.abspath(os.path.expanduser(directory))
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if regexp.search(filename):
                operation_function(os.path.join(root, filename))


def get_deployed_settings_module(django_settings_module):    
    mod_comps = django_settings_module.split('.')
    if len(mod_comps)==1:
        return "deployed_settings"
    else:
        return '.'.join(mod_comps[0:-1]) + ".deployed_settings"


def import_module(qualified_module_name):
    """Import the specified module and return the contents of that module.
    For example if we have a module foo.bar containing variables x and y,
    we can do the following:
      m = import_module("foo.bar")
      print m.x, m.y
    """
    m = __import__(qualified_module_name)
    mod_comps = (qualified_module_name.split('.'))[1:]
    for comp in mod_comps:
        m = getattr(m, comp)
    return m
    
def get_settings_file_directory(python_path_dir, django_settings_module):
    settings_module_comps = django_settings_module.split(".")
    if len(settings_module_comps)==1:
        return python_path_dir
    else:
        return os.path.join(python_path_dir, "/".join(settings_module_comps[0:-1]))


def get_python_path(python_path_dir, django_settings_module):
    """The PYTHONPATH we give to the python subprocess should include
    the python path needed to import our settings module as well as the
    directory containing the settings file itself (unless it is the same
    as python_path_dir).
    """
    settings_dir = get_settings_file_directory(python_path_dir, django_settings_module)
    if settings_dir != python_path_dir:
        return "%s:%s" % (python_path_dir, settings_dir)
    else:
        return python_path_dir


# Copied from engage.utils.process
# TODO: need to share code directly
def run_and_log_program(program_and_args, env_mapping, logger, cwd=None,
                        input=None, hide_input=False, allow_broken_pipe=False):
    """Run the specified program as a subprocess and log its output.
    program_and_args should be a list of entries where the first is the
    executable path, and the rest are the arguments.
    """
    logger.debug(' '.join(program_and_args))
    if cwd != None:
        logger.debug("Subprocess working directory is %s" % cwd)
    subproc = subprocess.Popen(program_and_args,
                               env=env_mapping, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, cwd=cwd)
    logger.debug("Started program %s, pid is %d" % (program_and_args[0],
                                                   subproc.pid))
    if input!=None:
        if not hide_input:
            logger.debug("Input is " + input)
        try:
            (output, dummy) = subproc.communicate(input)
            for line in output.split("\n"):
                logger.debug("[%d] %s" % (subproc.pid, line.rstrip()))
        except OSError:
            if not allow_broken_pipe:
                raise
            else:
                logger.warn("Subprocess %d closed stdin before write of input data complete" %
                            subproc.pid)
                for line in subproc.stdout:
                    logger.debug("[%d] %s" % (subproc.pid, line))
    else:
        subproc.stdin.close()
        for line in subproc.stdout:
            logger.debug("[%d] %s" % (subproc.pid, line))
    subproc.wait()
    logger.debug("[%d] %s exited with return code %d" % (subproc.pid,
                                                        program_and_args[0],
                                                        subproc.returncode))
    return subproc.returncode

class SubprocBadRc(Exception):
    def __init__(self, msg, rc):
        super(SubprocBadRc, self).__init__(msg)
        self.rc = rc

def check_run_and_log_program(program_and_args, env_mapping, logger, cwd=None,
                              input=None, hide_input=False, allow_broken_pipe=False):
    """Version of run_and_log_program that checks for return code and throws an
    exception if not zero.
    """
    rc = run_and_log_program(program_and_args, env_mapping, logger, cwd,
                             input, hide_input, allow_broken_pipe)
    if rc!=0:
        raise SubprocBadRc("Call to %s failed with return code %d, full command was '%s'" %
                           (program_and_args[0], rc, ' '.join(program_and_args)),
                           rc)
        

def create_virtualenv(desired_python_dir):
    logger.info(">> Creating Python virtualenv for validation")
    def find_exe_in_paths(paths, exe):
        tried = []
        for p in paths:
            e = os.path.join(p, exe)
            if os.path.exists(e):
                return e
            tried.append(e)
        raise Exception("Unable to find %s, tried %s" % (exe, tried))
    paths = []
    if os.uname()[0]=="Darwin" and sys.executable.endswith("Resources/Python.app/Contents/MacOS/Python"):
        # on MacOS, sys.executable could lie to us -- if we start a python like .....2.7/bin/python,
        # it will tell us .....2.7/Resources/Python.app/Contents/MacOS/Python. This is problematic,
        # because the other executable scripts (e.g. virtualenv) will be installed with the real python
        # not the one that sys.executable claims is the real python. To fix this, we add the real python
        # to the head of our search list.
        real_python_dir = os.path.abspath(os.path.join(sys.executable, "../../../../../bin"))
        paths.append(real_python_dir)
    paths.append(os.path.dirname(sys.executable))
    env_path = os.getenv("PATH")
    if env_path:
        for path in env_path.split(":"):
            paths.append(os.path.abspath(os.path.expanduser(path)))
    paths.append(os.path.expanduser("~/bin"))
    python_exe = find_exe_in_paths(paths, "python")
    virtualenv_exe = find_exe_in_paths(paths, "virtualenv")
    cmd = [virtualenv_exe, "--python=%s" % python_exe, "--no-site-packages",
           os.path.abspath(os.path.expanduser(desired_python_dir))]
    try:
        check_run_and_log_program(cmd, None, logger)
    except Exception, e:
        logger.exception("Problem in creating virtualenv. Command was '%s', error was %s" % (' '.join(cmd), str(e)))
        raise Exception("Problem in creating virtualenv. Command was '%s', error was %s" % (' '.join(cmd), str(e)))


def run_pip(pip_exe_path, requirements_file_path, logger,
            package_cache_dir=None):
    """Run pip to install the specified requirements file. This is similar to
    check_run_and_log_program(), except that we provide more specific error
    messages and logging.
    """
    cmd = [pip_exe_path, "install", "-r", requirements_file_path]    
    env = copy.deepcopy(os.environ)
    if package_cache_dir:
        env["PIP_DOWNLOAD_CACHE"] = package_cache_dir
    reqfile_basename = os.path.basename(requirements_file_path)
    logger.debug("Running pip on requirements file %s" %
                 reqfile_basename)
    try:
        subproc = subprocess.Popen(cmd, env=env,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        subproc.stdin.close()
        # build up a regexp of the error messages that come from pip
        p1 = re.escape("Could not find any downloads that satisfy the requirement")
        p2 = re.escape("No distributions at all found for")
        p3 = re.escape("Command") + ".*" + re.escape("failed with error code")
        rexp = re.compile("(" + p1 + ")|(" + p2 + ")|(" + p3 + ")")
        for line in subproc.stdout:
            if rexp.search(line):
                logger.error("pip> " + line)
            else:
                logger.debug("pip> " + line)
        subproc.wait()
    except Exception, e:
        err_msg = "Problem in running pip on requirements file %s. Error was %s" \
                  % (reqfile_basename, str(e))
        logger.exception(err_msg)
        raise PipError(err_msg)
    if subproc.returncode != 0:
        logger.error("Pip run failed, return code was %d" % subproc.returncode)
        raise PipError("Pip install on requirements file %s failed" %
                       reqfile_basename)
    logger.debug("Pip install on requirements file %s successful." %
                 reqfile_basename)


def install_requirements(python_virtualenv_dir, requirements_file,
                         package_cache_dir=None):
    if len(package_data.problem_packages)>0:
        # If there are packages known to cause problems, we check that list
        # against the requirements file and stop everything if a problematic
        # package is found.
        packages = parse(requirements_file,
                         parse_version_constraints=False)
        for pkg in packages:
            lpkg = pkg.lower()
            if lpkg in package_data.problem_packages:
                raise RequestedPackageError(
                    "Package '%s' is known to cause problems with Engage deployments. Please remove it from your requirements.txt file (or comment it out)." %
                                pkg)
        
    pip = os.path.abspath(os.path.join(os.path.expanduser(python_virtualenv_dir), "bin/pip"))
    if not os.path.exists(pip):
        raise RequestedPackageError("Could not find pip executable")
    req_file_path = os.path.abspath(os.path.expanduser(requirements_file))
    if package_cache_dir:
        # If the package cache is present, we read through the requirements file to see
        # if we have any matches. If matches are found, we install them directly. We'll
        # still run pip on the requirements file at the end to catch anything that is missing
        # or the wrong version.
        package_cache_dir = os.path.abspath(os.path.expanduser(package_cache_dir))
        logger.debug("Checking for packages in directory %s" % package_cache_dir)
        if os.path.exists(package_cache_dir):
            cache_files = os.listdir(package_cache_dir)
            package_files = get_local_files_matching_requirements(requirements_file,
                                                                  cache_files)
            for pkg_file in package_files:
                pkg_path = os.path.join(package_cache_dir, pkg_file)
                logger.debug("Installing %s from package cache" % pkg_file)
                cmd = [pip, "install", pkg_path]
                try:
                    check_run_and_log_program(cmd, None, logger)
                except Exception, e:
                    logger.exception("Problem in running pip on package %s. Command was '%s', error was %s" % (pkg_file, ' '.join(cmd), str(e)))
                    raise PipError("Problem in running pip on package %s. Command was '%s', error was %s" % (pkg_file, ' '.join(cmd), str(e)))

    # now, run pip on the requirements file.
    run_pip(pip, req_file_path, logger, package_cache_dir)


_platform_requirements = [
  "Django==1.3.1",
  "South==0.7.3"
]

def write_platform_requirements_file(install_path, components_list):
    requirements = copy.copy(_platform_requirements)
    req_set = set(requirements)
    # we stick the requirements file one level above the project root
    requirements_file = os.path.join(install_path, "engage_requirements.txt")
    for comp in components_list:
        req_list = get_additional_requirements(comp)
        for req in req_list:
            if req not in req_set:
                requirements.append(req)
                req_set.add(req)
    logger.debug("Platform requirements: %s" % requirements)
    with open(requirements_file, "w") as f:
        f.write("# Engage platform requirements\n")
        for req in requirements:
            f.write(req + "\n")
    return requirements_file

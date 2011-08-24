"""Utility functions for finding executables (python, virtualenv, etc.)
"""
import os
import os.path
import sys
import subprocess


def find_executable(name, paths, logger):
    """Use this function to find a file
    in one of serveral well-known locations
    """
    for directory in paths:
        exe = os.path.join(directory, name)
        if os.path.exists(exe):
            logger.debug("Using %s for %s" % (exe, name))
            return exe
    raise Exception("Unable to find executable %s in %s" % (name, paths.__repr__()))


class PythonNotFoundError(Exception):
    def __init__(self, paths, min_major_version, min_minor_version,
                 limit_major_version, limit_minor_version):
        self.min_version = "%d.%d" % (min_major_version, min_minor_version)
        self.limit_version = "%d.%d" % (limit_major_version, limit_minor_version)
        msg = "Unable to find a python executable with version >= %s and version < %s" % \
              (self.min_version, self.limit_version)
        Exception.__init__(self, msg)
        self.paths = paths


def _find_basis_of_virtualenv():
    """Look for a symbolic link in the python lib directory to see if the current python
    executable is a virtualenv. If so, return the directory of the bin directory containing the
    python executable which was used as the basis for the virtualenv. If this isn't a virtualenv,
    we just return None.
    """
    libpath = os.path.abspath(os.path.join(os.path.dirname(sys.executable),
                                           "../lib/python%d.%d" % (sys.version_info[0], sys.version_info[1])))
    testfile_path = os.path.join(libpath, "os.py")
    if os.path.exists(testfile_path) and os.path.islink(testfile_path):
        return os.path.abspath(os.path.join(os.path.dirname(os.readlink(testfile_path)), "../../bin"))
    else:
        return None
    
def get_python_search_paths():
    """Return a list of directories to check for a python executable. We check to see
    if the current executable is a python virtualenv. If so, we stick the basis of
    the virtualenv at the head of our list. Next, on the list is the current python
    executable's directory. After that, we put all the directories in the system PATH
    environment variable, followed by some well-known locations for python installs.
    The well-known locations are included because this call could be made in a subprocess
    that isn't given an environment.
    """
    class PathSetList(object):
        """Maintain an ordered list as well as a set of already-included paths"""
        def __init__(self):
            self.path_list = []
            self.path_set = set()
        def append(self, entry):
            if entry not in self.path_set:
                self.path_list.append(entry)
                self.path_set.add(entry)
    paths = PathSetList()
    ve_basis = _find_basis_of_virtualenv()
    if ve_basis:
        paths.append(ve_basis)
    if os.uname()[0]=="Darwin" and sys.executable.endswith("Resources/Python.app/Contents/MacOS/Python"):
        # on MacOS, sys.executable could lie to us -- if we start a python like .....2.7/bin/python,
        # it will tell us .....2.7/Resources/Python.app/Contents/MacOS/Python. This is problematic,
        # because the other executable scripts (e.g. virtualenv) will be installed with the real python
        # not the one that sys.executable claims is the real python. To fix this, we add the real python
        # to the head of our search list.
        real_python_dir = os.path.abspath(os.path.join(sys.executable, "../../../../../bin"))
        paths.append(real_python_dir)
                         
    paths.append(os.path.dirname(sys.executable))

    if os.environ.has_key('PATH'):
        for path in os.environ['PATH'].split(':'):
            paths.append(path)
                
    if os.uname()[0]=='Darwin':
        extra_paths = ["/Library/Frameworks/Python.framework/Versions/Current/bin",
                       "/Library/Frameworks/Python.framework/Versions/%d.%d/bin" %
                       (sys.version_info[0], sys.version_info[1]),
                       "/usr/bin", "/usr/local/bin", "/opt/local/bin"]
    else:
        extra_paths = ["/usr/bin", "/usr/local/bin"]
    for path in extra_paths:
        paths.append(path)

    paths.append(os.path.join(os.path.expanduser('~'), 'bin'))
    return paths.path_list

        
def find_python_executable(logger, explicit_path=None,
                           include_current_exe=True,
                           min_major_version=2, min_minor_version=6, limit_major_version=3, limit_minor_version=0):
    """
    This program attempts to locate a python executable matching the specified range criteria:
    min_major_version.min_minor_vers <= python_exe_version < limit_major_version.limit_minor_version.
    If explicit_path is set, the value is tested to see if it points to a python executable satisfying the
    range criteria. Otherwise, we check the set of paths returned by get_python_search_paths().

    If know python executable matching the criteria can be found, a PythonNotFoundError is thrown. This exeception
    has enough information to create a meaningful user error.
    """
    def test_python_exe(exe_path):
        if os.path.exists(exe_path):
            try:
                subproc = subprocess.Popen([exe_path, "--version"], env={},
                                          stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                          shell=False)
                subproc.stdin.close()
                lines = subproc.stdout.read().rstrip()
                subproc.wait()
                fields = lines.split()
                version = fields[1]
                version_comps = version.split('.')
                major_version = int(version_comps[0])
                minor_version = int(version_comps[1])
                if ((major_version>min_major_version) or (major_version==min_major_version and minor_version>=min_minor_version)) and \
                   ((major_version<limit_major_version) or (major_version==limit_major_version and minor_version<limit_minor_version)):
                    return True
                else:
                    return False
            except:
                return False
        else:
            return False
        # end of test_python_exe
        
    if explicit_path:
        exe_paths = [ explicit_path ]
    else:
        exe_paths = [ os.path.join(python_dir, "python") for python_dir in get_python_search_paths() ]
        
    for path in exe_paths:
        if test_python_exe(path):
            logger.info("Using python executable at %s" % path)
            return path
    # didn't find a usable python
    raise PythonNotFoundError(exe_paths, min_major_version, min_minor_version,
                              limit_major_version, limit_minor_version)


if __name__ == "__main__":
    """If running as a standalone script, call find_python_executable()
    and print the results.
    """
    import logging
    logger = logging.getLogger()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)
    python_exe = find_python_executable(logger)
    print "find_python_executable() returned %s" % python_exe
    print "get_python_search_paths() returned %s" % get_python_search_paths()


# Utilities for manipulating and checking paths

import os
import errno
import os.path

from user_error import UserError, InstErrInf, convert_exc_to_user_error
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = InstErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_INSTDIR_NOT_WRITABLE = 001
ERR_INSTDIR_ALREADY_EXISTS   = 002

define_error(ERR_INSTDIR_NOT_WRITABLE,
             _("Install directory '%(dir)s' is not writable."))
define_error(ERR_INSTDIR_ALREADY_EXISTS,
             _("Install directory '%(dir)s' already exists."))


def dir_path_is_writable(dir_path):
    """Given an absolute path to a target directory, we want to see if either
    it exists and we can write to it, or it does not exist but we can
    create the necesary subdirectories so that it exists.
    """
    old_path = None
    path = dir_path
    while path != old_path:
        if os.path.isdir(path):
            if os.access(path, os.W_OK): return True
            else: return False
        old_path = path
        path = os.path.dirname(path)
    return False
        
_dotslash = "." + os.sep
_dotslashlen = len(_dotslash)

def get_first_subdir_component(path):
    """Helper used in extracting the first subdirectory from an archive toc.
    It expects a relative path.
    
    >>> import os
    >>> p1 = "." + os.sep + "foo" + os.sep + "bar"
    >>> get_first_subdir_component(p1)
    'foo'
    >>> p2 = "foo" + os.sep + "bar"
    >>> get_first_subdir_component(p2)
    'foo'
    >>> get_first_subdir_component("foo")
    'foo'
    >>> p3 = "foo" + os.sep
    >>> get_first_subdir_component(p3)
    'foo'
    >>> p4 = os.sep + "foo" + os.sep + "bar"
    >>> print get_first_subdir_component(p4)
    None
    """
    if os.path.isabs(path): return None
    if path.find(_dotslash)==0:
        path = path[_dotslashlen:]
    if len(path)==0 or (path=="."): return None
    idx = path.find(os.sep)
    if idx==-1: return path
    else: return path[0:idx]


def check_installable_to_target_dir(install_dir, package_name):
    """Given that the installed software is supposed to end up in
    install_dir, check that we can really install there. This means that
    the parent directory is writable (or if it doesn't exist, is creatable) and
    that the directory we will create by expanding the package archive doesn't
    already exist. If these checks fails, throws an UserError. The
    package_name parameter is just for error messages.
    """
    parent_dir = os.path.dirname(install_dir)
    if not dir_path_is_writable(parent_dir):
        raise UserError(errors[ERR_INSTDIR_NOT_WRITABLE],
                        msg_args={"dir":parent_dir},
                        context=[package_name])
    if os.path.exists(install_dir):
        raise UserError(errors[ERR_INSTDIR_ALREADY_EXISTS],
                        msg_args={"dir":install_dir},
                        context=[package_name])

def mkdir_p(path): #create directory if it does not exist
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST:
            pass
        else: raise

def join_list(list_of_subpaths):
    """Like os.path.join(), but combines an arbirary list of subpaths into
    a full path"""
    path = list_of_subpaths[0]
    for new_component in list_of_subpaths:
        path = os.path.join(path, new_component)
    return os.path.normpath(path)

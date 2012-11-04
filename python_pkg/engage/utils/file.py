"""
Utilities for parsing and searching, and modifying files.
"""
import re
import os
import os.path
import tempfile
import shutil
import stat
import string
import grp
import subprocess
import sys
import codecs

from user_error import UserError, InstErrInf
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = InstErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_DATAFILE_NOT_FOUND = 001

define_error(ERR_DATAFILE_NOT_FOUND,
             _("Installer data file '%(path)s' not found."))


class FilePatternScan:
    """Scan a file for a set of regular expressions. The regular expressions,
    provided in re_map, are defined as a map from abritrary names to string
    patterns. For each call to scan(), the file is opened and scanned for each
    of the patterns. scan() returns a map from the keys in re_map to booleans,
    indicating whether the pattern was found. scan() reads to the end of the
    file and then saves the final file position. Subsequent calls to scan()
    start at the previous end position. This is useful when scanning server
    logfiles that are still being written by the server.

    The cumulative_results property is a  map from the re_map keys to
    booleans indicating whether the associated pattern was ever seen during
    a scan. If we reset the file, we reset the cumulative results as well.
    """
    def __init__(self, filename, re_map, raise_error_if_no_file=False,
                 seek_to_end_before_scan=False):
        """If raise_error_if_no_file is True, then we raise an IOError if the
        file does not exist. If we've already scanned into the file and
        a subsequent open fails, if raise_error_if_no_file is False,
        we reset the position."""
        self.filename = filename
        self.file_pos = 0
        self.re_map = re_map
        self.compiled_re_map = {}
        self.cumulative_results = {}
        self.raise_error_if_no_file = raise_error_if_no_file
        for key in re_map.keys():
            self.compiled_re_map[key] = re.compile(re_map[key])
            self.cumulative_results[key] = False
        try:
            self.file_ctime = os.path.getctime(filename)
        except:
            self.file_ctime = None
        if seek_to_end_before_scan:
            try:
                file_obj = open(self.filename, "rb")
                file_obj.seek(0, os.SEEK_END)
                self.file_pos = file_obj.tell()
            except:
                pass # swallow the exception
    
    def _make_empty_results_dict(self):
        results = {}
        for key in self.re_map.keys():
            results[key] = False
        return results

    def scan(self):
        results = self._make_empty_results_dict()
        try:
            ctime = os.path.getctime(self.filename)
            if self.file_ctime != ctime:
                # the file was newly created since the last scan,
                # so we reset everything
                self.ctime = ctime
                self.file_pos = 0
                self.cumulative_results = self._make_empty_results_dict()
            file_obj = open(self.filename, "rb")
        except:
            if self.raise_error_if_no_file or os.path.exists(self.filename):
                raise
            else:
                self.file_pos = 0
                return results
        file_obj.seek(self.file_pos)
        for line in file_obj:
            for key in self.compiled_re_map.keys():
                if self.compiled_re_map[key].search(line)!=None:
                    self.cumulative_results[key] = True
                    results[key] = True
        self.file_pos = file_obj.tell()
        file_obj.close()
        return results

    def __str__(self):
        str = ""
        for key in self.re_map:
            if self.cumulative_results[key]==True:
                found = "true"
            else:
                found = "false"
            str += ' {"key":"%s", "regexp":"%s", "found":"%s"}\n' % \
                   (key, self.re_map[key], found)
        return '{"filename":"%s", "position":%d,\n%s}' % \
            (self.filename, self.file_pos, str)

    
def subst_in_file(filename, pattern_list, subst_in_place=False): 
    """Scan the specified file and substitute patterns. pattern_list is
    list of pairs, where the first element is a regular expressison pattern
    and the second element is a either a string or a function. If the
    second element is a string, then occurrances of the pattern in the file
    are all replaced with the string. If the value is a function, then
    this function is called with a match object and should return the
    new value for the pattern. See the python documentation on re.sub() for
    details.

    If subst_in_place is True, then we leave only the modified file. If it
    is False, we leave the orginal file at <filename>.orig.

    Note that we set the permissions of the new file version to be the same
    as those for the original file. This is important for executable files.

    Returns the total number of substitutions made
    """
    if not os.access(filename, os.W_OK): # catch write problems early
        raise IOError, "Unable to write to %s" % filename
    source_file_perms = os.stat(filename).st_mode
    re_list = []
    for (pattern, value) in pattern_list:
        re_list.append((re.compile(pattern), value))
    if subst_in_place:
        source = open(filename, "rb")
        target = tempfile.NamedTemporaryFile(dir=os.path.dirname(filename),
                                             delete=False)
    else:
        shutil.move(filename, filename + ".orig")
        source = open(filename + ".orig", "rb")
        target = open(filename, "wb")
    total_count = 0
    for line in source:
        for (regexp, value) in re_list:
            (line, count) = regexp.subn(value, line)
            total_count += count
        target.write(line)
    source.close()
    target.close()
    if subst_in_place:
        shutil.move(target.name, filename)
    os.chmod(filename, source_file_perms)
    return total_count


def instantiate_template_file(src_file_path, dest_file_path, substitution_map, subst_in_place=False, logger=None,
                              force_executable_permissions=False):
    """Instantiate a template file using the specified substitution map.
    See string.Template() in the standard python library for the syntax of
    template files. If the source file and destination file are the same,
    the original file is left at <filename>.orig, unless subst_in_place=True.

    By default, we set the permissions of the new file version to be the same
    as those for the original file. If the file ends in .sh or force_executable_permissions
    is set, then we add in executable permissions. We only add in the group and other
    execute permissions if the corresponding read permissions are set.

    If logger is specified, we log the files and substitution calls at the debug level

    As a doctest, we write a simple template file in a temporary directory, instantiate
    the template, validate that the template was instantiated correctly, check that the
    execute permission was set, and remove the temp directory.

    
    >>> import tempfile
    >>> import os
    >>> import os.path
    >>> import shutil
    >>> tdir = tempfile.mkdtemp()
    >>> try:
    ...     src_file_path = os.path.join(tdir, "test.sh.tmpl")
    ...     dest_file_path = os.path.join(tdir, "test.sh")
    ...     # create the template file
    ...     with open(src_file_path, "w") as sf:
    ...         sf.write('this is ${v1} ${v2}. ${v2}')
    ...     instantiate_template_file(src_file_path, dest_file_path,
    ...                               {'v1':'a', 'v2':'test'})
    ...     assert os.path.exists(dest_file_path)
    ...     with open(dest_file_path, "r") as df:
    ...         data = df.read()
    ...     print data
    ...     assert has_executable_permission(dest_file_path) 
    ... finally:
    ...     shutil.rmtree(tdir)
    ...
    this is a test. test
    >>>
    """
    if logger:
        logger.debug("Intantiate template: src=%s," % src_file_path)
        logger.debug("  dest=%s," % dest_file_path)
        logger.debug("  substitutions=%s" % substitution_map.__repr__())
    source_file_perms = os.stat(src_file_path).st_mode

    fileObj = open(src_file_path, "rb")
    templStr = fileObj.read()
    fileObj.close()
    templ = string.Template(templStr)
    result = templ.substitute(substitution_map)

    if (src_file_path==dest_file_path) and not subst_in_place:
        shutil.move(src_file_path, src_file_path + ".orig")
        
    outfileObj = open(dest_file_path, "wb")
    outfileObj.write(result)
    outfileObj.close()
    perms = source_file_perms
    if force_executable_permissions or (os.path.basename(dest_file_path)[-3:]==".sh"):
        perms = perms | stat.S_IXUSR
        if (source_file_perms & stat.S_IRGRP):
            perms = perms | stat.S_IXGRP
        if (source_file_perms & stat.S_IROTH):
            perms = perms | stat.S_IROTH
    dest_file_perms = os.stat(dest_file_path).st_mode
    if perms != dest_file_perms:
        if logger: logger.action("chmod %0d %s" % (perms, dest_file_path))
        os.chmod(dest_file_path, perms)


def make_temp_config_file(contents, dir=None):
    """Make a temporary configuration file that is accessible only to the
    current user. Returns the name of the file. Caller is responsible for
    deleting the file.
    """
    fobj = tempfile.NamedTemporaryFile(dir=dir, delete=False)
    os.chmod(fobj.name, stat.S_IRUSR | stat.S_IWUSR) # only accessible to user
    fobj.write(contents)
    fobj.close()
    return fobj.name


def get_data_file_path(installer_module_file_path, data_file_name):
    """Get the full path for a data file used by an intaller module, validating that the
    file exists. installer_module_file_path should be the __file__ variable for the calling
    module (which evaluates to the full file path of the calling module). data_file_name
    should be the name of the desired data file. The data file is expected to be in the data
    subdirectory under the parent directory of the calling module. For example, if the
    calling module is at ~/foo/bar.py, and the data file name is bab, then the path will
    be ~/foo/data/bab.
    """
    parent_dirname = os.path.abspath(os.path.dirname(installer_module_file_path))
    data_file_path = os.path.join(os.path.join(parent_dirname, "data"), data_file_name)
    if not os.path.exists(data_file_path):
        raise UserError(errors[ERR_DATAFILE_NOT_FOUND],
                        msg_args={"path":data_file_path},
                        developer_msg="Called by installer file %s" % installer_module_file_path)
    else:
        return data_file_path


def get_data_file_contents(installer_module_file_path, data_file_name, mode="rb"):
    """Return the contents of the specified installer data file (see get_data_file_path
    for an explanation of the installer_module_file_path and data_file_name arguments).
    """
    path = get_data_file_path(installer_module_file_path, data_file_name)
    file = open(path, mode)
    data = file.read()
    file.close()
    return data

def has_executable_permission(path):
    statinfo = os.stat(path)
    if statinfo.st_mode & stat.S_IXUSR:
        return True
    else:
        return False

def set_shared_file_group_and_permissions(path, group_name, logger=None,
                                          writable_to_group=False,
                                          sudo_password=None):
    """For a file that is shared with another user (e.g. the webserver user),
    we may need to change its group to a shared group (e.g. www-data) and then
    give the file group read permissions (and execute for directories).
    If writable_to_group is true, we also make the file writable to the
    group.

    If sudo_password is specified, we run this under sudo.

    TODO: don't system commands if file already has permissions
    """
    assert os.path.exists(path)
    import engage_utils.process
    statinfo = os.stat(path)
    # grant rw for user and r for group
    permissions = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP
    if stat.S_ISDIR(statinfo.st_mode) or (statinfo.st_mode & stat.S_IXUSR):
        # if a directory or executable, grant execute permissions
        permissions = permissions | stat.S_IXUSR | stat.S_IXGRP
    if writable_to_group:
        permissions = permissions | stat.S_IWGRP
    gid = grp.getgrnam(group_name).gr_gid
    if sudo_password:
        engage_utils.process.sudo_chgrp(group_name, [path], sudo_password, logger)
    else:
        if logger:
            logger.action("chgrp %s %s" % (group_name, path))
        os.chown(path, -1, gid)
    if sudo_password:
        engage_utils.process.sudo_chmod(permissions, [path], sudo_password, logger)
    else:
        if logger:
            logger.action("chmod %o %s" % (permissions, path))
        os.chmod(path, permissions)


def set_shared_directory_group_and_permissions(path, group_name, logger=None,
                                               writable_to_group=False):
    """Call set_shared_file_group_and_permissions() on the specified directory,
    all subdirectories, and files.
    If writable_to_group is true, we also make the directories/files writable to the
    group.
    """
    assert os.path.isdir(path), "%s is not a directory" % path
    for (dirname, subdirs, files) in os.walk(path):
        set_shared_file_group_and_permissions(dirname, group_name, logger,
                                              writable_to_group=writable_to_group)
        for file in files:
            set_shared_file_group_and_permissions(os.path.join(dirname, file), group_name, logger,
                                                  writable_to_group=writable_to_group)


def sudo_set_shared_directory_group_and_permissions(path, group_name, logger,
                                                    sudo_password,
                                                    writable_to_group=False):
    assert os.path.isdir(path), "%s is not a directory" % path
    import engage_utils.process
    statinfo = os.stat(path)
    # grant rw for user and r for group
    permissions = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP
    if stat.S_ISDIR(statinfo.st_mode) or (statinfo.st_mode & stat.S_IXUSR):
        # if a directory or executable, grant execute permissions
        permissions = permissions | stat.S_IXUSR | stat.S_IXGRP
    if writable_to_group:
        permissions = permissions | stat.S_IWGRP
    engage_utils.process.sudo_chgrp(group_name, [path], sudo_password, logger, recursive=True)
    engage_utils.process.sudo_chmod(permissions, [path], sudo_password, logger, recursive=True)

def sudo_ensure_directory_group_reachable(path, group_name, logger,
                                          sudo_password):
    """This ensures that the specified directory can be reached by members of
    the specified group. If a parent directory does not have the necessary execute
    permissions, this won't be the case. We work up the directory hierarchy, and if a
    directory is not viewable by the group, we add execute permissions to either
    group or other depending on whether the directory is in the specified group.

    TODO: this is not going to work if the current user cannot read the directory.
    To get around this, we would need to run the entire function as root or grab the
    permissions using sudo in a subprocess.
    """
    import engage_utils.process
    pdir = os.path.dirname(path)
    gid = grp.getgrnam(group_name).gr_gid
    while pdir != '/':
        statinfo = os.stat(pdir)
        if statinfo.st_gid == gid:
            if (stinfo.st_mode & stat.S_IXGRP) == 0:
                permissions = statinfo.st_mode | stat.S_IXGRP
                engage_utils.process.sudo_chmod(permissions, [pdir], sudo_password, logger,
                                   recursive=False)
        elif (statinfo.st_mode & stat.S_IXOTH) == 0:
            permissions = statinfo.st_mode | stat.S_IXOTH
            engage_utils.process.sudo_chmod(permissions, [pdir], sudo_password, logger,
                               recursive=False)
        pdir = os.path.dirname(pdir)
            
            

def get_file_permissions(path):
    """Return a tuple of (user_id, group_id, mode_bits) for the specified file.
    The main use case to use this on conjunction with set_file_permissions() to do
    the following:
      1. save config file foo.conf to foo.conf.orig
      2. create a ververion of foo.conf
      3. make sure the permissions are the same for the new foo.conf as they were for the
         original one.
    """
    stat_data = os.stat(path)
    return (stat_data.st_uid, stat_data.st_gid, stat_data.st_mode)


def set_file_permissions(path, tuple):
    """Set the permissions of the specified file based on the given permissions
    tupe (user_id, group_id, mode_bits). Designed to be used with get_file_permissions()
    """
    (user_id, group_id, mode_bits) = tuple
    os.chown(path, user_id, group_id)
    os.chmod(path, mode_bits)


def subst_utf8_template_file(filename, substitutions, srcfile=None):
    """Perform string substitions on an utf8-encoded file. The source file's
    name should be <outfile>.tmpl, unless srcfile is provided explictly.
    """
    if srcfile:
        templ_file = srcfile
    else:
        templ_file = filename + ".tmpl"
    if not os.path.exists(templ_file):
        raise Exception("Template file %s not found" % templ_file)
    with codecs.open(templ_file, "r", "utf-8" ) as fileObj:
        templStr = fileObj.read()
    templ = string.Template(templStr)
    result = templ.substitute(substitutions)
    with open(filename, "w") as outfileObj:
        outfileObj.write(result)

def run_with_temp_file(func, data=None, *args):
    """Create a temporary file, write the data, if any, to the
    specified file, call the function func, and then delete the
    temp file.
    """
    with tempfile.NamedTemporaryFile(delete=False) as f:
        if data:
            f.write(data)
        name = f.name
        f.close()
    try:
        func(name, *args)
    finally:
        os.remove(name)


class NamedTempFile(object):
    def __init__(self, data=None):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            if data:
                f.write(data)
            self.name = f.name
            f.close()

    def close(self):
        os.remove(self.name)
        self.name = None
        
    def __enter__(self):
        return self

    def __exit__(self, tp, vl, tb):
        self.close()
        return False


class OptNamedTempFile(NamedTempFile):
    """This is a variant on NamedTempFile for when we might have a permanent
       file rather than a temp file. If the permanent file is specified,
       we do nothing, other than store its name. If the permanent file is not
       specified, we call NamedTempFile to create and delete the temp file
       as needed.
    """
    def __init__(self, perm_file_name=None):
        if perm_file_name:
            self.perm_file = True
            self.name = perm_file_name
        else:
            NamedTempFile.__init__(self)
            self.perm_file = False

    def close(self):
        if not self.perm_file:
            NamedTempFile.close(self)


class TempDir(object):
    def __init__(self, dir=None):
        self.name = tempfile.mkdtemp(dir=dir)

    def close(self):
        shutil.rmtree(self.name)
        self.name = None
        
    def __enter__(self):
        return self

    def __exit__(self, tp, vl, tb):
        self.close()
        return False


def mangle_resource_key(key):
    """Convert a resource key into a name that can be used as a python package name"""
    s = "%s__%s" % (key['name'], key['version'])
    return re.sub('[.-]', '_', s.replace(' ',''))


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


if __name__ == "__main__":
    import doctest
    doctest.testmod()

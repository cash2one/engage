import zipfile
import tarfile
import os
import tempfile
import shutil
import logging
logger = logging.getLogger(__name__)

from errors import ArchiveStructureError, FileFormatError

def _is_zip_direntry(name):
    l = len(name)
    if (l > 0) and (name[l-1] == '/'): return True
    else: return False

class BaseArchiveHandler(object):
    def __init__(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, tp, vl, tb):
        self.close()
        return False

    
class ZipfileHandler(BaseArchiveHandler):
    def __init__(self, filename, mode="r"):
        BaseArchiveHandler.__init__(self)
        self.filename = filename
        if mode=="r":
            self.archive = zipfile.ZipFile(filename, mode)
        else:
            self.archive = zipfile.ZipFile(filename, mode,
                                           compression=zipfile.ZIP_DEFLATED)
        self.mode = mode

    def is_file_in_archive(self, entry_name):
        try:
            info = self.archive.getinfo(entry_name)
            return True
        except KeyError:
            return False

    def get_namelist(self):
        return self.archive.namelist()

    def extract(self, parent_dir):
        """This is a workaround for a bug in Python's ZipFile.extractall() method implementation.
        It does not handle extracting subdirectories correctly, so we extract the files individually,
        creating subdirectories by hand.
        """
        for name in self.archive.namelist():
            if _is_zip_direntry(name):
                subdir = os.path.join(parent_dir, name)
                if not os.path.exists(subdir):
                    os.makedirs(subdir)
            else:
                self.archive.extract(name, parent_dir)

    def open_member(self, member):
        """Open the specified member file for reading, returning a file-like
        object.
        """
        return self.archive.open(member)

    def add_member(self, filepath, path_in_archive):
        assert self.mode=='a' or self.mode=='w'
        self.archive.write(filepath, path_in_archive)
        
    def close(self):
        self.archive.close()

    def create_new_from_dir(self, src_dirpath):
        assert self.mode == "w"
        logger.debug("Creating archive file at %s" % self.filename)
        src_dirpath = os.path.abspath(os.path.expanduser(src_dirpath))
        parent_dir = os.path.dirname(src_dirpath)
        for (dirname, subdirs, files) in os.walk(src_dirpath):
            subdir = dirname[len(parent_dir)+1:]
            for file in files:
                filepath = os.path.join(subdir, file)
                self.archive.write(os.path.join(dirname, file), filepath)


class TarfileHandler(BaseArchiveHandler):
    def __init__(self, filename, mode="r"):
        BaseArchiveHandler.__init__(self)
        self.filename = filename
        self.archive = tarfile.open(filename, mode)
        self.mode = mode

    def is_file_in_archive(self, entry_name):
        try:
            info = self.archive.getmember(entry_name)
            return True
        except KeyError:
            return False

    def get_namelist(self):
        return self.archive.getnames()

    def extract(self, parent_dir):
        self.archive.extractall(parent_dir)

    def open_member(self, member):
        """Open the specified member file for reading, returning a file-like
        object.
        """
        return self.archive.extractfile(member)

    def close(self):
        self.archive.close()

    def create_new_from_dir(self, src_dirpath):
        assert self.mode[0] == "w"
        logger.debug("Creating archive file at %s" % self.filename)
        src_dirpath = os.path.abspath(os.path.expanduser(src_dirpath))
        self.archive.add(src_dirpath, os.path.basename(src_dirpath))


_dotslash = "." + os.sep
_dotslashlen = len(_dotslash)

def _get_first_subdir_component(path):
    """Helper used in extracting the first subdirectory from an archive toc.
    It expects a relative path.
    """
    if os.path.isabs(path): return None
    if path.find(_dotslash)==0:
        path = path[_dotslashlen:]
    if len(path)==0 or (path=="."): return None
    idx = path.find(os.sep)
    if idx==-1: return path
    else: return path[0:idx]

def validate_archive_files(namelist):
    """Given a list of files in an archive, validate that they are relative paths, not absolute. Also,
    determine whether this is a common directory under which all files appear. If either test fails, raise
    an exception. Otherwise, return the name of the common directory
    """
    common_dirname = None
    for name in namelist:
        if os.path.isabs(name):
            raise ArchiveStructureError("Invalid format for archive: contains absolute file path %s" % name)
        if name.find(os.sep): # contains a directory component
            subdir = _get_first_subdir_component(name)
        else:
            subdir = name
        if common_dirname == None:
            common_dirname = subdir
        elif common_dirname != subdir:
            raise ArchiveStructureError("File %s does not fall under common subdirectory %s" % (name, common_dirname))
    return common_dirname


def create_handler(filename):
    # figure out the type of the file
    if zipfile.is_zipfile(filename):
        logger.debug("File is a zipfile")
        return ZipfileHandler(filename)
    elif tarfile.is_tarfile(filename):
        logger.debug("File is a tarfile")
        return TarfileHandler(filename)
    else:
        raise FileFormatError("Unable to read file %s -- neither a zip file or a tar file" % filename)


def add_file_to_existing_archive(archive_file, new_filename, path_in_archive):
    if zipfile.is_zipfile(archive_file):
        z = ZipfileHandler(archive_file, "a")
        z.add_member(new_filename, path_in_archive)
        z.close()
    elif tarfile.is_tarfile(archive_file):
        # No good way to add a file to an existing tgz archive. We just expand
        # it, add the file, and recreate the archive.
        tmpdir = tempfile.mkdtemp()
        try:
            t = TarfileHandler(archive_file)
            t.extract(tmpdir)
            common_dir = validate_archive_files(t.get_namelist())
            t.close()
            assert path_in_archive[0:len(common_dir)] == common_dir
            copy_dest = os.path.join(tmpdir, path_in_archive)
            shutil.copyfile(new_filename, copy_dest)
            t = TarfileHandler(archive_file, "w:gz")
            t.create_new_from_dir(os.path.join(tmpdir, common_dir))
            t.close()
        finally:
            shutil.rmtree(tmpdir)
    else:
        raise FileFormatError("Unable to read file %s -- neither a zip file or a tar file" % archive_file)

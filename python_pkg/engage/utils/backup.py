#!/usr/bin/env python

"""Utility functions for backups.
We backup and restore a list of files/directories to a directory
identified by backup_location. The files are saved in a tar archive.

"""
import os
import os.path
import tarfile
import sys
import shutil
import tempfile

import process
import log_setup

logger = log_setup.setup_engage_logger(__name__)

def _ends_with(s, suffix):
    if s[0-len(suffix):]==suffix:
        return True
    else:
        return False
    
def _get_compression_mode(archive_filename):
    if _ends_with(archive_filename, ".tar.gz") or \
       _ends_with(archive_filename, ".tgz"):
        compressed = True
        return "gz"
    else:
        return ""

def check_if_save_requires_superuser(file_list, followlinks=False):
    """Return true if a file in the list is owned by a different user
    than the current user
    """
    euid = os.geteuid()
    def is_same_user(file):
        return os.lstat(file).st_uid == euid

    for file in file_list:
        if os.path.isdir(file):
            for (dirpath, dirnames, filenames) in os.walk(file, followlinks=followlinks):
                if not is_same_user(dirpath):
                    return True
                for filename in filenames:
                    if not is_same_user(os.path.join(dirpath, filename)):
                        return True
        else:
            if not is_same_user(file):
                return True
    return False
                
def check_if_restore_requires_superuser(backup_archive):
    euid = os.geteuid()
    tar = tarfile.open(backup_archive)
    for member in tar.getmembers():
        if member.uid != euid:
            tar.close()
            return True
    tar.close()
    return False

def save(file_list, backup_location, move=False):
    full_path_list = [os.path.abspath(os.path.expanduser(f)) for f in file_list]
    tar = tarfile.open(backup_location, "w|" + _get_compression_mode(backup_location))
    for f in full_path_list:
        tar.add(f)
    tar.close()
    if move:
        for f in full_path_list:
            if os.path.isdir(f):
                shutil.rmtree(f)
            else:
                os.remove(f)

def save_as_sudo_subprocess(file_list, backup_location, sudo_password, move=False):
    backup_loc_path = os.path.abspath(os.path.expanduser(backup_location))
    f = tempfile.NamedTemporaryFile(delete=False)
    try:
        f.write("\n".join(file_list))
        f.close()
        if move:
            args = [sys.executable, __file__, "-f", f.name, "-m", "save", backup_loc_path]
        else:
            args = [sys.executable, __file__, "-f", f.name, "save", backup_loc_path]
        process.run_sudo_program(args, sudo_password, logger)
    finally:
        os.unlink(f.name)

                
def restore(backup_location, move=False):
    tar = tarfile.open(backup_location, "r|" + _get_compression_mode(backup_location))
    tar.extractall("/")
    tar.close()
    if move:
        os.remove(backup_location)

def restore_as_sudo_subprocess(backup_location, sudo_password, move=False):
    backup_loc_path = os.path.abspath(os.path.expanduser(backup_location))
    if move:
        args = [sys.executable, __file__, "-m", "restore", backup_loc_path]
    else:
        args = [sys.executable, __file__, "restore", backup_loc_path]
    process.run_sudo_program(args, sudo_password, logger)


def restore_to_temp_directory(backup_location):
    tar = tarfile.open(backup_location, "r|" + _get_compression_mode(backup_location))
    tempdir = tempfile.mkdtemp()
    tar.extractall(tempdir)
    tar.close()
    return tempdir
    
    
if __name__ == "__main__":
    # if run as a script, we act as a command-line utility
    from optparse import OptionParser
    parser = OptionParser(usage="%prog [options] save|restore backup_location [file1 file2 ...]")
    parser.add_option("--files", "-f", action="store", dest="files",
                      default=None, help="If specified, read the specified file to get a list of files to save, rather than taking them from the command line")
    parser.add_option("--move", "-m", action="store_true", dest="move",
                      default=False, help="If specified, move files, otherwise copy them")
    (options, args) = parser.parse_args()
    if len(args)<2:
        parser.error("Wrong number of args, expecting at least 2")
    cmd = args[0]
    if cmd!="save" and cmd!="restore":
        parser.error("Command must be either save or restore")
    if cmd=="save":
        if options.files==None and len(args)<3:
            parser.error("To save must specify at least one filename")
        elif options.files and len(args)>2:
            parser.error("Cannot specify files on both command line and listing file")
    else:
        if options.files or len(args)>2:
            parser.error("Do not specify file list for restore")
        
    backup_location = args[1]
    if not (_ends_with(backup_location, ".tar") or _ends_with(backup_location, ".tgz") or \
            _ends_with(backup_location, ".tar.gz")):
        parser.error("Backup location must be a tar archive")
    backup_dir = os.path.dirname(backup_location)
    if not os.path.isdir(backup_dir):
        os.makedirs(backup_dir)

    if cmd=="save":
        if options.files:
            with open(options.files, "r") as f:
                files = f.read().split()
        else:
            files = args[2:]
        save(files, backup_location, options.move)
    else:
        restore(backup_location, options.move)
    sys.exit(0)
    

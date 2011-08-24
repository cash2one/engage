#!/usr/bin/env python
"""This utility installs an engage extension into a deployment home.
"""

import os
import os.path
import sys
from optparse import OptionParser
import shutil
import re
import logging

logger = logging.getLogger(__name__)

# enable importing from the python_pkg sub-directory
base_src_dir=os.path.abspath(os.path.dirname(__file__))
python_pkg_dir = os.path.join(base_src_dir, "python_pkg")
assert os.path.exists(python_pkg_dir), "Python package directory %s does not exist" % python_pkg_dir
sys.path.append(python_pkg_dir)

from engage.extensions import installed_extensions, extension_versions

dist_root = os.path.abspath(os.path.dirname(__file__))
dist_root_parent = os.path.abspath(os.path.join(dist_root, ".."))

class EngageExtension(object):
    def __init__(self, path, name, version):
        self.path = path
        self.name = name
        self.version = version

    def _copy_dir(self, src_dirname, target, dry_run=False):
        src_dir = os.path.join(self.path, src_dirname)
        dest_dir = os.path.join(os.path.join(target, src_dirname),
                                self.name)
        if os.path.exists(src_dir):
            logger.info("Copying %s to %s" % (src_dirname, dest_dir))
            if os.path.exists(dest_dir):
                raise Exception("Target directory %s already exists" % dest_dir)
            if not dry_run:
                shutil.copytree(src_dir, dest_dir)
    
    def install(self, dist_root, dry_run=False):
        if not dry_run:
            logger.info("Running install of %s to %s" % (self.name, dist_root))
        else:
            logger.info("Dry run install of %s to %s" % (self.name, dist_root))
        self._copy_dir("metadata", dist_root, dry_run=dry_run)
        dest_engage_pkg_dir = os.path.join(os.path.join(dist_root, "python_pkg"),
                                           "engage")
        self._copy_dir("drivers", dest_engage_pkg_dir, dry_run=dry_run)
        self._copy_dir("tests", dest_engage_pkg_dir, dry_run=dry_run)
        self._copy_dir("mgt_backends", dest_engage_pkg_dir, dry_run=dry_run)
        # For the software packages we copy the individual files to the main package
        # cache.
        src_cache_dir = os.path.join(self.path, "sw_packages")
        dest_cache_dir = os.path.join(dist_root, "sw_packages")
        if os.path.exists(src_cache_dir):
            logger.info("Copying software packages from %s to %s" %
                        (src_cache_dir, dest_cache_dir))
            for fname in os.listdir(src_cache_dir):
                src_file = os.path.join(src_cache_dir, fname)
                dest_file = os.path.join(dest_cache_dir, fname)
                logger.debug("Copying %s to %s" % (fname, dest_file))
                shutil.copyfile(src_file, dest_file)
        # update the extension file
        installed_extensions.append(self.name)
        extension_versions[self.name] = self.version
        extns_file = os.path.join(dest_engage_pkg_dir, "extensions.py")
        logger.info("Updating extensions file %s" % extns_file)
        with open(extns_file, "rb") as ef:
            lines = ef.read().split("\n")
        updated_list = False
        updated_versions = False
        if not dry_run:
            with open(extns_file, "wb") as ef:
                for line in lines:
                    if re.match("^installed_extensions = ", line):
                        ef.write("installed_extensions = %s\n" %
                                 installed_extensions.__repr__())
                        updated_list = True
                    elif re.match("^extension_versions = ", line):
                        ef.write("extension_versions = %s\n" %
                                 extension_versions.__repr__())
                        updated_versions = True
                    else:
                        ef.write(line + "\n")
        else:
            for line in lines:
                if re.match("^installed_extensions = ", line):
                    sys.stdout.write("installed_extensions = %s\n" %
                                     installed_extensions.__repr__())
                    updated_list = True
                elif re.match("^extension_versions = ", line):
                    sys.stdout.write("extension_versions = %s\n" %
                                     extension_versions.__repr__())
                    updated_versions = True
                else:
                    sys.stdout.write(line + "\n")
        if (not updated_list) or (not updated_versions):
            raise Exception("Extension registration file %s did not have correct format, unable to complete update" % extns_file)
        logger.info("Successfully installed extension %s" % self.name)
                                        
        
def process_args(argv):
        usage = "usage: %prog [options] path_to_extension"
        parser = OptionParser(usage=usage)
        parser.add_option("--dry-run", action="store_true",
                          help="If specified, don't make changes, just log what would be done",
                          default=False)
        (options, args) = parser.parse_args(args=argv)
        if len(args)==0:
            parser.print_help()
            sys.exit(0)
        elif len(args) > 1:
            parser.error("Expecting exactly one argument, path to extension directory")
        extension_path = os.path.abspath(args[0])
        if not os.path.exists(extension_path):
            parser.error("Extension directory %s does not exist" % extension_path)
        extension_name = os.path.basename(extension_path)
        if os.path.basename(dist_root_parent)=="src":
            parser.error("Cannot install extension into source tree %s, run from distribution tree" % dist_root)
        if extension_name in installed_extensions:
            parser.error("Extension %s already installed" % extension_name)
        version_file = os.path.join(extension_path, "version.txt")
        if not os.path.exists(version_file):
            parser.error("Missing version file %s" % version_file)
        with open(version_file, "rb") as vf:
            extension_version = vf.read().rstrip()
        ext = EngageExtension(extension_path, extension_name,
                              extension_version)
        return (ext, options)


def main(argv=sys.argv[1:]):
    (ext, opts) = process_args(argv)
    ext.install(dist_root, dry_run=opts.dry_run)
    return 0


if __name__ == "__main__":
    #formatter = logging.Formatter("[%(levelname)s][%(name)s] %(message)s")
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    #console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)
    sys.exit(main())



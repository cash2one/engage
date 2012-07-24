#! /usr/bin/env python
# Micro Package Manager
# Download external packages

import sys
from subprocess import Popen, PIPE
import logging
import os
import string
from optparse import OptionParser
import getpass

LOG_LEVEL=logging.DEBUG
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(LOG_LEVEL)
logger.addHandler(handler)


def system(command):
    """Run a command in the shell. If the command fails, we thow an
    exception.
    """
    p = Popen(command, shell=True)
    (pid, exit_status) = os.waitpid(p.pid, 0)
    rc = exit_status >> 8 # the low byte is the signal ending the proc
    if rc != 0:
        raise Exception("Command execution failed: '%s'" % command)


def run_subproc_and_get_output(args):
    return Popen(args, stdout=PIPE, shell=True).communicate()[0]


def get_platform():
    uname = (run_subproc_and_get_output("uname")).rstrip()
    if uname == "Darwin":
        release = (run_subproc_and_get_output("uname -r")).rstrip().split('.')
        if release[0]=='11' and release[1]=='4':
            return "maxosx64" # mac osx lion
        assert release[0] == '10', "Mac OS release expected to start with 10 or 11, actual was %s" % release[0]
        sub_release = int(release[1])
        if sub_release >= 6:
            return "macosx64"
        else:
            return "macosx"
    elif uname == 'Linux':
        uname_m = (run_subproc_and_get_output("uname -m")).rstrip()
        if uname_m == 'x86_64':
            return 'linux64'
        else:
            return 'linux'
    else:
        raise Exception("unknown platform type. uname returned %s" % uname)


def test_for_wget():
    try:
        result = Popen("wget --help", stdout=PIPE,
                         shell=True).communicate()[0]
        if len(result)>0: return True
        else: return False
    except:
        return False

def get_cksum(file, target_dir):
    result = run_subproc_and_get_output("cd %s; cksum %s" % (target_dir, file))
    return string.rstrip(result)
    

########################################
# handlers
########################################

class Handler(object):
    def __init__(self, config, target_dir, dry_run):
        self.config = config
        self.target_dir = target_dir
        self.dry_run = dry_run
    def download(self, metadata):
        pass

class WgetHandler(Handler):
    NAME = "wget"
    def __init__(self, config, target_dir, dry_run):
        Handler.__init__(self, config, target_dir, dry_run)
        if config.has_key("no_check_certificate"):
            self.no_check_certificate = config["no_check_certificate"]
        else:
            self.no_check_certificate = False
            
    def download(self, metadata):
        if self.no_check_certificate or (metadata.has_key("no_check_certificate") and metadata['no_check_certificate']):
            cmd = "wget --no-check-certificate -O %s \"%s\"" % (os.path.join(self.target_dir, metadata["filename"]), metadata["location"])
        else:
            cmd = "wget -O %s \"%s\"" % (os.path.join(self.target_dir, metadata["filename"]), metadata["location"])
        if not self.dry_run:
            system(cmd)
        else:
            print cmd


class ScpHandler(Handler):
    NAME = "scp"
    def __init__(self, config, target_dir, dry_run):
        """The config object may optionally contain a hosts property which is a mapping from
        hostname keys (as used in the location in the metadata) to objects containing hostname and
        user properties. For example we might have something like:
        { 'hosts': { 'host1': {'hostname':'hostname1.foo.com', 'user':'joe'}}}
        This would cause a location of 'host1:/foo/bar.txt' to be mapped to:
        joe@hostname1.foo.com:/foo/bar.txt.
        If a host entry is not found, the default user name is used and the original value in the
        location string is used for the hostname.
        """
        Handler.__init__(self, config, target_dir, dry_run)
        self.default_user = getpass.getuser()
        if config.has_key("hosts"):
            self.hosts = config["hosts"]
        else:
            self.hosts = {}
        
    def download(self, metadata):
        location = metadata["location"]
        idx = location.index(':')
        if idx == (-1):
            raise Exception("location '%s' has invalid format for scp handler. Should have host:/filepath" % location)
        host_key = location[0:idx]
        remote_path = location[idx+1:]
        if self.hosts.has_key(host_key):
            host = self.hosts[host_key]['hostname']
            if self.hosts[host_key].has_key('user'):
                user = self.hosts[host_key]['user']
            else:
                user = self.default_user
        else:
            host = host_key
            user = self.default_user
        cmd = "scp %s@%s:%s %s" % (user, host, remote_path, os.path.join(self.target_dir, metadata["filename"]))
        if not self.dry_run:
            system(cmd)
        else:
            print cmd


handler_types = {
    WgetHandler.NAME: WgetHandler,
    ScpHandler.NAME: ScpHandler
}

    
class PackageMgr(object):
    def __init__(self, target_dir, config, packages, platform, dry_run=False,
                 stop_on_checksum_mismatch=False):
        assert os.path.exists(target_dir), "Target directory %s does not exist" % target_dir
        self.target_dir = target_dir
        self.config = config
        self.packages = packages
        self.platform = platform
        self.dry_run = dry_run
        self.stop_on_checksum_mismatch = stop_on_checksum_mismatch
        self.handlers = {}
        for handler_name in handler_types.keys():
            if config.has_key(handler_name):
                handler_config = config[handler_name]
            else:
                handler_config = {}
            self.handlers[handler_name] = (handler_types[handler_name])(handler_config, self.target_dir, self.dry_run)
        self.files_already_present = 0
        self.files_downloaded = 0

    def _run_handler(self, metadata):
        """See if we need to download the file. If so, download it and verify the checksum.
        """
        filename = metadata["filename"]
        path = os.path.join(self.target_dir, filename)
        if os.path.exists(path):
            cksum = get_cksum(filename, self.target_dir)
            if cksum != metadata["checksum"]:
                print "File %s already exists, but checksum does not match expected" % \
                      path
                print "Checksum was %s" % cksum
                if self.stop_on_checksum_mismatch:
                    sys.exit(1)
                else:
                    print "Renaming %s to %s.old to allow download of new file" % (path, path)
                    os.rename(path, path+".old")
            else:
                logger.info("File %s already exists, skipping" % filename)
                self.files_already_present = self.files_already_present + 1
                return
        handler_name = metadata["handler"]
        if not self.handlers.has_key(handler_name):
            print "Invalid handler type %s for file %s" % (handler_name, filename)
            sys.exit(1)
        handler = self.handlers[handler_name]
        logger.info("Retrieving %s via %s" % (filename, handler_name))
        handler.download(metadata)
        if not self.dry_run:
            if not os.path.exists(path):
                print "Retrieval of %s supposedly successful, but file does not exist" % path
                sys.exit(1)
            cksum = get_cksum(filename, self.target_dir)
            if cksum != metadata["checksum"]:
                print "File %s retrieved successfully, but checksum does not match expected" % \
                      path
                sys.exit(1)
            logger.info("Successfully retrieved %s" % filename)
        self.files_downloaded = self.files_downloaded + 1

    def download_by_group(self, group_list):
        groups = set(group_list)
        for package in self.packages:
            pkg_groups = set(package["groups"])
            if groups.isdisjoint(pkg_groups):
                continue
            if package.has_key("platform") and package['platform']!=self.platform:
                print "Skipping '%s' -- only for %s" % (package['filename'],
                                                        package['platform'])
                continue
            
            self._run_handler(package)

    def download_by_filename(self, file_list):
        for package in self.packages:
            if not (package['filename'] in file_list):
                continue
            if package.has_key("platform") and package['platform']!=self.platform:
                print "Skipping '%s' -- only for %s" % (package['filename'],
                                                        package['platform'])
                continue
            self._run_handler(package)

    def download_all(self):
        for package in self.packages:
            if package.has_key("platform") and package['platform']!=self.platform:
                print "Skipping '%s' -- only for %s" % (package['filename'],
                                                        package['platform'])
                continue
            self._run_handler(package)

        
        
    
########################################
# main program
########################################

def main(argv):
    import json
    parser = OptionParser(usage="\n%prog [options] group <download_group1> <download_group2> ...\n%prog [options] file <download_file1> <download_file2> ...\n%prog [options] all")
    default_target_dir = os.path.abspath(".")
    default_package_file = os.path.join(os.path.abspath("."), "packages.json")
    default_platform = get_platform()
    parser.add_option("-t", "--target-dir", action="store", dest="target_dir",
                      default=default_target_dir,
                      help="Directory to download files. Default=%s" % default_target_dir)
    parser.add_option("-p", "--package-file", action="store", dest="package_file",
                      default=default_package_file, help="File containing package definitions. Default=%s" % default_package_file)
    parser.add_option("-c", "--config-file", action="store", dest="config_file",
                      default=None, help="Configuration file. Default is None.")
    parser.add_option("-m", "--platform", action="store", dest="platform",
                      default=default_platform, help="Platform. Default is %s." % default_platform)
    parser.add_option("-d", "--dry-run", action="store_true", dest="dry_run",
                      default=False, help="If specified, print what would be done, but do not actually download files.")
    parser.add_option("--stop-on-checksum-mismatch", action="store_true", dest="stop_on_checksum_mismatch",
                      default=False, help="If specified, stop if a local file does not match checksum (rather than attempting to redownload the file)")

    (options, args) = parser.parse_args(argv)

    if not test_for_wget():
        parser.error("Unable to find wget executable")

    if not os.path.isdir(options.target_dir):
        parser.error("Target directory %s does not exist" % options.target_dir)
    print "Copying to %s" % options.target_dir

    if not os.path.exists(options.package_file):
        parser.error("Package file %s does not exist" % options.package_file)

    if len(args) == 0:
        parser.error("Must specify either group or file")

    command = args[0]
    valid_commands = ["group", "file", "all"]
    if not (command in valid_commands):
        parser.error("Invalid command %s, must be one of %s" % (command, valid_commands))

    command_args = args[1:]

    with open(options.package_file, "rb") as pf:
        packages = json.load(pf)

    if options.config_file:
        with open(options.config_file, "rb") as cf:
            config = json.load(cf)
    else:
        config = {}

    pm = PackageMgr(options.target_dir, config, packages, options.platform, options.dry_run,
                    options.stop_on_checksum_mismatch)
    if command == "group":
        pm.download_by_group(command_args)
    elif command == "file":
        pm.download_by_filename(command_args)
    else:
        pm.download_all()
    print "Completed command successfully (%s files downloaded, %s files already present)." % (pm.files_downloaded, pm.files_already_present)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

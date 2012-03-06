"""Utility functions for collecting information about the
system we're running on.
"""
from subprocess import Popen, PIPE
import getpass
import platform
import os.path
import string
import socket

def _run_subproc_and_get_output(args):
    return Popen(args, stdout=PIPE, shell=True).communicate()[0]

SUPPORTED_PLATFORMS=["linux", "linux64", "macosx", "macosx64"]


def get_platform():
    """We have a standard categorization of os platforms and architectures that we use.
    Currently supported platforms are in SUPPORTED_PLATFORMS.
    """
    uname = (_run_subproc_and_get_output("uname")).rstrip()
    if uname == "Darwin":
        release = (_run_subproc_and_get_output("uname -r")).rstrip().split('.')
        major = int(release[0])
        assert major >= 9, "Mac OS release expected to be 9 or greater, actual was %s" % major
        if major >= 10:
            platform = "macosx64"
        else:
            platform = "macosx"
    elif uname == 'Linux':
        uname_m = (_run_subproc_and_get_output("uname -m")).rstrip()
        if uname_m == 'x86_64':
            platform = 'linux64'
        else:
            platform = 'linux'
    else:
        raise Exception("unknown platform type. uname returned %s" % uname)
    assert platform in SUPPORTED_PLATFORMS, "Unexpected platform %s" % platform
    return platform

# Constants defining OS descriptions and resource keys.
# A given app can support all or a proper subset of these.
LINUX_UBUNTU_11 = "Ubuntu Linux 11.10"
LINUX_UBUNTU_11_64BIT = "Ubuntu Linux 11.10 (64-bit)"
LINUX_UBUNTU_10_64BIT = "Ubuntu Linux 10.04 (64-bit)"
MACOSX_10_5 = "MacOSX 10.5 (Leopard)"
MACOSX_10_6 = "MacOSX 10.6 (Snow Leopard)"

os_keys = {
    LINUX_UBUNTU_11: {u"name": u"ubuntu-linux", u"version": u"11.10"},
    LINUX_UBUNTU_11_64BIT: {u"name": u"ubuntu-linux", u"version": u"11.10"},
    LINUX_UBUNTU_10_64BIT: {u"name": u"ubuntu-linux", u"version": u"10.04"},
    MACOSX_10_5: {u"name": u"mac-osx", u"version": u"10.5"},
    MACOSX_10_6: {u"name": u"mac-osx", u"version": u"10.6"}
}

os_arches = {
    LINUX_UBUNTU_11: "i386",
    LINUX_UBUNTU_10_64BIT: "x86_64",
    LINUX_UBUNTU_11_64BIT: "x86_64",
    MACOSX_10_5: "i386",
    MACOSX_10_6: "x86_64"
}

default_os_choices = [LINUX_UBUNTU_11, LINUX_UBUNTU_11_64BIT,
                      LINUX_UBUNTU_10_64BIT,
                      MACOSX_10_5, MACOSX_10_6]

def get_ip_for_interface(interface_name):
    """Given an interface name, run ifconfig and return the
    ip address of that interface. Returns None if it runs into
    problems. This currently only works on Linux. OSX uses
    a slightly different format.
    """
    import subprocess
    cmd = "ifconfig %s | grep 'inet addr'" % interface_name
    try:
        subproc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, shell=True)
        subproc.stdin.close()
        r = subproc.stdout.read().rstrip()
        subproc.wait()
        if subproc.returncode != 0:
            return None
        r = r.lstrip()
        addr = r.split()[1][5:]
        if len(addr.split(".")) == 4:
            return addr
        else:
            return None
    except: # if we run into a problem, just assume we don't have a that interface or an ip
        return None
         


def get_machine_info(os_choices=default_os_choices):
    """Get the key indentifying information about the current machine and
    return it as an in-memory Json representation (dictionaries). os_choices
    is a list of operating systems supported by the application. This list is
    also included in the resulting json structure.
    """
    (system, node, release, version, machine, processor) = platform.uname()
    os_type = None
    if system == "Darwin":
        if release[0:2] == "9.": os_type = MACOSX_10_5
        elif release[0:3] == "10.": os_type = MACOSX_10_6
        private_ip = None
        public_ip = socket.gethostbyname(socket.gethostname())
    elif system == "Linux":
        # Each linux distribution has its own file in /etc with info about the
        # distribution name and version. We need to have a special case for
        # eqch file to parse the unique format!
        if os.path.exists("/etc/lsb-release"): # e.g. Ubuntu
            os_info_file = open("/etc/lsb-release", "r")
            info = {}
            for line in os_info_file:
                kv = string.split(line, "=")
                if len(kv) == 2: info[kv[0]] = kv[1].rstrip()
            os_info_file.close()
            if info.has_key("DISTRIB_ID") and info.has_key("DISTRIB_RELEASE"):
                os_type = "%s Linux %s" % (info["DISTRIB_ID"], info["DISTRIB_RELEASE"])
                if machine == "x86_64":
                    # we distinguish the 64-bit build by adding "(64-bit)" to the base ubuntu os name
                    os_type = "%s (64-bit)" % os_type
        elif os.path.exists("/etc/redhat-release"): # e.g. CentOS
            os_info_file = open("/etc/redhat-release", "r")
            line = os_info_file.readline()
            os_info_file.close()
            info = string.split(line, " ")
            os_type = "%s Linux %s" % (info[0], info[2])
        # figure out what is the private interface, if there is one
        ip0 = get_ip_for_interface("eth0")
        ip1 = get_ip_for_interface("eth1")
        private_ip = None
        public_ip = None
        if ip0:
            if ip0.startswith("10."):
                private_ip = ip0
            else:
                public_ip = ip0
        if ip1:
            if ip1.startswith("10."):
                if not private_ip:
                    private_ip = ip1
            else:
                if not public_ip:
                    public_ip = ip1
            
    info = {"hostname":node, "username": getpass.getuser(),
            "os_choices": os_choices, "private_ip":private_ip,
            "public_ip":public_ip}
    if (os_type != None) and (os_type in os_choices): info["os"] = os_type
    return info


def get_target_machine_resource(id, hostname, username, password, os_desc, private_ip):
    key = os_keys[os_desc]
    arch = os_arches[os_desc]
    return {
        u"id":id,
        u"key": key,
        u"properties": {
            u"installed": True,
            u"use_as_install_target": True
        },
        u"config_port": {
            u"hostname":hostname,
            u"os_user_name": username,
            u"sudo_password": password,
            u"cpu_arch": arch,
            u"private_ip": private_ip
        }
    }

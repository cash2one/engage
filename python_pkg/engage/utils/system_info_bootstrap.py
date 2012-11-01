"""Subset of system_info that is required for bootstrap.py
"""
from subprocess import Popen, PIPE

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

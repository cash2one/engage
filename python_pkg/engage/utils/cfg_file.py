"""Some utilities specific to modifying config files.
"""

import os
import os.path
import sys
import logging
import tempfile
import shutil

import engage_utils.process as processutils
import file as fileutils

from log_setup import setup_engage_logger
logger = setup_engage_logger(__name__)

from regexp import *

def _get_config_line_regexps(line):
    """
    >>> (p1, p2) = _get_config_line_regexps("this test")
    >>> r1 = p1.compile()
    >>> r2 = p2.compile()
    >>> r1.match("this test") is not None
    True
    >>> r1.match("this testx") is not None
    False
    >>> r1.match("this test ") is not None
    True
    >>> r1.match("this test # sdkdj") is not None
    True
    >>> r1.match("  this test") is not None
    True
    >>> r1.match("# this test") is not None
    False
    >>> r2.match("# this test") is not None
    True
    >>> r2.match("## this test") is not None
    True
    >>> r2.match("# this test # comment") is not None
    True
    >>> r2.match("this test") is not None
    False
    >>> r2.match("# this test xyz") is not None
    False
    >>> r2.match(" # this test") is not None
    True
    """
    opt_whitespace = zero_or_more(whitespace_char())
    line_pat = line_ends_with(concat(opt_whitespace,
                                     lit(line),
                                     opt_whitespace,
                                     zero_or_one(concat(lit('#'),
                                                        zero_or_more(any_except_newline())))))
    commented_line_pat = concat(opt_whitespace, one_or_more(lit('#')), opt_whitespace, line_pat)
    return (line_pat, commented_line_pat)


def _add_config_file_line(config_file, line):
    """We want to itempotently add a config file entry to the config file.
    There are three cases we handle:
     * If it is not there, we just append it to the end of the file along with a comment
     * If it is there, but is commented out, we uncomment the line
     * If it is there, and is not commented out, we leave the file alone
    """
    (line_pat, cmt_pat) = _get_config_line_regexps(line)
    line_re = line_pat.compile()
    cmt_re = cmt_pat.compile()
    line_match_count = 0
    comment_match_count = 0
    with open(config_file, "r") as f:
        for l in f:
            if line_re.match(l):
                line_match_count += 1
            elif cmt_re.match(l):
                comment_match_count += 1
    if line_match_count > 0:
        logger.debug("Config line '%s' already in config file '%s'" %
                     (line, config_file))
        return

    # if there already is .orig file, we leave it alone and create a temp
    # file for our work.
    if os.path.exists(config_file + ".orig"):
        tf = tempfile.NamedTemporaryFile(delete=False)
        backup_file_name = tf.name
        tf.close()
        delete_backup_file_when_done = True
    else:
        backup_file_name = config_file + ".orig"
        delete_backup_file_when_done = False

    conf_file_perms = fileutils.get_file_permissions(config_file)
    os.rename(config_file, backup_file_name)
    try:
        if line_match_count==0 and comment_match_count==0:
            shutil.copy(backup_file_name, config_file)
            with open(config_file, "a") as f:
                import datetime
                f.write("# Added by Engage %s\n" % datetime.datetime.now().strftime("%Y-%m-%d"))
                f.write(line+"\n")
            logger.debug("Added config line '%s' to config file '%s'" %
                         (line, config_file))
        else:
            # find the commented version and uncomment
            found = False
            with open(backup_file_name, "r") as rf:
                with open(config_file, "w") as wf:
                    for l in rf:
                        if (not found) and cmt_re.match(l):
                            # we take the line starting at the
                            # beginning of the actual config
                            # string.
                            m = lit(line).compile().search(l)
                            wf.write(l[m.start():])
                            found = True
                        else:
                            wf.write(l)
            assert found
            logger.debug("Uncommented config line '%s' in config file '%s'" %
                         (line, config_file))
    except:
        # if we got an error, move back the original config file
        os.rename(backup_file_name, config_file)
        raise
    fileutils.set_file_permissions(config_file, conf_file_perms)
    if delete_backup_file_when_done:
        os.remove(backup_file_name)

def add_config_file_line(config_file, line, sudo_password):
    """Add line to config file (see above for detailed description).
    This is just a wrapper over _add_config_file_line(). Unless we are
    running as root, we need to spawn a subprocess and run it under sudo
    """ 
    if processutils.is_running_as_root():
        _add_config_file_line(config_file, line)
    else:
        processutils.run_sudo_program([sys.executable, __file__, config_file, line],
                                   sudo_password, logger)

def is_config_line_present(config_file, line):
    """Return True if line is present in the file and not commented out,
    False otherwise.
    """
    (line_pat, cmt_line_pat) = _get_config_line_regexps(line)
    line_re = line_pat.compile()
    with open(config_file, "r") as f:
        for l in f:
            if line_re.match(l):
                return True
    return False

if __name__ == "__main__":
    """For the add_config_file() functionality, we need to run this same program
    as an sudo subprocess.
    """
    args = sys.argv[1:]
    if len(args)!=2:
        print "%s <config_file> <line>" % sys.argv[0]
        sys.exit(1)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    _add_config_file_line(args[0], args[1])
    print "_add_config_file_line was successful"
    sys.exit(0)
    


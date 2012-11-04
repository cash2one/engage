# subset of process module needed for bootstrap.py and upgrade.py
# utilities for dealing with (sub)processes

import subprocess
import os
import sys


def system(shell_command_string, logger, log_output_as_info=False, cwd=None):
    """Replacement for os.system(), which doesn't handle return codes correctly.
    We also do logging. Set log_output_as_info to True if you have a really
    long-running action.
    Returns the exit code of the child process.

    run_and_log_programm() is still preferred, as it is more
    robust."""
    logger.debug(shell_command_string)
    if log_output_as_info: log_fn = logger.info
    else: log_fn = logger.debug
    subproc = subprocess.Popen(shell_command_string, shell=True,
                               cwd=cwd,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    for line in subproc.stdout:
        log_fn("[%d] %s" % (subproc.pid, line.rstrip()))
    (pid, exit_status) = os.waitpid(subproc.pid, 0)
    rc = exit_status >> 8 # the low byte is the signal ending the proc
    logger.debug("[%d] exited with return code %d" % (subproc.pid, rc))
    return rc


def run_and_log_program(program_and_args, env_mapping, logger, cwd=None,
                        input=None, hide_input=False,
                        hide_command=False, hide_environ=False, allow_broken_pipe=False):
    """Run the specified program as a subprocess and log its output.
    program_and_args should be a list of entries where the first is the
    executable path, and the rest are the arguments.
    """
    if not hide_command:
        logger.debug(' '.join(program_and_args))
    if cwd != None:
        logger.debug("Subprocess working directory is %s" % cwd)
    if env_mapping == None or len(env_mapping)>0 and (env_mapping==os.environ):
        logger.debug("Subprocess inheriting parent process's environment")
    elif len(env_mapping)>0:
        if not hide_environ:
            logger.debug("Subprocess environment is %s" % str(env_mapping))
    else:
        logger.debug("Subprocess passed empty environment")
    subproc = subprocess.Popen(program_and_args,
                               env=env_mapping, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, cwd=cwd)
    logger.debug("Started program %s, pid is %d" % (program_and_args[0],
                                                   subproc.pid))
    if input!=None:
        if not hide_input:
            logger.debug("Input is " + input)
        try:
            (output, dummy) = subproc.communicate(input)
            for line in output.split("\n"):
                logger.debug("[%d] %s" % (subproc.pid, line.rstrip()))
        except OSError:
            if not allow_broken_pipe:
                raise
            else:
                logger.warn("Subprocess %d closed stdin before write of input data complete" %
                            subproc.pid)
                for line in subproc.stdout:
                    logger.debug("[%d] %s" % (subproc.pid, line))
    else:
        subproc.stdin.close()
        for line in subproc.stdout:
            logger.debug("[%d] %s" % (subproc.pid, line))
    subproc.wait()
    logger.debug("[%d] %s exited with return code %d" % (subproc.pid,
                                                        program_and_args[0],
                                                        subproc.returncode))
    return subproc.returncode


_sudo_exe = "/usr/bin/sudo"

class SudoError(Exception):
    def get_nested_exc_info(self):
        return None


class SudoBadRc(SudoError):
    """This exception is thrown when the sudo operation returns a non-zero
    return code
    """
    def __init__(self, rc, program_and_args):
        self.rc = rc
        self.program_and_args = program_and_args

    def get_exc_info(self, current_exc_state):
        return current_exc_state

    def __str__(self):
        return "Sudo execution of '%s' failed, return code was %d" % (" ".join(self.program_and_args),
                                                                      self.rc)
    def __repr__(self):
        return "SudoBadRc(%d, %s)" % (self.rc, self.program_and_args.__repr__())


class SudoExcept(SudoError):
    """This exception is thrown when a sudo command throws an exception
    """
    def __init__(self, exc_info, program_and_args, rc=None):
        self.exc_info = exc_info
        (self.exc_type, self.exc_val, self.exc_tb) = exc_info
        self.program_and_args = program_and_args
        self.rc = rc

    def get_nested_exc_info(self):
        return self.exc_info

    def __str__(self):
        msg = "Sudo execution of '%s' failed, exception was '%s(%s)'" % (" ".join(self.program_and_args),
                                                                         self.exc_type, self.exc_val)
        if self.rc!=None:
            msg = msg + ", return code was %d" % self.rc
        return msg

    def __repr__(self):
        return "%s(%s, %s, rc=%s)" % (self.__class__.__name__, self.exc_info.__repr__(), self.program_and_args.__repr__(), self.rc)

class SudoTimestampError(SudoExcept):
    """This exception is thrown the timestamp clear operation failed
    """
    def __init__(self, exc_info, program_and_args, rc=None):
        SudoExcept.__init__(self, exc_info, program_and_args, rc)


class SudoTimestampBadRc(SudoError):
    """This exception is thrown when the sudo operation returns a non-zero
    return code
    """
    def __init__(self, rc, program_and_args):
        self.rc = rc
        self.program_and_args = program_and_args

    def get_exc_info(self, current_exc_state):
        return current_exc_state

    def __str__(self):
        return "Sudo execution of '%s' failed, return code was %d" % (" ".join(self.program_and_args),
                                                                      self.rc)
    def __repr__(self):
        return "SudoTimestampBadRc(%d, %s)" % (self.rc, self.program_and_args.__repr__())

def clear_sudo_timestamp(logger=None):
    """Clear the sudo timestamp to ensure that the password is always checked.
    """
    cmd = [_sudo_exe, "-K"]
    if logger: logger.debug(' '.join(cmd))
    try:
        subproc = subprocess.Popen(cmd, env={}, stdin=None,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, cwd=None)
        for line in subproc.stdout:
            if logger: logger.debug("[%d] %s" % (subproc.pid, line))
        subproc.wait()
    except:
        exc_info = sys.exc_info()
        sys.exc_clear()
        raise SudoTimestampError(exc_info, cmd)
    if subproc.returncode != 0:
        raise SudoTimestampBadRc(subproc.returncode, cmd)


def is_running_as_root():
    """If the effective user id is 0, then we
    are running as root (superuser).
    """
    return os.geteuid() == 0

def is_sudo_password_required(logger=None):
    assert os.geteuid() != 0, "check only valid when not running as root"
    clear_sudo_timestamp(logger)
    cmd = [_sudo_exe, "-n", "/bin/ls", "/"]
    try:
        subproc = subprocess.Popen(cmd, env={}, stdin=None,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, cwd=None)
        for line in subproc.stdout:
            if logger: logger.debug("[%d] %s" % (subproc.pid, line))
        subproc.wait()
    except Exception, e:
        if logger: logger.exception("Problem when checking for sudo access: %s" % e)
        raise
    if subproc.returncode==0:
        return False
    else:
        return True

# The SUDO_PASSWORD_REQUIRED variable has three values:
# True - running as a regular user and need a password to access sudo
# False - running as a regular user but can run sudo in non-interactive mode
# None - running as effective user 0 (root), sudo not needed at all
SUDO_PASSWORD_REQUIRED = is_sudo_password_required() if not is_running_as_root() \
                         else None


class NoPasswordError(SudoError):
    """If you attempt to call run_sudo_program without providing
    a password, and you aren't running as root, you get this error.
    """
    pass


def run_sudo_program(program_and_args, sudo_password,
                     logger, cwd=None, env={}, user="root"):
    """Wrapper over run and log program for programs running under sudo.
    It adds sudo and the -S option to the command arguments and then passes
    the password in as the standard input. The echoing of the standard input
    to the logger is supressed.

    If you want to run as a different user from root, specify the user name for the
    user keyword argument. This causes execution with the -s option.

    Note that we don't run under sudo if we're already running as root and want to
    run as root.
    """
    if SUDO_PASSWORD_REQUIRED==None: # running as root
        if user=="root":
            # if we are already root and want to run as root, no need to sudo
            rc = run_and_log_program(program_and_args, env, logger, cwd,
                                     input=None)
            if rc != 0:
                raise SudoBadRc(rc, program_and_args)
            else:
                return 0
        else:
            # do not need to pass in a password, since already root
            input_to_subproc = None
            opts = ["-n",]
    elif SUDO_PASSWORD_REQUIRED==False:
            input_to_subproc = None
            opts = ["-n",]
    elif sudo_password==None:
        raise NoPasswordError("Operation '%s' requires sudo access, but no password provided" % ' '.join(program_and_args))
    else:
        input_to_subproc = sudo_password + "\n"
        opts = ["-p", "", "-S"]
    
    # we need to clear the sudo timestamp first so that sudo always expects a password and doesn't
    # give us a broken pipe error
    clear_sudo_timestamp(logger)

    if user=="root":
        cmd = [_sudo_exe,] + opts + program_and_args
    else:
        cmd = [_sudo_exe, "-u", user] + opts + program_and_args
        
    try:
        rc =  run_and_log_program(cmd, {}, logger, cwd,
                                  input=input_to_subproc,
                                  hide_input=True, allow_broken_pipe=True)
        if rc != 0:
            raise SudoBadRc(rc, cmd)
        return rc
    except SudoBadRc:
        raise
    except:
        exc_info = sys.exc_info()
        sys.exc_clear()
        raise SudoExcept(exc_info, cmd)


# utilities for dealing with (sub)processes

import subprocess
import os
import os.path
import sys
import re
import tempfile
import signal
import time
import pwd
import grp

def get_pid_from_file(pidfile, resource_id=None, logger=None):
    if not os.path.exists(pidfile):
        if logger!=None and resource_id!=None:
            logger.debug("%s: server not up - pid file '%s' not found" %
                         (resource_id, pidfile))
        return None
    file = open(pidfile, "rb")
    data = file.read()
    file.close()
    pid = int(data)
    return pid

def run_and_log_program(program_and_args, env_mapping, logger, cwd=None,
                        input=None, hide_input=False,
                        hide_command=False, allow_broken_pipe=False):
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

class SudoError(Exception):
    def get_nested_exc_info(self):
        return None


class SudoBadRc(SudoError):
    """This exception is thrown the timestamp clear operation failed
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
        return "SudoExcept(%s, %s, rc=%s)" % (self.exc_info.__repr__(), self.program_and_args.__repr__(), self.rc)


# setup some executable paths used by some of the following utility functions
if sys.platform=="darwin":
    _cp_exe = "/bin/cp"
    _chmod_exe = "/bin/chmod"
    _chown_exe = "/usr/sbin/chown"
    _sudo_exe = "/usr/bin/sudo"
    _mkdir_exe = "/bin/mkdir"
    _cat_exe = "/bin/cat"
    _kill_exe = "/bin/kill"
    _rm_exe = "/bin/rm"
elif sys.platform=="linux2":
    _cp_exe = "/bin/cp"
    _chmod_exe = "/bin/chmod"
    _chown_exe = "/bin/chown"
    _sudo_exe = "/usr/bin/sudo"
    _mkdir_exe = '/bin/mkdir'
    _cat_exe = '/bin/cat'
    _kill_exe = '/bin/kill'
    _rm_exe = "/bin/rm"
else:
    raise Exception("engage.utils.process: Undefined plaform %s" % sys.platform)


def clear_sudo_timestamp(logger):
    """Clear the sudo timestamp to ensure that the password is always checked.
    """
    cmd = [_sudo_exe, "-K"]
    logger.debug(' '.join(cmd))
    try:
        subproc = subprocess.Popen(cmd, env={}, stdin=None,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, cwd=None)
        for line in subproc.stdout:
            logger.debug("[%d] %s" % (subproc.pid, line))
        subproc.wait()
    except:
        exc_info = sys.exc_info()
        sys.exc_clear()
        raise SudoExcept(exc_info, cmd)
    if subproc.returncode != 0:
        raise SudoBadRc(subproc.returncode, cmd)


def is_running_as_root():
    """If the effective user id is 0, then we
    are running as root (superuser).
    """
    return os.geteuid() == 0


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
    if is_running_as_root():
        if user=="root":
            # if we are already root wand want to run as root, no need to sudo
            rc = run_and_log_program(program_and_args, env, logger, cwd,
                                     input=None)
            if rc != 0:
                raise SudoBadRc(rc, program_and_args)
            return rc
        else:
            # do not need to pass in a password, since already root
            input_to_subproc = None
    elif sudo_password==None:
        raise NoPasswordError("Operation '%s' requires sudo access, but no password provided" % ' '.join(program_and_args))
    else:
        input_to_subproc = sudo_password + "\n"
    
    # we need to clear the sudo timestamp first so that sudo always expects a password and doesn't
    # give us a broken pipe error
    clear_sudo_timestamp(logger)

    if user=="root":
        cmd = [_sudo_exe, "-p", "", "-S"] + program_and_args
    else:
        cmd = [_sudo_exe, "-u", user, "-p", "", "-S"] + program_and_args
        
    try:
        rc =  run_and_log_program(cmd, {}, logger, cwd,
                                  input=input_to_subproc,
                                  hide_input=True, allow_broken_pipe=True)
        if rc != 0:
            raise SudoBadRc(rc, cmd)
        return rc
    except SudoBadRc, e:
        exc_info = sys.exc_info()
        sys.exc_clear()
        raise SudoExcept(exc_info, cmd, e.rc)
    except:
        exc_info = sys.exc_info()
        sys.exc_clear()
        raise SudoExcept(exc_info, cmd)


def test_sudo(sudo_password, program_and_args=["ls"], iterations=100):
    """Test function for sudo. This just checks for intermittent
    errors by running the same sudo command many times
    """
    import logging
    logger = logging.getLogger("test_sudo")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    def action(msg):
        print "[ACTION] %s" % msg
    logger.debug = action
    for i in range(1, iterations):
        try:
            run_sudo_program(program_and_args, sudo_password, logger)
        except:
            print "failed in iteration %d" % i
            raise
    print "test successful"



def sudo_copy(copy_args, sudo_password, logger):
    """Copy files (as in the unix cp command) running as the superuser.
    copy_args is a list of arguments to the cp operation
    (e.g. [src_file, dest_file]).
    """
    cmd = [_cp_exe] + copy_args
    run_sudo_program(cmd, sudo_password, logger)


def _format_unix_mode_bits(mode):
    """
    >>> _format_unix_mode_bits(0755)
    '755'
    >>> _format_unix_mode_bits(01000755)
    '755'
    >>> _format_unix_mode_bits(0100)
    '100'
    >>> _format_unix_mode_bits(256)
    '400'
    >>> _format_unix_mode_bits(01)
    '001'
    >>> _format_unix_mode_bits(1)
    '001'
    >>> _format_unix_mode_bits(9)
    '011'
    
    """
    if type(mode)==str or type(mode)==unicode:
        return mode
    oct_mode = oct(mode)
    ln = len(oct_mode)
    if ln >= 3:
        return oct_mode[-3:]
    elif ln==2:
        return "0" + oct_mode
    elif ln==1:
        return "00" + oct_mode
    else:
        assert 0
        
def sudo_chmod(mode, files, sudo_password, logger):
    """Change file permissions (as in the chmod command) running as the superuser.
    """
    cmd = [_chmod_exe, _format_unix_mode_bits(mode)] + files
    run_sudo_program(cmd, sudo_password, logger)


def sudo_chown(user, targets, sudo_password, logger, recursive=False):
    """Change file ownership (as in the chown command) running as the superuser.
    """
    if recursive:
        cmd = [_chown_exe, "-R", user] + targets
    else:
        cmd = [_chown_exe, user] + targets
    run_sudo_program(cmd, sudo_password, logger)

def sudo_mkdir(dir_path, sudo_password, logger, create_intermediate_dirs=False):
    if create_intermediate_dirs:
        cmd = [_mkdir_exe, "-p", dir_path]
    else:
        cmd = [_mkdir_exe, dir_path]
    run_sudo_program(cmd, sudo_password, logger)

def sudo_set_file_permissions(path, user_id, group_id, mode_bits, logger, sudo_password):
    """Set the permissions of a file, running as root
    """
    assert os.path.exists(path), "sudo_set_file_permissions: File %s missing" % path
    user = pwd.getpwuid(user_id)[0]
    group = grp.getgrgid(group_id)[0]
    sudo_chown("%s:%s" % (user, group), [path], sudo_password, logger)
    sudo_chmod(mode_bits, [path], sudo_password, logger)

def sudo_ensure_user_in_group(group_name, logger, sudo_password, user=None):
    if user==None:
        user_id = os.getuid()
        user = pwd.getpwuid(user_id)[0]
    root_user = pwd.getpwuid(0)[0]
    if is_running_as_root() and user==root_user:
        logger.debug("Running as root, no need to ensure user is in group '%s'" % group_name)
        return
    else:
        if sys.platform=="darwin":
            cmd = ["/usr/bin/dscl", "localhost", "-append",
                   "/Local/Default/Groups/%s" % group_name,
                   "GroupMembership", user]
        else:
            cmd = ['/usr/sbin/adduser', user, group_name]
        run_sudo_program(cmd, sudo_password, logger)


def sudo_cat_file(path, logger, sudo_password):
    """Use this to get the contents of a file that is only
    readable to root. Returns the contents of the file"""
    if is_running_as_root():
        with open(path, "r") as f:
            return f.read()

    if sudo_password==None:
        raise NoPasswordError("sudo_cat_file requires sudo password, but not password provided")
    
    # we need to clear the sudo timestamp first so that sudo always expects a password and doesn't
    # give us a broken pipe error
    clear_sudo_timestamp(logger)

    cmd = [_sudo_exe, "-p", "", "-S", _cat_exe, path]
    logger.debug(' '.join(cmd))
    subproc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    logger.debug("Started program %s, pid is %d" % (cmd[0],
                                                   subproc.pid))
    try:
        (output, err) = subproc.communicate(sudo_password + "\n")
        if len(err)>0:
            for line in err.split('\n'):
                logger.debug("[%d] %s" % (subproc.pid, line))
    except OSError:
        logger.warn("Subprocess %d closed stdin before write of input data complete" %
                    subproc.pid)
        output = '\n'.join(subproc.stdout)
        for line in subproc.stderr:
            logger.debug("[%d] %s" % (subproc.pid, line))
    subproc.wait()
    if subproc.returncode != 0:
        raise SudoBadRc(subproc.returncode, cmd)
    else:
        return output
    
    
def run_background_program(program_and_args, env_mapping, logfile, logger,
                           cwd=None, pidfile=None):
    """Start another process in the background. Does not wait for it to complete,
    but will check once to see if the process was terminated immediately. Returns
    0 if start was successful (either the program is still running or
    completed successfully).

    If pidfile is specified, write the pid out to that file.
    """
    log_dir = os.path.dirname(logfile)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    stdout = open(logfile, "wb")
    logger.debug(' '.join(program_and_args))
    subproc = subprocess.Popen(program_and_args,
                               env=env_mapping, stdin=subprocess.PIPE,
                               stdout=stdout,
                               stderr=subprocess.STDOUT, cwd=cwd)
    logger.debug("Started background program %s, pid is %d, output written to %s" %
                (program_and_args[0], subproc.pid, logfile))
    subproc.stdin.close()
    rc = subproc.poll()
    if rc==None:
        if pidfile:
            with open(pidfile, "w") as f:
                f.write("%d" % subproc.pid)
        return 0
    else: return rc


if sys.platform=="darwin":
    def is_process_alive(pid):
        subproc = subprocess.Popen(["ps", "-p", pid.__str__()],
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        subproc.stdin.close()
        result = subproc.stdout.read().splitlines()
	if len(result) == 2:
		return True
	else:
		return False
elif sys.platform=="linux2":
    def is_process_alive(pid):
        return os.path.exists("/proc/%d" % pid)
else:
    raise Exception("installutils.process.is_process_alive() not ported to platform %s" % sys.platform)


def check_server_status(pidfile, logger=None, resource_id=None,
                        remove_pidfile_if_dead_proc=False):
    """Check whether a server process is alive by grabbing its pid from the specified
    pidfile and then checking the liveness of that pid. If the pidfile doesn't
    exist, assume that server isn't alive. Returns the pid if the server is running
    and None if it isn't running.

    If logger and resource id are specified, we log this info to the logger at
    the debug level. Otherwise we just do our work silently.
    """
    pid = get_pid_from_file(pidfile, resource_id, logger)
    if pid==None:
        return None
    elif is_process_alive(pid)==False:
        if remove_pidfile_if_dead_proc:
            os.remove(pidfile)
        if logger!=None and resource_id!=None:
            logger.debug("%s: server not up - pid '%d' not running" %
                         (resource_id, pid))
        return None
    else:
        if logger!=None and resource_id!=None:
            logger.debug("%s: server up (pid %d)" %
                         (resource_id, pid))
        return pid
        

class ServerStopTimeout(Exception):
    """This exception used to signal that the server process did not respond
    to sigterm or sigkill without the specified timeout period.
    """
    pass


def stop_server_process(pidfile, logger, resource_id,
                        timeout_tries=10, force_stop=False):
    """Stop a server process whose pid is given by the pidfile.
    Sends sigterm to process, unless force_stop is True. Then check up
    to timeout_tries times, waiting 1 second between each try, to see if the
    process went away. Removes the pid file of the process after it is
    verified to be stopped.

    Returns the pid of the stopped process. If the process was not running
    to begin with, return None. Raises an exception if the process has not
    gone away after the timeout period.
    """
    pid = check_server_status(pidfile, logger, resource_id,
                              remove_pidfile_if_dead_proc=True)
    if not pid:
        return None

    if force_stop:
        signo = signal.SIGKILL
    else:
        signo = signal.SIGTERM

    logger.debug("%s: sending signal %d to process %d" %
                 (resource_id, signo, pid))
    os.kill(pid, signo)
    
    for t in range(timeout_tries):
        if is_process_alive(pid):
           time.sleep(1.0)
        else:
            os.remove(pidfile)
            logger.debug("%s: process %d stopped sucessfully" %
                         (resource_id, pid))
            return pid

    raise ServerStopTimeout("%s: unable to stop process %d" %
                            (resource_id, pid))


def run_server(program_and_args, env_mapping, logfile, logger, pidfile_name,
               cwd=None):
    """Start another process as a server. Does not wait for it to complete.
    Returns the process object for the process. If started successfully, the pid
    of the process is written to pidfile.
    """
    log_dir = os.path.dirname(logfile)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    stdout = open(logfile, "wb")
    logger.debug(' '.join(program_and_args))
    subproc = subprocess.Popen(program_and_args,
                               env=env_mapping, stdin=subprocess.PIPE,
                               stdout=stdout,
                               stderr=subprocess.STDOUT, cwd=cwd)
    logger.debug("Started server program %s, pid is %d, output written to %s" %
                (program_and_args[0], subproc.pid, logfile))
    subproc.stdin.close()
    if subproc.poll() == None: # still running
        pidfile = open(pidfile_name, "w")
        pidfile.write("%d" % subproc.pid)
        pidfile.close()
    return subproc


def sudo_run_server(program_and_args, env_mapping, logfile, logger,
                    sudo_password, cwd=None):
    """Script for running a server process as root. Unlike the vanilla
    run_server(), the program being run is responsible for creating a pidfile.
    We do this because, if we run under sudo, the child won't be the actual server
    process.
    """
    log_dir = os.path.dirname(logfile)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    stdout = open(logfile, "wb")
    try:
        if is_running_as_root():
            # if we are already root, run directly
            logger.debug(' '.join(program_and_args))
            subproc = subprocess.Popen(program_and_args,
                                       env=env_mapping, stdin=subprocess.PIPE,
                                       stdout=stdout,
                                       stderr=subprocess.STDOUT, cwd=cwd)
            logger.debug("Started server program %s, pid is %d, output written to %s" %
                        (program_and_args[0], subproc.pid, logfile))
            subproc.stdin.close()
            return subproc
        elif sudo_password==None:
            raise NoPasswordError("Operation '%s' requires sudo access, but no password provided" % ' '.join(program_and_args))

        # we need to clear the sudo timestamp first so that sudo always expects a password and doesn't
        # give us a broken pipe error
        clear_sudo_timestamp(logger)
        cmd = [_sudo_exe, "-p", "", "-S"] + program_and_args
        logger.debug(' '.join(cmd))
        subproc = subprocess.Popen(cmd,
                                   env=env_mapping, stdin=subprocess.PIPE,
                                   stdout=stdout,
                                   stderr=subprocess.STDOUT, cwd=cwd)
        logger.debug("Started sudo server program %s, pid is %d, output written to %s" %
                    (program_and_args[0], subproc.pid, logfile))
        subproc.stdin.write(sudo_password + "\n")
        subproc.stdin.close()
        return subproc
    finally:
        stdout.close()


def sudo_stop_server_process(pidfile, logger, resource_id,
                             sudo_password,
                             timeout_tries=10, force_stop=False):
    """This is a version of stop_server_process() for when the
    server was started under root. We need to use sudo to
    run the kill command
    """
    pid = check_server_status(pidfile, logger, resource_id,
                              remove_pidfile_if_dead_proc=True)
    if not pid:
        return None

    if force_stop:
        signo = signal.SIGKILL
    else:
        signo = signal.SIGTERM

    logger.debug("%s: sending signal %d to process %d" %
                 (resource_id, signo, pid))
    run_sudo_program([_kill_exe, str(signo), str(pid)], sudo_password,
                     logger)
    
    for t in range(timeout_tries):
        if is_process_alive(pid):
           time.sleep(1.0)
        else:
            run_sudo_program([_rm_exe, pidfile], sudo_password,
                             logger)
            logger.debug("%s: process %d stopped sucessfully" %
                         (resource_id, pid))
            return pid

    raise ServerStopTimeout("%s: unable to stop process %d" %
                            (resource_id, pid))


def run_program_and_scan_results(program_and_args, re_map, logger, env=None,
                                 cwd=None, input=None, log_output=False,
                                 allow_broken_pipe=False,
                                 return_mos=False,
                                 hide_command=False):
    """Run the specified program as a subprocess and scan its output for the
    regular expressions specified in re_map. re_map is a map from symbolic
    names to regular expression patterns. Returns a pair: the return code
    of the program followed by a map from the keys in re_map to booleans
    which indicate whether the associated pattern was found.

    If return_mos is True, then the result map will be from the symbolic
    names to lists of match objects or None, rather than True/False.
    """
    regexps = {}
    results = {}
    if return_mos:
        not_found_value = None
    else:
        not_found_value = False
    for key in re_map.keys():
        regexps[key] = re.compile(re_map[key])
        results[key] = not_found_value
    if not hide_command:
        logger.debug(' '.join(program_and_args))
    subproc = subprocess.Popen(program_and_args,
                               env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, cwd=cwd)
    logger.debug("Started program %s, pid is %d" % (program_and_args[0],
                                                   subproc.pid))
    lines = None
    try:
        (output, dummy) = subproc.communicate(input)
        lines = output.split("\n")
    except OSError:
        if not allow_broken_pipe:
            raise
        else:
            logger.warn("Subprocess %d closed stdin before write of input data complete" %
                        subproc.pid)
            if lines==None:
                lines = subproc.stdout
            
    for line in lines:
        if log_output:
            logger.debug("[%d] %s" % (subproc.pid, line))
        for key in regexps.keys():
            mo = regexps[key].search(line)
            if mo!=None:
                if return_mos:
                    if results[key]!=None:
                        results[key].append(mo)
                    else:
                        results[key] = [mo,]
                else:
                    results[key] = True
    subproc.wait()
    logger.debug("[%d] %s exited with return code %d" % (subproc.pid,
                                                        program_and_args[0],
                                                        subproc.returncode))
    return (subproc.returncode, results)


def run_sudo_program_and_scan_results(program_and_args, re_map, logger,
                                      sudo_password, env=None, cwd=None,
                                      log_output=False, return_mos=False):
    """Run a program under sudo and scan the results as described in
    run_program_and_scan_results()
    """
    if is_running_as_root():
        # if we are already root, no need to sudo
        return run_program_and_scan_results(program_and_args, re_map, logger,
                                            env=env, cwd=cwd,
                                            log_output=log_output,
                                            return_mos=return_mos)
    elif sudo_password==None:
        raise NoPasswordError("Operation '%s' requires sudo access, but no password provided" % ' '.join(program_and_args))
    
    # we need to clear the sudo timestamp first so that sudo always expects a password and doesn't
    # give us a broken pipe error
    clear_sudo_timestamp(logger)

    cmd = [_sudo_exe, "-p", "", "-S"] + program_and_args
    return run_program_and_scan_results(cmd, re_map, logger,
                                        env, cwd, input=sudo_password+"\n",
                                        log_output=log_output,
                                        return_mos=return_mos,
                                        allow_broken_pipe=True)
    

def find_matching_processes(process_pattern_list, exclude_pattern=None,
                            treat_patterns_as_literals=True):
    """Check the system for processes whose command names contain one
    of the specified patterns. process_pattern_list should be a list
    of regular expression patterns. If exclude_pattern is provided, we
    compare any candidate matching commands to that pattern. If the command
    contains the exclude_pattern, we drop it.

    If treat_patterns_as_literals is true, we run each pattern through
    re.escape(). Otherwise, we assume they are regular expressions

    Returns a list of (process_id, command) pairs.
    """
    if sys.platform == 'linux2':
        psargs = '-ef'
        pid_field = 1
        cmd_field = 7
    else:
        psargs = '-Ax'
        pid_field = 0
        cmd_field = 3

    subproc = subprocess.Popen(["/bin/ps", psargs],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    if treat_patterns_as_literals:
        pattern = '|'.join(["(%s)" % re.escape(process_name) for process_name in process_pattern_list])
    else:
        pattern = '|'.join(["(%s)" % process_name for process_name in process_pattern_list])
    regexp = re.compile(pattern)
    if exclude_pattern and treat_patterns_as_literals:
        exclude_regexp = re.compile(re.escape(exclude_pattern))
    elif exclude_pattern:
        exclude_regexp = re.compile(exclude_pattern)
    else:
        exclude_regexp = None
    result = []
    for line in subproc.stdout:
        fields = line.split()
        cmd = ' '.join(fields[cmd_field:])
        if regexp.search(cmd):
            if exclude_regexp and exclude_regexp.search(cmd):
                continue
            fields = line.split()
            result.append((int(fields[pid_field]), cmd))
    (pid, exit_status) = os.waitpid(subproc.pid, 0)
    return result
    

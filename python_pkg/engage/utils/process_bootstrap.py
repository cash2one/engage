# subset of process module needed for bootstrap.py
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


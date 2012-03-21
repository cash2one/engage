
import os
import os.path
import sys
import stat
import resource

def _setup_fds(log_file):
    stdin = os.open("/dev/null", os.O_RDONLY)
    stdout = os.open(log_file, os.O_WRONLY)
    stderr = os.dup(stdout)
    sys.stdout = os.fdopen(stdout, "w")
    sys.stderr = os.fdopen(stderr, "w")

def daemonize(exe_path, args, log_file, cwd):
    if not os.path.exists(log_file):
        os.mknod(log_file, 0644, stat.S_IFREG)
    os.closerange(0, resource.RLIMIT_NOFILE)
    _setup_fds(log_file)
    pid = os.fork()
    if pid==0: # child
        sys.stdout.write("Starting %s" % exe_path)
        sys.stdout.flush()
        os.chdir(cwd)
        os.execv(exe_path, [exe_path,]+args)
    else:
        sys.stdout.close()
        sys.stderr.close()
        return pid

if __name__=="__main__":
    if len(sys.argv)<4:
        sys.stderr.write("daemonize.py exe_path log_file cwd [arg1 arg2 ...]\n")
        sys.exit(1)
    exe_path = sys.argv[1]
    log_file = sys.argv[2]
    cwd = sys.argv[3]
    args = sys.argv[4:]
    if not os.path.exists(exe_path):
        sys.stderr.write("Executable %s not found\n" % exe_path)
        sys.exit(1)
    log_dir = os.path.dirname(log_file)
    if not os.path.isdir(log_dir):
        os.makedirs(log_dir)

    daemonize(exe_path, args, log_file, cwd)
    sys.exit(0)


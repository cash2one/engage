
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

def fixpath(path):
    return os.path.abspath(os.path.expanduser(path))

def detach(cwd):
    os.closerange(0, resource.RLIMIT_NOFILE)
    os.chdir(cwd)
    os.setsid() # detach from parent session
    os.umask(0)
    
def daemonize(exe_path, args, log_file, cwd, pid_file=None):
    if not os.path.exists(log_file):
        with open(log_file, "w") as f:
            f.write("Starting %s %s" % (exe_path, ' '.join(args)))
            f.flush()
    
    pid = os.fork()
    if pid==0: # child
        detach(cwd)
        pid = os.fork()
        if pid==0: # grandchild
            if pid_file:
                with open(pid_file, "w") as f:
                    f.write(str(os.getpid()))
            detach(cwd)
            _setup_fds(log_file)
            os.execv(exe_path, [exe_path,]+args)
        else: # child
            sys.exit(0)
    else: # parent
        if pid_file:
            print "Forked child, log file is %s, pid file is %s" % \
                  (log_file, pid_file)
        else:
            print "Forked child, log file is %s" % log_file
        return

def print_usage(rc):
    sys.stderr.write("daemonize.py exe_path [--pid-file=pid_file] log_file cwd [arg1 arg2 ...]\n")
    sys.exit(rc)
    
if __name__=="__main__":
    if len(sys.argv)==2 and (sys.argv[1]=="--help" or sys.argv[1]=="-h"):
        print_usage(0)
    elif len(sys.argv)<4:
        print_usage(1)
    exe_path = sys.argv[1]
    if sys.argv[2].startswith("--pid-file="):
        if len(sys.argv)<5:
            print_usage(1) # need an extra slot for pid file arg
        pid_file = fixpath(sys.argv[2][len("--pid-file="):])
        pid_file_dir = os.path.dirname(pid_file)
        if not os.path.exists(pid_file_dir):
            os.makedirs(pid_file_dir)
        log_file = fixpath(sys.argv[3])
        cwd = sys.argv[4]
        args = sys.argv[5:]
    else:
        pid_file = None
        log_file = fixpath(sys.argv[2])
        cwd = fixpath(sys.argv[3])
        args = sys.argv[4:]
    if not os.path.exists(exe_path):
        sys.stderr.write("Executable %s not found\n" % exe_path)
        sys.exit(1)
    log_dir = os.path.dirname(log_file)
    if not os.path.isdir(log_dir):
        os.makedirs(log_dir)

    daemonize(exe_path, args, log_file, cwd, pid_file=pid_file)
    sys.exit(0)


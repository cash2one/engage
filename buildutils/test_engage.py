import nose
import optparse
import os.path
import random
import shutil
import string
import subprocess
import sys

if sys.version_info[0]!=2 or sys.version_info[1]<6:
    raise Exception("""Engage requires Python version 2.6 or 2.7,
but test_engage.py was started with Python %d.%d (at %s)""" %
                    (sys.version_info[0], sys.version_info[1], sys.executable))

join = os.path.join

def selfjoin(path):
    return os.path.normpath(join(os.path.dirname(os.path.abspath(__file__)), path))

PACKAGE = 'engage'
ENGAGE_DIR = selfjoin('..') # main engage dir is one level above this file
SRC_DIR = selfjoin('../python_pkg/%s' % PACKAGE)
OUTPUT_DIR = selfjoin('../test_output')

def shell(command):
    """Run shell command and return tuple of (stdout, stderr, returncode)"""
    proc = subprocess.Popen(command, shell=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    return stdout, stderr, proc.returncode

def bootstrap(deploy_dir, engage_dir=ENGAGE_DIR):
    (o, e, rc) = shell('%s %s --include-test-data %s' %
                       (sys.executable, join(engage_dir, 'bootstrap.py'),
                        deploy_dir))
    if rc != 0:
        sys.stdout.write(o)
        sys.stdout.write(e)
        sys.stdout.flush()
        raise Exception("Engage bootstrap at directoy %s failed. Return code was %d" %
                        (deploy_dir, rc))

def random_str(length=6, charspace=string.ascii_lowercase+string.digits):
    return ''.join(random.sample(charspace, length))

def get_randomized_deploy_dir(dirname_prefix, base_dir=OUTPUT_DIR):
    return join(base_dir, '%s%s' % (dirname_prefix, random_str()))

def main():
    op = optparse.OptionParser()
    op.add_option('-c', '--collect-only', action='store_true', default=False)
    op.add_option('-x', '--xunit-file')
    op.add_option('-d', '--demos-dir')
    opts, _args = op.parse_args()

    argv = ['--verbose', '--with-doctest']
    if opts.xunit_file:
        argv.extend(['--with-xunit', '--xunit-file=%s' % opts.xunit_file])
    if opts.collect_only:
        argv.append('--collect-only')

    if opts.demos_dir:
        deploy_dir = get_randomized_deploy_dir('test_demos_')
    else:
        deploy_dir = get_randomized_deploy_dir('test_engage_')
    print 'bootstrapping %s' % deploy_dir
    bootstrap(deploy_dir)
    activate_path = join(deploy_dir, 'engage/bin/activate')
    pkg_file = shell('. %s && python -c "import %s; print %s.__file__"' % \
                         (activate_path, PACKAGE, PACKAGE))[0]
    test_dir = os.path.expanduser(opts.demos_dir) \
        if opts.demos_dir else os.path.dirname(pkg_file)
    argv.append('--where=%s' % test_dir)
    noseargs = ' '.join(argv)
    # Use --exe to look for tests in modules that are sometimes inexplicably executable
    command = '. %s && nosetests --exe %s' % (activate_path, noseargs)
    print command
    print
    stdout, stderr, returncode = shell(command)
    print stdout
    print
    print stderr
    if returncode == 0:
        shutil.rmtree(deploy_dir)
    return returncode

if __name__ == '__main__':
    sys.exit(main())

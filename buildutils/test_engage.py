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
BUILD_DIR = selfjoin('../test_output')

def shell(command):
    """Run shell command and return tuple of (stdout, stderr, returncode)"""
    proc = subprocess.Popen(command, shell=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    return stdout, stderr, proc.returncode

def bootstrap(deploy_dir, engage_dir=ENGAGE_DIR):
    shell('%s %s %s' % (sys.executable, join(engage_dir, 'bootstrap.py'), deploy_dir))

def random_str(length=6, charspace=string.ascii_lowercase+string.digits):
    return ''.join(random.sample(charspace, length))

def get_randomized_deploy_dir(dirname_prefix, base_dir=BUILD_DIR):
    return join(base_dir, '%s%s' % (dirname_prefix, random_str()))

def main():
    op = optparse.OptionParser()
    op.add_option('-c', '--collect-only', action='store_true', default=False)
    op.add_option('-s', '--use-src', action='store_true', default=False)
    op.add_option('-x', '--xunit-file')
    opts, _args = op.parse_args()

    argv = ['--verbose', '--with-doctest']
    if opts.xunit_file:
        argv.extend(['--with-xunit', '--xunit-file=%s' % opts.xunit_file])
    if opts.collect_only:
        argv.append('--collect-only')

    if opts.use_src:
        argv.append('--where=%s' % SRC_DIR)
        print argv
        nose.main(argv=argv)
    else:
        deploy_dir = get_randomized_deploy_dir('test_engage_')
        bootstrap(deploy_dir)
        activate_path = join(deploy_dir, 'engage/bin/activate')
        pkg_file = shell('. %s && python -c "import %s; print %s.__file__"' % \
                             (activate_path, PACKAGE, PACKAGE))[0]
        test_dir =  os.path.dirname(pkg_file)
        argv.append('--where=%s' % test_dir)
        noseargs = ' '.join(argv)
        # Why are the *.py files executible on linux? Not sure, but this will fix it
        chmod_cmd = 'find %s -name "*.py" -exec chmod -x {} \;' % test_dir
        subprocess.check_call(chmod_cmd, shell=True)
        command = '. %s && nosetests %s' % (activate_path, noseargs)
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

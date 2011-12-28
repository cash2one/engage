import httplib
import json
import logging
import os.path
import random
import socket
import string
import subprocess
import sys

join = os.path.join

"""Common installer testing functions and parameters"""

THIS_DIR = os.path.dirname(os.path.abspath(__file__))

INSTALLER_DEFAULTS = {
    'hostname': 'localhost',
    'port': 8000,
    'websvr_hostname': 'localhost',
    'websvr_port': 8000,
    'app_admin_password': 'test',
    'log_directory': '',
    'home': 'django_app',
    'admin_email': 'admin@example.com',
    'configuration option': '1',
    'expected_exit_code': 0,
    'expected_url_codes': [('http://{host}:{port}', 200)]}

DEFAULT_MASTER_PASSWORD = 'testpass'

def find_dir(name, path=THIS_DIR):
    """Recursively climb path to find named directory"""
    if not path or path == '/':
        return None
    entries = os.listdir(path)
    if name in entries:
        found = os.path.join(path, name)
        if os.path.isdir(found):
            return found
    return find_dir(name, os.path.dirname(path))


logging.basicConfig(
    level=logging.DEBUG, format='%(asctime)s %(name)s %(levelname)s %(message)s')
logger = logging.getLogger('test_common')


BUILD_DIR = join(find_dir('build_output'))
if BUILD_DIR:
    ENGAGE_DIR = join(BUILD_DIR, 'engage')
else:
    SDIST_TEST_OUTPUT_DIR = find_dir("test_output")
    assert os.path.exists(SDIST_TEST_OUTPUT_DIR),\
        "Unable to find %s or %s directories, searching up from %s" % (
        BUILD_DIR, SDIST_TEST_OUTPUT_DIR, THIS_DIR)
    BUILD_DIR = SDIST_TEST_OUTPUT_DIR
    ENGAGE_DIR = os.path.abspath(join(BUILD_DIR, ".."))

logger.info("Running beneath %s" % BUILD_DIR)
assert os.path.exists(ENGAGE_DIR), \
    "Something is very wrong, engage directory %s does not exist" % ENGAGE_DIR

TEST_APP_DIR = join(BUILD_DIR, 'test_apps')


def assert_context(engage_dir):
    """Ensure environment conducive to running installers"""
    logger.debug('Checking for engage dir at %s' % engage_dir)
    if not os.path.exists(engage_dir):
        raise Exception('Engage must be built first (cd code && make engage)')
    logger.debug('Checking for ~/.pydistutils.cfg')
    if os.path.exists(os.path.expanduser("~/.pydistutils.cfg")):
        raise Exception('Please rename ~/.pydistutils.cfg before running this program')

def get_config(specific, defaults=INSTALLER_DEFAULTS):
    """Return overlay of specific dict onto defaults"""
    config = defaults.copy()
    config.update(specific)
    return config

def write_master_password(path, password=DEFAULT_MASTER_PASSWORD):
    with open(path, 'w') as f:
        f.write(password)
    os.chmod(path, 0600)
    return path

def write_config_file(deploy_dir, config_map, name='config.json'):
    """Write json contents of config_map in deploy_dir and return full path to file"""
    config_path = join(deploy_dir, name)
    with open(config_path, 'w') as f:
        json.dump(config_map, f)
    return config_path

def shell(command):
    """Run and return exit status of command"""
    return subprocess.call(command, shell=True)

def bootstrap(deploy_dir, engage_dir=ENGAGE_DIR):
    shell('%s %s %s' % (sys.executable, join(engage_dir, 'bootstrap.py'), deploy_dir))

def ensure_subdir(path, name):
    """Create named dir under path if necessary and return path"""
    subdir = os.path.join(path, name)
    if not os.path.exists(subdir):
        os.mkdir(subdir, 0755)
    return subdir

def install(deploy_dir, config_filename, master_password_file=None):
    command = 'cd %s && ./engage/bin/install --config-choices-file=%s' % (
        deploy_dir, config_filename)
    if master_password_file:
        command += ' --master-password-file=%s' % master_password_file
    logger.info('Installing with: %s' % command)
    return shell(command)

def upgrade(deploy_dir, engage_dir, application_archive, master_password_file=None):
    command = 'cd %s && %s upgrade.py --application-archive=%s' % (
        engage_dir, sys.executable, application_archive)
    if master_password_file:
        command += ' --master-password-file=%s' % master_password_file
    command += ' %s' % deploy_dir
    logger.info('Upgrading with: %s' % command)
    return shell(command)

def get_init_script(config_map):
    """Return path to init script"""
    return join(config_map['Install directory'], 'engage/bin/svcctl')

def stop(init_script, master_password_file):
    return shell('%s stop -p %s' % (init_script, master_password_file))

def random_str(length=6, charspace=string.ascii_lowercase+string.digits):
    return ''.join(random.sample(charspace, length))

def get_randomized_deploy_dir(dirname_prefix, base_dir=BUILD_DIR):
    return join(base_dir, '%s%s' % (dirname_prefix, random_str()))

def get_response(netloc, path, scheme='http'):
    """Return the response status for an http(s) request to netloc/path"""
    if scheme == 'http':
        conn = httplib.HTTPConnection(netloc)
    elif scheme == 'https':
        conn = httplib.HTTPSConnection(netloc)
    conn.request('GET', path)
    resp = conn.getresponse()
    return resp.status

def port_is_available(netloc):
    """Host:port is available if making request to it results in socket.error"""
    try:
        get_response(netloc, '')
    except socket.error:
        return True
    else:
        return False

def get_netloc(config_map):
    """Return host:port obtained from config_map"""
    return '%s:%s' % (config_map['websvr_hostname'], config_map['websvr_port'])


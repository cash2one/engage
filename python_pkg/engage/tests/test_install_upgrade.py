import os.path
import shutil
import time
import urlparse
import sys

try:
    import engage
except:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import engage.tests.test_common as tc
from engage.engine.cmdline_install import APPLICATION_ARCHIVE_PROP
from engage.engine.password import create_password_db

join = os.path.join

INSTALLERS = {
    'tomcat': {
        'hello': {
            'install': {
                APPLICATION_ARCHIVE_PROP: join(tc.TEST_APP_DIR, 'tomcat_hello.war'),
                'websvr_port': 8080, # for checking response
                'manager_port': 8080,
                'password_map': {'apache-tomcat/admin_password': 'testpass'}
                },
            }
        },
    'django': {
        'test-app': {
            'install': {
                APPLICATION_ARCHIVE_PROP: join(tc.TEST_APP_DIR, 'django_test_app_v1.tgz')},
            'upgrade': {
                APPLICATION_ARCHIVE_PROP: join(tc.TEST_APP_DIR, 'django_test_app_v2.tgz')}
            }
        }
    }


OPERATIONS = ['install', 'upgrade']


def app_is_available(config_map):
    """Determine availability by making requests based on url templates"""
    templates = config_map['expected_url_codes']
    host = config_map['websvr_hostname']
    port = config_map['websvr_port']

    urls = [(tmpl.format(host=host, port=port), ex) for (tmpl, ex) in templates]
    tc.logger.debug('Checking app availability at %s' % urls)
    got_expected = []
    try:
        for (url, expect) in urls:
            _scheme, netloc, path, _query, _fragment = urlparse.urlsplit(url)
            got_expected.append(expect == tc.get_response(netloc, path))
        return all(got_expected)
    except:
        tc.logger.exception('Exception while getting response')
        return False

def run_operations(installer_name, app_name):
    deploy_dir = tc.get_randomized_deploy_dir('test_install_')
    master_password_file = join(deploy_dir, 'master_password')

    operations = INSTALLERS[installer_name][app_name].keys()
    for operation in OPERATIONS: # retain correct order
        if operation not in operations:
            continue
        config_map = tc.get_config(INSTALLERS[installer_name][app_name][operation])
        config_map['Installer'] = installer_name
        config_map['Install directory'] = deploy_dir

        if operation == 'install':
            assert tc.port_is_available(tc.get_netloc(config_map))
            tc.bootstrap(deploy_dir)
            tc.write_master_password(master_password_file)
            config_dir = tc.ensure_subdir(deploy_dir, 'config')
            config_path = tc.write_config_file(config_dir, config_map)
            if 'password_map' in config_map:
                create_password_db(deploy_dir, tc.DEFAULT_MASTER_PASSWORD,
                                   config_map['password_map'])
            exit_code = tc.install(deploy_dir, config_path, master_password_file)

        elif operation == 'upgrade':
            exit_code = tc.upgrade(deploy_dir, tc.ENGAGE_DIR,
                                   config_map[APPLICATION_ARCHIVE_PROP],
                                   master_password_file)

        assert config_map['expected_exit_code'] == exit_code
        time.sleep(1) # allow for delayed start
        assert app_is_available(config_map)
        if operation == 'upgrade' or len(operations) == 1:
            # only shutdown on install if it's the only operation
            tc.stop(tc.get_init_script(config_map), master_password_file)
            assert tc.port_is_available(tc.get_netloc(config_map))
    tc.logger.info('removing %s' % (deploy_dir))
    shutil.rmtree(deploy_dir)

def test_install_upgrade_generator():
    """Generate install+upgrade tests based on INSTALLERS tree"""
    tc.assert_context(tc.ENGAGE_DIR)
    for installer_name in INSTALLERS:
        for app_name in INSTALLERS[installer_name]:
            yield run_operations, installer_name, app_name


# You can run this test file as a main script. By default,
# this will execute all the install_upgrade tests. You can also
# run individual tests via the apps and installer command line options.
if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("--installer", dest="installer", default="django",
                      help="installer name, default is django (used with --apps option)")
    parser.add_option("--apps", dest="apps", default=None,
                  help="list of apps to test (defaults to all)")
    (opts, args) = parser.parse_args()
    if opts.apps:
        app_list = opts.apps.split(",")
    else:
        app_list = INSTALLERS[opts.installer].keys()
    for app in app_list:
        run_operations(opts.installer, app)
    sys.exit(0)

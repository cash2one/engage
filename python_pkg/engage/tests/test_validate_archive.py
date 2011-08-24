import logging
import os.path
import shutil
import sys
import tempfile

from engage.tests.test_common import BUILD_DIR, shell

join = os.path.join

"""When run from nose, generate tests for as many apps as keys in
APP_ARCHIVE that it can also locate in build_output."""

APP_ARCHIVE = {
    'fc':
        {'file': 'fc-1.0.tar.gz',
         'module': 'gffc'},
    'gfwebsite':
        {'file': 'genforma_website.tar.gz',
         'module': 'gfmainsite'}}

# paths below are relative to build_output
PATHS = {
    'validator':
        {'Darwin': '{appname}/genforma.app/Contents/Frameworks/content/genforma/engage_django_sdk/packager/runtests.py',
         'Linux': '{appname}/genforma_installer/lib/content/genforma/engage_django_sdk/packager/runtests.py'},
    'archive':
        {'Darwin': '{appname}/genforma.app/Contents/Frameworks/sw_packages/{file}',
         'Linux': '{appname}/genforma_installer/sw_packages/{file}'}}

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)s %(levelname)s %(message)s')
logger = logging.getLogger('test_validate_archive')

OSNAME = os.uname()[0]

def archive_path(appname):
    file = APP_ARCHIVE[appname]['file']
    return join(BUILD_DIR, PATHS['archive'][OSNAME].format(appname=appname, file=file))

def test_generator(appnames=APP_ARCHIVE.keys()):
    """Generate tests for as many apps as are both keys in APP_ARCHIVE
    and also exist in build_output"""
    for appname in appnames:
        if os.path.exists(archive_path(appname)):
            yield validate, appname

def validate(appname):
    logger.debug('Validating %s archive' % appname)
    validator = join(BUILD_DIR, PATHS['validator'][OSNAME].format(appname=appname))
    module = APP_ARCHIVE[appname]['module']
    command = 'python {validator} -v {archive} {module}'.format(
        validator=validator, archive=archive_path(appname), module=module)
    logger.debug('Running command %s' % command)
    try:
        shell(command)
    except:
        logger.exception('Error running validator')
        raise


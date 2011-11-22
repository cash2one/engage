"""Tests for engage_file_layout
"""
from engage_file_layout import *
    
def validate_layout(installer_name=None):
    logger.info("Getting installer layout object with installer_name=%s" % installer_name)
    l = get_engine_layout_mgr(installer_name)
    gc = l.get_installer_config()
    app_name = gc.application_name
    assert app_name
    r = l.get_resource_def_file()
    logger.debug("resource def file = %s" % r)
    r = l.get_software_library_file()
    logger.debug("software library file = %s" % r)
    r = l.get_configurator_exe()
    logger.debug("configurator exe = %s" % r)
    r = l.get_password_file_directory()
    logger.debug("password file directory = %s" % r)
    r = l.get_password_database_file()
    logger.debug("password database file = %s" % r)
    r = l.get_password_salt_file()
    logger.debug("password salt file = %s" % r)
    r = l.get_install_spec_template_file(0)
    logger.debug("install spec template file = %s" % r)
    r = l.get_install_spec_file(0)
    logger.debug("install spec file = %s" % r)
    r = l.get_install_script_file()
    logger.debug("install script file = %s" % r)
    r = l.get_cache_directory()
    logger.debug("cache directory = %s" % r)
    r = l.get_log_directory()
    logger.debug("log directory = %s" % r)
    r = l.get_preprocessed_resource_file()
    logger.debug("Preprocessed resource file = %s" % r)
    r = l.get_preprocessed_library_file()
    logger.debug("Preprocessed library file = %s" % r)
    r = l.get_extension_resource_files()
    logger.debug("Extension resource files = %s" % r)
    r = l.get_extension_library_files()
    logger.debug("Extension library files = %s" % r)
    logger.info("installer_file_layout test for layout %s, app %s successful" % \
                (l.LAYOUT_TYPE, app_name))


# we use this for testing
KNOWN_INSTALLERS = ["django", "moinmoin", "tomcat", "jasper"]

#    
# We dynamically generate tests bases on what's presenting in the surrounding file system.
# These tests can be run by running this file from the command line or by running through
# the Nose test runner.
#
def test_generator(installer_names=KNOWN_INSTALLERS):
    logger.info("Generating test cases for %s" % __name__)
    for installer in KNOWN_INSTALLERS:
        yield validate_layout, installer


# if run as main, run the tests
if __name__ == '__main__':
    l = get_engine_layout_mgr()
    print "Layout is %s" % l.LAYOUT_TYPE
    for (fn, installer) in test_generator():
        fn(installer)

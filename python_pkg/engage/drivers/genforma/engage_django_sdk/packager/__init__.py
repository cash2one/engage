#!/usr/bin/env python
# Django application packager utility
# Copyright 2010 by genForma Corporation






import sys
import os
import os.path
import shutil
from optparse import OptionParser
import traceback
import string
from copy import deepcopy
import json
import subprocess
import tempfile
import logging
import urlparse

logger = logging.getLogger(__name__)

try:
    from engage_django_sdk.version import VERSION
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from engage_django_sdk.version import VERSION


# We store VERSION in the django_config.json file. COMPATIBLE_PACKAGER_VERSION is the earliest
# version of the packager which is supported by this version of the code. run_safe_validations()
# compares the version stored in the config file against the compatible version. If they config
# file version is older than the compatible version, an exception is thrown. This prevents someone
# from uploading an archive based on an obsolute version of the packager.  Bump up the compatible
# version number when the contents of the config file or the way settings are handled is changed.
#
# Note that we only compare the first two elements of the version number. The third element is
# not considered, so it is ok if the application's version is behind in path level, if the major
# and minor versions match.
COMPATIBLE_PACKAGER_VERSION = ".".join(VERSION.split('.')[0:2])


from errors import *
from archive_handlers import ZipfileHandler, TarfileHandler, create_handler, \
                             validate_archive_files
from django_config import django_config_from_validation_results, django_config_from_json
from generate_settings import generate_settings_file, simulated_install
from utils import app_module_name_to_dir, write_json, find_files, \
                  get_deployed_settings_module, import_module, \
                  get_settings_file_directory, get_python_path
from validation_results import *
import command
import parse_requirements
from find_module import find_python_module
from engage_django_components import COMPONENTS_FILENAME, read_components_file
from package_data import PREINSTALLED_PACKAGES, get_apps_for_packages, \
     PACKAGES_FOR_KNOWN_APPS, validate_package_list



SETTINGS_FILENAME = "settings.py"
DJANGO_CFG_FILENAME = "engage_django_cfg.json"


def run_safe_validations(handler):
    """This function runs all the validations that can safely be done without running
    user code. It returns the common parent directory of the archive.
    """
    logger.info(">> Running safe validations")
    # check archive format
    namelist = handler.get_namelist()
    common_dir = validate_archive_files(namelist)
    logger.debug("Common directory is %s" % common_dir)
    
    # check for and then read configuration file
    config_file = common_dir + os.sep + DJANGO_CFG_FILENAME
    if not handler.is_file_in_archive(config_file):
        raise FileMissingError("Archive missing configuration file %s" %
                               config_file)
    fileobj = handler.open_member(config_file)
    data = fileobj.read()
    django_config = django_config_from_json(data, COMPATIBLE_PACKAGER_VERSION)

    # check for additional_components file and parse if present
    components_file = common_dir + os.sep + COMPONENTS_FILENAME
    if handler.is_file_in_archive(components_file):
        fileobj = handler.open_member(components_file)
        read_components_file(fileobj, components_file, django_config.components)
    else:
        if len(django_config.components)>0:
            raise ValidationError("No additional component file at %s, but application with packaged with an additional component file" %
                                  filepath)

    # check for other required files
    settings_module_file = django_config.get_settings_module_file()
    if not handler.is_file_in_archive(settings_module_file):
        raise FileMissingError("Archive missing django settings file %s" % settings_module_file)
    logger.debug("Has required files")
    return (common_dir, django_config)


def run_safe_validations_on_archive(archive_file):
    """Wrapper on run_safe_validations that opens the archive,
    does the validations, and then closes it.
    """
    with create_handler(archive_file) as handler:
        return run_safe_validations(handler)

def check_if_setting_overridden(setting_name, module, results):
    if not hasattr(module, setting_name):
        raise ValidationError("Expected setting '%s' not defined. Is the setting file set up correctly?" % setting_name)
    setting_value = getattr(module, setting_name)
    engage_value = getattr(module.engage_settings, setting_name)
    if setting_value != engage_value:
        results.warning("Setting '%s' was overriden to value '%s'" %
                        (setting_name, setting_value))


def check_url_setting(setting_name, setting_value, results, default_value='',
                      path_should_end_in_slash=True):
    if setting_value == default_value:
        logger.debug("Setting '%s' has default value" % setting_name)
        return True
    try:
        sr = urlparse.urlsplit(setting_value)
        if path_should_end_in_slash and (sr[2][len(sr[2])-1] != '/'):
            results.warning("Setting '%s': The path component of the URL ('%s') is expected by Django to end in a slash ('/'). Engage will add a slash" %
                            (setting_name, sr[2]))
        logger.debug("Setting '%s' is a valid URL" % setting_name)
        return True
    except:
        results.error("Invalid URL format for setting '%s': '%s'" %
                      (setting_name, setting_value))
        return False


def check_directory_setting(setting_name, setting_value, default_value,
                            app_dir_path, results):
    if setting_value == default_value:
        logger.debug("Setting '%s' has default value" % setting_name)
    elif not os.path.isdir(setting_value):
        results.error("Setting '%s' points to directory '%s', which does not exist" %
                      (setting_name, setting_vaxolue))
    elif string.find(os.path.realpath(setting_value),
                     os.path.realpath(app_dir_path)) != 0:
        results.error("Setting '%s' points to directory '%s', which is not a subdirectory of '%s'" %
                      (setting_name, setting_value, app_dir_path))
    else:
        logger.debug("Setting '%s' passed directory checks." % setting_name)


def check_directory_tuple_setting(setting_name, setting_value,
                                  app_dir_path, results):
    """Validate a setting that is a tuple of directory names.
    """
    if isinstance(setting_value, str) or isinstance(setting_value, unicode):
        results.warning("Expecting a tuple for %s setting, got a string. If only one element, put a comma after the string." %
                        setting_name)
        check_directory_setting(setting_name, setting_value, None,
                                app_dir_path, results)
    else:
        # check each path in the list
        for dirname in setting_value:
            check_directory_setting(setting_name, dirname,
                                    None, app_dir_path, results)


def validate_installed_app(app_name, python_path_dir, known_apps,
                           app_dir_path, django_settings_module, results):
    try:
        import_module(app_name)
        logger.debug("Application '%s' Ok." % app_name)
    except:
        (exc_typ, exc_val, exc_tb) = sys.exc_info()
        if exc_typ==ImportError and str(exc_val)==("No module named %s" % app_name):
            logger.debug("Unable to find module named %s" % app_name)
            if app_name in PACKAGES_FOR_KNOWN_APPS:
                pkgs = PACKAGES_FOR_KNOWN_APPS[app_name]
                if len(pkgs)>1:
                    results.error("Django Application '%s' not found. Perhaps you wanted to include one of the following packages in your requirements.txt file: %s" %
                                    (app_name, pkgs))
                else:
                    results.error("Django Application '%s' not found. Perhaps you wanted to include the '%s' package in your requirements.txt file" %
                                  (app_name, pkgs[0]))
            else:
                pp_msg = "Your project was installed at %s. PYTHONPATH was set to %s." % (app_dir_path, get_python_path(python_path_dir, django_settings_module))
                results.error("Django Application '%s' not found. If it is from an external package, add the associated package to the requirements.txt file. If the application is supposed to be a python module included with you project tree, check the value you provided for the settings module. %s" %
                                  (app_name, pp_msg))
        else: # another exception occurred in import
            logger.exception("Exception when trying to import app %s" % app_name)
            results.warning("Django Application '%s' was found, but an error occurred when trying to import the application: %s(%s)" %
                          (app_name, exc_typ.__name__, str(exc_val)))

def validate_post_install_commands(app_name, settings_module, results):
    """Validate that each named command in ENGAGE_DJANGO_POSTINSTALL_COMMANDS
    is actually present as a command in manage.py.
    """
    from django.core.management import get_commands
    commands = get_commands().keys()
    for cmd in results.post_install_commands:
        if cmd not in commands:
            results.error("Unable to find post-install command %s in available commands" % cmd)
            return
    logger.debug("Post installation commands for application %s Ok." % app_name) 

def validate_fixture_file(fixture_name, installed_apps, fixture_dirs,
                          python_path_dir, settings_file_directory,
                          known_apps, results):
    """Use the same logic as django-admin.py loaddata to search for a
    fixture file.
    """
    if fixture_name.endswith((".json", ".xml")):
        filenames = [fixture_name]
    else:
        filenames = [fixture_name+".json", fixture_name+".xml"]
    # first try an absolute path
    if os.path.isabs(fixture_name):
        for filename in filenames:
            if os.path.exists(filename):
                logging.debug("Found fixture file %s" % filename)
                return
        results.error("Unable to find fixture %s" % fixture_name)
        return
    # next, look in the fixtures directory under all the installed apps
    for app_module in installed_apps:
        try:
            m = import_module(app_name)
            fixture_dir = os.path.join(os.path.dirname(m.__file__),
                                       "fixtures")
        except: # as a fallback, look under our python path
            fixture_dir = os.path.join(app_module_name_to_dir(python_path_dir,
                                                              app_module, False),
                                       "fixtures")
        if os.path.isdir(fixture_dir):
            for filename in filenames:
                fixture_path = os.path.join(fixture_dir, filename)
                if os.path.exists(fixture_path):
                    logger.debug("Found fixture %s at %s" % (fixture_name, fixture_path))
                    return
    # next, look under all the specified fixture directories
    for dirname in fixture_dirs:
        for filename in filenames:
            fixture_path = os.path.join(dirname, filename)
            if os.path.exists(fixture_path):
                logger.debug("Found fixture %s at %s" % (fixture_name, fixture_path))
                return
    # finally, look relative to settings_file_directory
    for filename in filenames:
        fixture_path = os.path.join(settings_file_directory, filename)
        if os.path.exists(fixture_path):
            logger.debug("Found fixture %s at %s" % (fixture_name, fixture_path))
            return
    # if we got here, we didn't find the fixture file anywhere
    results.error("Unable to find fixture %s" % fixture_name)


def validate_migration_apps(migration_apps, installed_apps, results):
    for app in migration_apps:
        found = False
        for installed_app in installed_apps:
            # look for an exact match or a suffix
            if (app == installed_app) or (installed_app[len(installed_app)-len(app)-1:] == ("." + app)):
                logger.debug("Found migration app %s" % app)
                found = True
                break
        if not found:
            results.error("Unable to find migration app %s in installed apps" % app)


def _tuple_setting_to_list(v):
    """We need to have a special case if the user specified a single element
    tuple as (v) instead of (v,).
    """
    if hasattr(v, "__iter__"):
        return list(v)
    else:
        return [v]

def get_user_required_packages(app_dir_path):
    """Look for a requirements.txt file. If found, parse the file and return
    a list of eggs.
    """
    requirements_file = os.path.join(app_dir_path, "requirements.txt")
    if os.path.exists(requirements_file):
        logger.debug("Found requirements.txt file")
        return parse_requirements.parse(requirements_file)
    else:
        logger.debug("Did not find requirements.txt file")
        return []
        

def _get_subdir_component(parent_dir, subdir):
    """Given two paths, where the second is a subdirectory of the
    first, return the part of the second path, which, when os.path.join()'ed to
    the first path, creates the second path. If the two paths are equal,
    return ''
    """
    parent_dir = os.path.abspath(os.path.expanduser(parent_dir))
    subdir = os.path.abspath(os.path.expanduser(subdir))
    assert subdir[:len(parent_dir)] == parent_dir, \
           "%s not a subdirectory of %s" % (subdir, parent_dir)
    if parent_dir==subdir:
        return ""
    else:
        return subdir[len(parent_dir)+1:]


def extract_static_files_settings(settings_module, app_dir_path, results):
    # Extract any settings related to static files that we need in the
    # install phase and perform the related sanity checks.
    def get_url_path(url):
        if len(url)==0:
            return None
        sr = urlparse.urlsplit(url)
        if sr[2][len(sr[2])-1] != '/':
            return sr[2] + '/'
        else:
            return sr[2]

    def path_setting_has_value(setting_name):
        return hasattr(settings_module, setting_name) and \
               getattr(settings_module, setting_name)!=None and \
               getattr(settings_module, setting_name)!=''

    def url_setting_has_value(setting_name):
        return hasattr(settings_module, setting_name) and \
               getattr(settings_module, setting_name)!=None and \
               getattr(settings_module, setting_name)!='' and \
               check_url_setting(setting_name, getattr(settings_module, setting_name),
                                 results)
        
    if path_setting_has_value('MEDIA_ROOT'):
        results.media_root_subdir = _get_subdir_component(app_dir_path,
                                                          settings_module.MEDIA_ROOT)
    if url_setting_has_value("MEDIA_URL"):
        results.media_url_path = get_url_path(settings_module.MEDIA_URL)
    else:
        results.media_url_path = None
    if url_setting_has_value("STATIC_URL"):
        results.static_url_path = get_url_path(settings_module.STATIC_URL)
    else:
        results.static_url_path = None
    if path_setting_has_value("STATIC_ROOT"):
        results.static_root_subdir = _get_subdir_component(app_dir_path,
                                                           settings_module.STATIC_ROOT)
    if hasattr(settings_module, "ADMIN_MEDIA_PREFIX"):
        check_url_setting("ADMIN_MEDIA_PREFIX",
                          settings_module.ADMIN_MEDIA_PREFIX,
                          results)

    # Check that STATIC_URL, STATIC_ROOT, and INSTALLED_APPS are consistent.
    # If STATIC_URL isn't set, we won't enable any staticfiles-related functionality.
    # Thus, we give an error if it is none and either the app is present or STATIC_ROOT
    # is set.
    # If STATIC_URL is set, but STATIC_ROOT isn't, we will set it to
    # <project_root>/static.
    if ("django.contrib.staticfiles" in results.installed_apps) and \
       results.static_url_path==None:
        results.warning("django.contrib.staticfiles was included in INSTALLED_APPS,"+
                        " but STATIC_URL was not set. Static file mappings will not be enabled.")
    if results.static_root_subdir and results.static_root_subdir!='' and \
       results.static_url_path==None:
        results.warning("STATIC_ROOT setting was specified as %s, but STATIC_URL was not set. Static file mappings will not be enabled." % settings_module.STATIC_ROOT)

    if results.static_url_path!=None and \
       (results.static_root_subdir==None or results.static_root_subdir==''):
        if "django.contrib.staticfiles" in results.installed_apps:
            logger.debug("Using default value for STATIC_ROOT: <project_home>/static")
            results.static_root_subdir = "static"
        else:
            results.warning("STATIC_URL setting was specified, but STATIC_ROOT was not set and django.contrib.staticfiles not in INSTALLED_APPS. Static mappings will not be enabled.")
            results.static_url_path = None
            results.static_root_subdir = None
        

def validate_settings(app_dir_path, django_settings_module, django_config=None,
                      prev_version_component_list=None):
    """This is the main settings validation function. It takes the following arguments:
        app_dir_path           - path to the top level directory of the extracted application
        django_settings_module - fully qualified name of the django settings module
        django_config          - if provided, this is the django_config data generated
                                 during the original packaging of the app. We validate
                                 that it is still consistent with the current app.

    This function returns an intance of SettingValidationResults.

    Note that validate_settings() must be run after generate_settings(). We import
    the deployed_settings module rather than the user's django_settings_module so
    we can see whether they've overridden any of the settings.
    """
    # normalize the target install path
    app_dir_path = os.path.abspath(os.path.expanduser(app_dir_path))
    
    results = SettingValidationResults(VERSION, logger)
    python_path_dir = find_python_module(django_settings_module, app_dir_path)
    if not python_path_dir:
        raise ValidationError("Unable to find django settings module %s under %s" % (django_settings_module, app_dir_path))
    # we store only the subdirectory part of the python path, since the rest depends
    # on where we install the app.
    if os.path.dirname(app_dir_path)==python_path_dir:
        results.python_path_subdirectory = ""
    else:
        results.python_path_subdirectory = _get_subdir_component(os.path.dirname(app_dir_path), python_path_dir)
    # get the settings file directory
    settings_file_directory = get_settings_file_directory(python_path_dir, django_settings_module)

    # do the import of app's settings
    sys.path = [python_path_dir] + sys.path

    deployed_settings_module = get_deployed_settings_module(django_settings_module)
    logger.debug("Importing settings module %s" % deployed_settings_module)
    try:
        settings_module = import_module(deployed_settings_module)
    except:
        (exc_type, exc_value, exc_traceback) = sys.exc_info()
        logger.exception("Exception in settings file import: %s(%s)" %
                         (exc_type.__name__, str(exc_value)))
        raise SettingsImportError("Error in settings import: %s(%s)" %
                                  (exc_type.__name__, str(exc_value)))
        
    # Check that the settings controlled by engage weren't overridden by app.
    # If any are overridden, we treat them as warnings.
    check_if_setting_overridden('TIME_ZONE', settings_module, results)
    check_if_setting_overridden('SECRET_KEY', settings_module, results)
    check_if_setting_overridden('ADMINS', settings_module, results)
    check_if_setting_overridden('DATABASES', settings_module, results)
    check_if_setting_overridden('LOGGING_CONFIG', settings_module,
                                results)

    # Check that settings which point to a directory are either not set or
    # point to a valid directory
    if hasattr(settings_module, "MEDIA_ROOT"):
        check_directory_setting("MEDIA_ROOT",
                                settings_module.MEDIA_ROOT,
                                '', app_dir_path, results)
    if hasattr(settings_module, "TEMPLATE_DIRS"):
        check_directory_tuple_setting("TEMPLATE_DIRS",
                                      settings_module.TEMPLATE_DIRS,
                                      app_dir_path, results)
    
    # Get the packages in requirements.txt. We use this in validating
    # the django apps. We defer the validation of the actual packages
    # until we have parsed and validated the engage_components.json file.
    user_required_packages = get_user_required_packages(app_dir_path)
    
    # check that all INSTALLED_APPS are pointing to apps accessible in the target system
    if hasattr(settings_module, "INSTALLED_APPS"):
        installed_apps = []
        packages = PREINSTALLED_PACKAGES + user_required_packages
        known_apps = set(get_apps_for_packages(packages))
        for app_name in settings_module.INSTALLED_APPS:
            validate_installed_app(app_name, python_path_dir, known_apps,
                                   app_dir_path, django_settings_module, results)
            installed_apps.append(app_name)
    else:
        installed_apps = []
    results.installed_apps = installed_apps

    if hasattr(settings_module, "FIXTURE_DIRS"):
        fixture_dirs = _tuple_setting_to_list(settings_module.FIXTURE_DIRS)
        check_directory_tuple_setting("FIXTURE_DIRS", fixture_dirs,
                                      app_dir_path, results)
    else:
        fixture_dirs = []
    # check that ENGAGE_APP_DB_FIXTURES points to valid fixture files
    if hasattr(settings_module, "ENGAGE_APP_DB_FIXTURES"):
        results.fixtures = _tuple_setting_to_list(settings_module.ENGAGE_APP_DB_FIXTURES)
        for fixture in results.fixtures:
            validate_fixture_file(fixture, results.installed_apps, fixture_dirs,
                                  python_path_dir, settings_file_directory, known_apps, results)
    else:
        results.fixtures = []

    # check ENGAGE_MIGRATION_APPS, if present
    if hasattr(settings_module, "ENGAGE_MIGRATION_APPS"):
        results.migration_apps = _tuple_setting_to_list(settings_module.ENGAGE_MIGRATION_APPS)
        if len(results.migration_apps)>0 and not ("south" in results.installed_apps):
            results.error("Django apps to upgraded specified in ENGAGE_MIGRATION_APPS, but south not included in INSTALLED_APPS")
        validate_migration_apps(results.migration_apps, results.installed_apps, results)
    else:
        results.migration_apps = []

    # check the static files directories, if present. Each entry could be a source
    # directory, or a tuple of (target_subdir, source_path)
    if hasattr(settings_module, "STATICFILES_DIRS"):
        staticfiles_dirs = _tuple_setting_to_list(settings_module.STATICFILES_DIRS)
        for dirpath in staticfiles_dirs:
            if isinstance(dirpath, tuple):
                dirpath = dirpath[1]
            if not os.path.isdir(dirpath):
                results.error("Setting STATICFILES_DIRS references '%s', which does not exist" % dirpath)
            elif string.find(os.path.realpath(dirpath),
                             os.path.realpath(app_dir_path)) != 0:
                results.error("Setting STATICFILES_DIRS references '%s', which is not a subdirectory of '%s'" % (dirpath, app_dir_path))
                 
        check_directory_tuple_setting("STATICFILES_DIRS", staticfiles_dirs,
                                      app_dir_path, results)
    # gather the values of static files related settings for use during
    # installation.
    extract_static_files_settings(settings_module, app_dir_path, results)
        
    # check each command in ENGAGE_DJANGO_POSTINSTALL_COMMANDS is actually present in manager
    if hasattr(settings_module, "ENGAGE_DJANGO_POSTINSTALL_COMMANDS"):
        results.post_install_commands = list(settings_module.ENGAGE_DJANGO_POSTINSTALL_COMMANDS)
        validate_post_install_commands(app_name, settings_module, results)
    else:
        results.post_install_commands = []

    # read the additional components file and put the data into the results
    additional_comp_file = os.path.join(app_dir_path, COMPONENTS_FILENAME)
    if os.path.exists(additional_comp_file):
        with open(additional_comp_file, "rb") as cf:
            results.components = read_components_file(cf, additional_comp_file, None)
    else:
        results.components = []

    # validate the user required packages, taking into account the components requested
    # by the user.
    validate_package_list(user_required_packages, results.components, results)
    
    # extract the product name and version, if present
    if hasattr(settings_module, "ENGAGE_PRODUCT_NAME"):
        results.product = settings_module.ENGAGE_PRODUCT_NAME
    if hasattr(settings_module, "ENGAGE_PRODUCT_VERSION"):
        results.product_version = settings_module.ENGAGE_PRODUCT_VERSION

    # if provided, check that the django_config matches the settings values
    if django_config:
        django_config_ok = True
        if installed_apps != django_config.installed_apps:
            results.error("INSTALLED_APPS in configuration file (%s) does not match INSTALLED_APPS in settings file (%s). Your configuration file is likely out of date. Try re-running prepare." %
                          (django_config.installed_apps.__repr__(),
                           installed_apps.__repr__()))
            django_config_ok = False
        if results.fixtures != django_config.fixtures:
            # TODO: this was originally an error, which caused some issues.
            # See ticket #166.
            results.warning("ENGAGE_APP_DB_FIXTURES in configuration file (%s) does not match value in settings file (%s). If this is not what you expect, your configuration file is likely out of date: try re-running prepare." %
                          (django_config.fixtures.__repr__(),
                           results.fixtures.__repr__()))
            django_config_ok = False
        if results.migration_apps != django_config.migration_apps:
            results.error("ENGAGE_MIGRATION_APPS in configuration file (%s) does not match value in settings file (%s). Your configuration file is likely out of date. Try re-running prepare." %
                          (django_config.migration_apps.__repr__(),
                           results.migration_apps.__repr__()))
            django_config_ok = False
        if results.product and results.product != django_config.product:
            results.error("ENGAGE_PRODUCT_NAME in configuration file (%s) does not match value in settings file (%s). Your configuration file is likely out of date. Try re-running prepare." % (django_config.product, results.product))
            django_config_ok = False
        if results.product_version and results.product_version != django_config.product_version:
            results.error("ENGAGE_PRODUCT_VERSION in configuration file (%s) does not match value in settings file (%s). Your configuration file is likely out of date. Try re-running prepare." % (django_config.product_version, results.product_version))
            django_config_ok = False
        if django_config_ok:
            logger.debug("Verified config file is consistent with settings file")

    return results # all done

        
def run_installed_tests_as_subprocess(app_dir_path, django_settings_module,
                                      python_exe_path=sys.executable,
                                      use_logger=None, read_config_file=True):
    """Run the installed mode tests as a separate subprocess, using the installed app's environment.
    A results file is used to communcate back the results of the validation. After the run is complete,
    an instance of ParsedJsonResults is returned
    """
    logger.info(">> Validating application settings")
    app_dir_path = os.path.abspath(os.path.expanduser(app_dir_path))
    if not os.path.exists(app_dir_path):
        raise TestSetupError("Django settings file validator: application directory '%s' does not exist" % app_dir_path)
    python_path_dir = find_python_module(django_settings_module, app_dir_path)
    if python_path_dir==None:
        raise TestSetupError("Django settings file validator: unable to find settings module %s under %s" %
                             (django_settings_module, app_dir_path))
    if use_logger == None:
        use_logger = logger
    python_path = get_python_path(python_path_dir, django_settings_module)
    use_logger.debug("Setting PYTHONPATH to %s" % python_path)
    # we create a temporary file that will contain the results
    tf = tempfile.NamedTemporaryFile(delete=False)
    tf.write("null")
    tf.close()
    script_file = os.path.dirname(os.path.abspath(__file__))
    try:
        program_and_args = [python_exe_path, script_file, "-v",
                            "validate-installed", app_dir_path, tf.name]
        if not read_config_file:
            program_and_args.append(django_settings_module)
        use_logger.debug(' '.join(program_and_args))
        env = {
            "PYTHONPATH": python_path,
            "DJANGO_SETTINGS_MODULE": "%s" % \
               get_deployed_settings_module(django_settings_module)
        }
        cwd = get_settings_file_directory(python_path_dir, django_settings_module)
        subproc = subprocess.Popen(program_and_args,
                                   env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, cwd=cwd)
        use_logger.debug("Started program %s, pid is %d" % (program_and_args[0],
                                                            subproc.pid))
        subproc.stdin.close()
        for line in subproc.stdout:
            use_logger.debug("[%d] %s" % (subproc.pid, line.rstrip()))
        subproc.wait()
        use_logger.debug("[%d] %s exited with return code %d" % (subproc.pid,
                                                                 program_and_args[0],
                                                                 subproc.returncode))
        with  open(tf.name, "rb") as f:
            json_obj = json.load(f)
        results = ParsedJsonResults(json_obj)
        return results
    finally:
        os.remove(tf.name)


##### Section: Commands #####

class CommandManager(command.CommandManager):
    def __init__(self):
        super(CommandManager, self).__init__()
        self.verbose = None

    def add_options(self, parser):
        parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                          default=False)
        parser.add_option("--test-install-dir", dest="test_install_dir",
                          default=None,
                          help="Use the specified directory as a target for test installation, rather than a temporary directory")
        parser.add_option("--package-cache-dir", dest="package_cache_dir",
                          default=None,
                          help="Directory to check for local copies of packages")

    def process_generic_options(self, options, args):
        self.verbose = options.verbose

command_manager = CommandManager()

class Command(command.Command):
    """Base class for packager commands. Subclases should define NAME and USAGE class properties as well."""
    def __init__(self, parser, args, options, num_additional_args=None):
        super(Command, self).__init__(parser, args, options,
                                      num_additional_args)

    def get_results_file(self):
        """Return the name of the results file or None if there isn't one"""
        return None


class PrepareCommandBase(Command):
    """Base class for the prepare commands. Provides the main functionality
    for validating and preparing an archive. It expects the self.app_module_name
    member to be defined by the subclasses. This base class defines the following
    members:
     * self.archive_file
     * self.archive_type (either zip or tgz)
     * _validate_and_prepare_dir()
    """
    def __init__(self, parser, args, options, argcnt, archive_file):
        super(PrepareCommandBase, self).__init__(parser, args, options,
                                                 argcnt)
        self.archive_file = archive_file
        if self.archive_file[-4:] == ".zip":
            self.archive_type = "zip"
        elif self.archive_file[-4:]==".tgz" or self.archive_file[-7:]==".tar.gz":
            self.archive_type = "tgz"
        else:
            parser.error("Archive filename '%s' must end in either .zip (zip archive), .tgz, or .tar.gz (gzipped tar archive)" % self.archive_file)

    def _validate_and_prepare_dir(self, app_dir_path, undo_ops, python_exe):
        results = run_installed_tests_as_subprocess(app_dir_path,
                                                    self.django_settings_module,
                                                    python_exe_path=python_exe,
                                                    read_config_file=False)
        if len(results.error_messages)>0:
            for error in results.error_messages:
                logger.error("ERROR>> %s" % error)
        if len(results.warning_messages)>0:
            for warning in results.warning_messages:
                logger.warning("WARNING>> %s" % warning)
        results.print_final_status_message(logger)
        if results.get_return_code() != SUCCESS_RC:
            return results.get_return_code()
        config = django_config_from_validation_results(self.django_settings_module,
                                                       VERSION,
                                                       results)
        write_json(config.to_json(), os.path.join(app_dir_path, DJANGO_CFG_FILENAME))

        # undo the changes we made
        for (op_fun, args) in undo_ops:
            op_fun(*args)
        # delete all the .pyc files
        find_files(app_dir_path, "\.pyc$", os.remove)
        # (re)create the archive
        if self.archive_type == "zip":
            archive = ZipfileHandler(self.archive_file, "w")
        else:
            archive = TarfileHandler(self.archive_file, "w:gz")
        archive.create_new_from_dir(app_dir_path)
        archive.close()
        return SUCCESS_RC
        
    def _validate_and_prepare_dir_old(self, app_dir_path, undo_ops):
        """Called by the subclass run() method after setting up the directory.
        """
        results = validate_settings(app_dir_path, self.django_settings_module)
        if results.get_return_code() != SUCCESS_RC:
            results.print_final_status_message(logger)
            return results.get_return_code()
        config = django_config_from_validation_results(self.django_settings_module,
                                                       VERSION, results)
        write_json(config.to_json(), os.path.join(app_dir_path, DJANGO_CFG_FILENAME))

        # undo the changes we made
        for (op_fun, args) in undo_ops:
            op_fun(*args)
        # delete all the .pyc files
        find_files(app_dir_path, "\.pyc$", os.remove)
        # (re)create the archive
        if self.archive_type == "zip":
            archive = ZipfileHandler(self.archive_file, "w")
        else:
            archive = TarfileHandler(self.archive_file, "w:gz")
        archive.create_new_from_dir(app_dir_path)
        archive.close()
        return SUCCESS_RC
        
_prepare_dir_long_desc = \
"""This command performs validations on a django project, generates the
necessary engage configuration file, removes unneeded files (e.g. .pyc files),
and creates a archive file suitable for deployment to Engage.

The arguments are:
 django_project_directory - directory containing the django app and its
                            dependencies.
 django_settings_module   - name of Python module containing the settings
                            for this app.
 output_archive_file      - name of output archive to be generated. Should end
                            in either .tgz (gzipped tar achive),
                            .tar.gz (gzipped tar archive), or .zip
                            (zip archive).
"""

class PrepareDirCommand(PrepareCommandBase):
    NAME = "prepare-dir"
    USAGE = "%prog [options] prepare-dir django_project_directory django_settings_module output_archive_file"
    SHORT_DESC = "Prepare the specified Django project directory for deployment"
    LONG_DESC = _prepare_dir_long_desc
    def __init__(self, parser, args, options):
        if len(args) != 3:
            parser.error("Expecting three arguments to prepare-dir: django_project_directory, django_settings_module, output_archive_file")
        super(PrepareDirCommand, self).__init__(parser, args, options, 3,
                                                args[2])
        self.django_project_directory = os.path.abspath(args[0])
        if not os.path.isdir(self.django_project_directory):
            parser.error("Django project directory %s does not exist or is not a directory." %
                         self.django_project_directory)
        self.django_settings_module = args[1]

    def run(self):
        if self.options.test_install_dir:
            install_dir = os.path.abspath(os.path.expanduser(self.options.test_install_dir))
            os.makedirs(install_dir)
        else:
            install_dir = tempfile.mkdtemp(suffix='-engage')
        try:
            (app_dir_path, undo_ops, python_exe) = \
                simulated_install(self.django_project_directory,
                                  install_dir, self.django_settings_module,
                                  package_cache_dir=self.options.package_cache_dir)
            return self._validate_and_prepare_dir(app_dir_path, undo_ops,
                                                  python_exe)
        finally:
            if not self.options.test_install_dir:
                shutil.rmtree(install_dir)

command_manager.register_command(PrepareDirCommand)


_prepare_archive_long_desc = \
"""This command performs validations on a django project archive file,
generates the necessary engage configuration file, and removes unneeded files
(e.g. .pyc files). Note that changes are performed in-place on the original
archive file.

The arguments are:
 django_archive_file    - archive file containing the django app and its
                          dependencies. Should be either a gzipped tar archive
                          (ending in .tgz or .tar.gz) or a zip archive (ending in
                          .zip).
 django_settings_module - name of Python module containing the settings for this app
"""

class PrepareArchiveCommand(PrepareCommandBase):
    NAME = "prepare-archive"
    USAGE = "%prog [options] prepare-archive django_archive_file app_module_name"
    SHORT_DESC = "Prepare the specified Django project archive for deployment"
    LONG_DESC = _prepare_archive_long_desc
    def __init__(self, parser, args, options):
        if len(args) != 2:
            parser.error("Expecting two arguments to prepare-archive: django_archive file, django_settings_module")
        super(PrepareArchiveCommand, self).__init__(parser, args, options, 2,
                                                    args[0])
        self.django_settings_module = args[1]
        if not os.path.exists(self.archive_file):
            parser.error("Django archive file %s does not exist" %
                         self.archive_file)

    def run(self):
        if self.options.test_install_dir:
            install_dir = os.path.abspath(os.path.expanduser(self.options.test_install_dir))
            os.makedirs(install_dir)
        else:
            install_dir = tempfile.mkdtemp(suffix='-engage')
        try:
            (app_dir_path, undo_ops, python_exe) = \
                simulated_install(self.archive_file, install_dir,
                                  self.django_settings_module,
                                  package_cache_dir=self.options.package_cache_dir)
            return self._validate_and_prepare_dir(app_dir_path, undo_ops,
                                                  python_exe)
        finally:
            if not self.options.test_install_dir:
                shutil.rmtree(install_dir)

command_manager.register_command(PrepareArchiveCommand)

_vs_long_desc = \
"""This command validates a django archive created using prepare-dir or
prepare-archive. It only performs validations which do not involve executing
the Python code in the archive. This include checks that the archive is
readable, verifying that all required files are present, and parsing the
engage config file.
"""

class ValidateSafeCommand(Command):
    NAME = "validate-safe"
    USAGE = "%prog [options] validate-safe django_archive_file"
    SHORT_DESC = "Perform safe validations on the specified django application"
    LONG_DESC = _vs_long_desc
    def __init__(self, parser, args, options):
        super(ValidateSafeCommand, self).__init__(parser, args, options, 1)
        self.django_archive_file = args[0]
        if not os.path.exists(self.django_archive_file):
            parser.error("Django archive file %s does not exist" % self.django_archive_file)
            
    def run(self):
        (common_dir, django_config) = \
            run_safe_validations_on_archive(self.django_archive_file)
        logger.info(">> All safe mode checks passed.")
        return SUCCESS_RC

command_manager.register_command(ValidateSafeCommand)    


_vf_long_desc = \
"""This command validates a django archive created using prepare-dir or
prepare-archive. It performs all validations, including those which execute
the Python code in the archive. This include all the checks performed by
the validate-safe command, as well as loading the settings and verifying
individual settings values.
"""

class ValidateFullCommand(Command):
    NAME = "validate-full"
    USAGE = "%prog [options] validate-full django_archive_file"
    SHORT_DESC = "Perform all validations on the specified django application"
    LONG_DESC = _vf_long_desc
    def __init__(self, parser, args, options):
        super(ValidateFullCommand, self).__init__(parser, args, options, 1)
        self.archive_file = args[0]
        if not os.path.exists(self.archive_file):
            parser.error("Django archive file %s does not exist" % self.archive_file)
            
    def run(self):
        with create_handler(self.archive_file) as handler:
            (common_dir, django_config) = run_safe_validations(handler)
        if self.options.test_install_dir:
            install_dir = os.path.abspath(os.path.expanduser(self.options.test_install_dir))
            os.makedirs(install_dir)            
        else:
            install_dir = tempfile.mkdtemp(suffix="-engage")
        try:
            (app_dir_path, undo_ops, python_exe) = \
                simulated_install(self.archive_file, install_dir,
                                  django_config.django_settings_module,
                                  package_cache_dir=self.options.package_cache_dir)
            results = run_installed_tests_as_subprocess(app_dir_path,
                                                        django_config.django_settings_module,
                                                        python_exe_path=python_exe,
                                                        read_config_file=True)
            results.print_final_status_message(logger)
            return results.get_return_code()
        finally:
            if self.options.test_install_dir:
                shutil.rmtree(install_dir)

command_manager.register_command(ValidateFullCommand)


_vi_long_desc = \
"""This command validates an installed django application (e.g. deployed
by Engage). It is run near the end of the deployment process before the
application is started. It performs all validations, including those which
execute the Python code in the archive. This include all the checks performed by
the validate-safe command, as well as loading the settings and verifying
individual settings values.
"""

class ValidateInstalledCommand(Command):
    NAME = "validate-installed"
    USAGE = "%prog validate-installed [options] app_dir_path results_file"
    SHORT_DESC = "Perform all validations on an installed django application"
    LONG_DESC = _vi_long_desc
    def __init__(self, parser, args, options):
        super(ValidateInstalledCommand, self).__init__(parser, args, options, None)
        num_args = len(args)
        # We have a 'hidden' third argument which is the django settings module.
        # If specified, we will not try to read the django config file and
        # use that instead. This is only for being called as a subprocess.
        if num_args!=2 and num_args!=3:
            parser.error("Expecting 2 arguments for %s command." %
                         ValidateInstalledCommand.NAME)
        self.app_dir_path = args[0]
        self.results_file = args[1]
        if num_args==3:
            self.django_settings_module = args[2]
        else:
            self.django_settings_module = None
        if not os.path.isdir(self.app_dir_path):
            parser.error("Django application directory %s does not exist or is not a directory" % self.app_dir_path)
        
    def get_results_file(self):
        return self.results_file

    def run(self):
        if self.django_settings_module:
            ds_mod = self.django_settings_module
            django_config = None
        else:
            config_file = os.path.join(self.app_dir_path, DJANGO_CFG_FILENAME)
            if not os.path.exists(config_file):
                raise FileMissingError("Missing configuration file %s" % config_file)
            with open(config_file, "rb") as fileobj:
                django_config = django_config_from_json(fileobj.read(), COMPATIBLE_PACKAGER_VERSION)
            ds_mod = django_config.django_settings_module
        results = validate_settings(self.app_dir_path, ds_mod,
                                    django_config)
        write_json(results.to_json(), self.results_file)
        results.print_final_status_message(logger)
        return results.get_return_code()    


command_manager.register_command(ValidateInstalledCommand)


##### End Section: Commands #####

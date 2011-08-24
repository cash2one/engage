"""Service manager base class for Django-based apps. In most cases,
apps should be able to use this class directly, and only set a few
properties in the install spec. For more advanced cases, they can subclass
from this class or from the service manager class directly.

This driver is more complex than most, as it needs to work with an
application provided dynamically by the user. The file layout of the
installed app will be:
 <home_path>
   set in the resource definition, e.g. <deployment_home>/django_app
 <home_path>/<app_dir>
   we extract the user's application package under the home
   path. The name of the directory is not known until runtime)
 <home_path>/<app_dir>/requirements.txt
   The requirements.txt file should go under the application directory,
   if present.
 <home_path>/django.sh
   Management script for starting/stopping django if using the django
   development webserver. The path to this is at self.config.app_admin_script
 <home_path>/...<settings_file_directory>
   This is the directory containing the settings files - the user
   specified file and the two generated files (engage_settings.py
   and deployed_settings.py). This directory may be app_dir or some
   sub-directory, depending on how many sub-packages are included
   in django_settings_module and on how far under <app_dir> these
   packages begin. For example, if django_settings_module
   is foo.bar.settings, and the foo package is at <app_dir>/foo,
   then the settings file directory is going to be at
   <home_path>/<app_dir>/foo/bar. If the foo package is at <app_dir>,
   then the settings file directory is <home_path>/foo
 <python_path_dir>
   This is the directory to be added to the python path so that the
   django settings module can be imported. It needs to be the directory
   containing the first component of the module. For example, if the
   django settings module is foo.bar.settings, and foo is directly under
   <app_dir>, then <python_path_dir> should be <home_dir>/<app_dir>.

The class DjangoFileLayout in django_file_layout.py helps to manage the dynamic
aspects of the file layout.
 
"""

import os
import os.path
import string
import time
import re
import sys
from random import choice
import json

import fixup_python_path
from django_file_layout import create_file_layout
import engage.drivers.service_manager as service_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.utils.path as iupath
import engage.utils.log_setup
import engage.utils.file as iufile
import engage.utils.process as iuprocess
import engage.utils.http as iuhttp
import apache_utils
import engage_django_sdk.packager
import engage_django_sdk.packager.errors
import engage_django_sdk.packager.archive_handlers
import engage_django_sdk.packager.generate_settings as gs
from engage.drivers.backup_file_resource_mixin import BackupFileMixin
from engage.drivers.password_repo_mixin import PasswordRepoMixin
from engage.drivers.action import Context


from engage.utils.user_error import ScriptErrInf, UserError, convert_exc_to_user_error
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

ERR_NO_SETTINGS_FILE = 1
ERR_NO_DJANGO_SCRIPT = 2
ERR_MISSING_INST_PROP = 3
ERR_DJANGO_STARTUP = 4
ERR_DJANGO_SHUTDOWN = 5
ERR_DJANGO_STATUS = 6
ERR_DJANGO_NO_RESP = 7
ERR_DJANGO_PYTHON_SCRIPT_FAILED = 9
ERR_DJANGO_MANAGE_PY_SETUP = 10
ERR_USER_ARCHIVE_NOT_FOUND = 11
ERR_USER_ARCHIVE_WRONG_FORMAT = 12
ERR_USER_ARCHIVE_STRUCTURE = 13
ERR_USER_ARCHIVE_MISSING_FILE = 14
ERR_DJANGO_RESOURCE_DEF_ERROR = 15
ERR_DJANGO_VALIDATE_FAILED = 16
ERR_REQUIREMENTS_INSTALL_FAILED = 17
ERR_WSGI_SCRIPT = 18

define_error(ERR_NO_SETTINGS_FILE,
             _("Settings file '%(file)s' does not exist."))
define_error(ERR_NO_DJANGO_SCRIPT,
             _("Django administration script file '%(file)s' for %(appname)s does not exist."))
define_error(ERR_MISSING_INST_PROP,
             _("Required django installer configuration property '%(prop)s' does not exist."))
define_error(ERR_DJANGO_STARTUP,
             _("Error in starting django server process for %(appname)s"))
define_error(ERR_DJANGO_SHUTDOWN,
             _("Error in stopping django server process for %(appname)s"))
define_error(ERR_DJANGO_STATUS,
             _("Error in checking status of django server process for %(appname)s"))
define_error(ERR_DJANGO_NO_RESP,
             _("No response from django server process for %(appname)s"))
define_error(ERR_DJANGO_PYTHON_SCRIPT_FAILED,
             _("Django setup script '%(script)s' for %(appname)s failed"))
define_error(ERR_DJANGO_MANAGE_PY_SETUP,
             _("Substitutions in manage.py script at '%(file)s' failed"))
define_error(ERR_USER_ARCHIVE_NOT_FOUND,
             _("Django application archive file '%(file)s' not found"))
define_error(ERR_USER_ARCHIVE_WRONG_FORMAT,
             _("Django application archive file '%(file)s' is neither a zip or tar archive"))
define_error(ERR_USER_ARCHIVE_STRUCTURE,
             _("Django application archive file '%(file)s' has invalid structure: %(msg)s"))
define_error(ERR_USER_ARCHIVE_MISSING_FILE,
             _("Django application archive file '%(file)s' invalid: %(msg)s"))
define_error(ERR_DJANGO_RESOURCE_DEF_ERROR,
             _("Django-App resource definition not configured correctly"))
define_error(ERR_DJANGO_VALIDATE_FAILED,
             _("Django application validation failed, reason was '%(rc)s'."))
define_error(ERR_REQUIREMENTS_INSTALL_FAILED,
             _("Installation of application requirements via pip failed."))
define_error(ERR_WSGI_SCRIPT,
             _("Execution of script to setup WSGI with apache failed. Script was '%(script)s'."))

#####################################################################

# timeouts for checking server liveness after startup
TIMEOUT_TRIES = 10
TIME_BETWEEN_TRIES = 2.0

#####################################################################
# Define configuration properties used to specify/override the
# behavior of the service manager class.

# short name for application
PROP_APP_SHORT_NAME = u"app_short_name"

# test url to use to validate application response
PROP_APP_TEST_URL = u"test_url"
# default value
PROP_APP_TEST_URL_DEFAULT = "/"

#####################################################################

# define the configuration data used by the resource instance
_config_type = {
  "config_port": {
    "home": unicode,
    "websvr_hostname": unicode,
    "admin_name": unicode,
    "admin_email": unicode,
    "email_host": unicode,
    "email_host_user": unicode,
    "email_from": unicode,
    "email_password": unicode,
    "email_port": int,
    "time_zone": unicode,
    "log_directory": unicode
  },
  "input_ports": {
    "host": {
      "genforma_home": unicode,
      "hostname": unicode,
      "sudo_password": unicode
    },
    "python": {
      "PYTHONPATH": unicode,
      "home": unicode
    },
    "django_db": {
      "ENGINE": unicode,
      "NAME": unicode,
      "USER": unicode,
      # PASSWORD is optional - can be none
      #"PASSWORD": unicode,
      "HOST": unicode
      # Port is optional - can be None
      #"PORT": int
    },
    "webserver_config": {
      "port": int,
      "webserver_type": unicode,
      "controller_exe": unicode
    }
  },
  "output_ports": {
    "django": {
      "layout_cfg_file": unicode
    }
  }
}

logger = engage.utils.log_setup.setup_script_logger(__name__)


def gen_password(length, chars=string.letters+string.digits):
    return ''.join([ choice(chars) for i in range(length) ])


class Config(resource_metadata.Config):
    def __init__(self, props_in, types, id, package_name, app_short_name):
        resource_metadata.Config.__init__(self, props_in, types)
        self._add_computed_prop("id", id)
        self._add_computed_prop("package_name", package_name)
        self._add_computed_prop("home_path",
                                os.path.abspath(self.config_port.home))
        self._add_computed_prop("home_dir_parent",
                                os.path.dirname(self.home_path))
        self._add_computed_prop("home_dir",
                                os.path.basename(self.home_path))
        self._add_computed_prop("python_bin_dir",
                                os.path.dirname(self.input_ports.python.home))
        self._add_computed_prop("django_admin_script",
                                os.path.join(self.python_bin_dir,
                                             "django-admin.py"))
        self._add_computed_prop("app_short_name", app_short_name)
        self._add_computed_prop("app_admin_script",
                                os.path.join(self.home_path, "django.sh"))
        # application_archive is an optional configuration property. If present,
        # we use that instead of the package manager to find the package file.
        if hasattr(self.config_port, "application_archive"):
            self._add_computed_prop("user_specified_package", True)
            # expand the full path
            self._add_computed_prop("application_archive", os.path.abspath(os.path.expanduser(self.config_port.application_archive)))
        else:
            self._add_computed_prop("user_specified_package", False)
        # websvr_listen_host is an optional configuration property. This is the
        # property used to tell the django webserver which IP/hostname to listen on.
        # If not in the resource instance, we use the websvr_hostname value as a default.
        if hasattr(self.config_port, "websvr_listen_host"):
            self._add_computed_prop("websvr_listen_host", self.config_port.websvr_listen_host)
        else:
            self._add_computed_prop("websvr_listen_host", self.config_port.websvr_hostname)
        # the package cache for engage (use as pip's download cache)
        self._add_computed_prop("package_cache_dir",
                                 os.path.join(self.input_ports.host.genforma_home,
                                              "engage/sw_packages"))



def make_context(resource_json, sudo_password_fn, dry_run=False):
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=sudo_password_fn,
                  dry_run=dry_run)
    return ctx


class Manager(BackupFileMixin, PasswordRepoMixin, service_manager.Manager):
    def _get_app_prop(self, name, default):
        """This helper method gets an application-specific property from the
        properties section of the configuration metadata. This comes from
        the install spec. We use this to permit customizing the behavior of
        a django app installer without having to write python classes.
        """
        if self.metadata.properties.has_key(name):
            return self.metadata.properties[name]
        else:
            return default

    def _get_required_app_prop(self, name):
        """This helper method gets a required application-specific property from the
        properties section of the configuration metadata. This comes from
        the install spec. We use this to permit customizing the behavior of
        a django app installer without having to write python classes.
        """
        if self.metadata.properties.has_key(name):
            return self.metadata.properties[name]
        else:
            raise UserError(errors[ERR_MISSING_INST_PROP],
                            msg_args={"prop":name},
                            developer_msg="%s instance %s" %
                            (self.config.package_name, self.config.id))

    def _check_server_response(self):
        """Check if the server is responding. If so, return. If no response after timeout,
        throw an error.
        """
        logger.info("Checking for response from Django server")
        for i in range(TIMEOUT_TRIES):
            if iuhttp.check_url(self.config.config_port.websvr_hostname, self.config.input_ports.webserver_config.port, self.test_url, logger):
                logger.info("Server responds.")
                return
            time.sleep(TIME_BETWEEN_TRIES)
        raise UserError(errors[ERR_DJANGO_NO_RESP],
                        msg_args={"appname":self.config.app_short_name},
                        developer_msg="url was http://%s:%d%s" % (self.config.config_port.websvr_hostname, self.config.input_ports.webserver_config.port,
                                                                  self.test_url))

    def _run_python_script(self, script_name, arglist, file_layout, input=None):
        script_path = iufile.get_data_file_path(__file__, script_name)
        prog_and_args = [self.config.input_ports.python.home, script_path] + arglist
        rc = iuprocess.run_and_log_program(prog_and_args,
                                           file_layout.get_django_env_vars(),
                                           logger,
                                           cwd=file_layout.get_settings_file_directory(), input=input,
                                           hide_input=True)
        if rc != 0:
            raise UserError(errors[ERR_DJANGO_PYTHON_SCRIPT_FAILED],
                            msg_args={"appname":self.config.app_short_name,
                                      "script":script_name},
                            developer_msg="return code was %d, script at %s" % (rc, script_path))

    def _install_pip_requirements(self, requirements_file_path):
        prog_and_args = [self.config.input_ports.pip.pipbin, "install", "--requirement=%s" % requirements_file_path]
        env = {}
        if os.path.exists(self.config.package_cache_dir):
            env['PIP_DOWNLOAD_CACHE'] = self.config.package_cache_dir
        rc = iuprocess.run_and_log_program(prog_and_args, env, logger,
                                           cwd=os.path.dirname(self.config.input_ports.pip.pipbin))
        if rc == 0:
            logger.info("Successful installed requirements from file %s" % requirements_file_path)
        else:
            raise UserError(errors[ERR_REQUIREMENTS_INSTALL_FAILED],
                            developer_msg="return code was %d, requirements file was %s" % (rc, requirements_file_path))
            

    def __init__(self, metadata, config=None):
        # This driver is in the process of being migrated to the new-style action model.
        # We instantiate both the old-style config object and the new style context object.
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        # we give any subclasses a chance to override the configuration
        # object.
        if config==None:
            self.config = metadata.get_config(_config_type, Config, self.id,
                                              package_name, self._get_required_app_prop(PROP_APP_SHORT_NAME))
        else:
            self.config = config
        self.test_url = self._get_app_prop(PROP_APP_TEST_URL, PROP_APP_TEST_URL_DEFAULT)
        self.ctx = make_context(metadata.to_json(), sudo_password_fn=self._get_sudo_password,
                                dry_run=False) # cannot support dry-run mode until we move fully to new-style actions

    def _get_backup_file_list(self):
        """Need by the backup file mixin to know what to copy.
        """
        files = [self.config.home_path,]
        if self.config.input_ports.webserver_config.webserver_type=="apache":
            files.append("/etc/apache2/sites-enabled/%s_apache_wsgi.conf" % self.config.app_short_name)
        return files


    def validate_pre_install(self):
        iupath.check_installable_to_target_dir(self.config.home_path,
                                               self.config.package_name)
        logger.debug("%s instance %s passed pre-install checks." %
                     (self.config.package_name, self.id))

    def _extract_package(self, package):
        """Run validation on the packaged app and then extract it to the directory under
        home_path. Returns DjangoFileLayout and django_config instances.
        """
        if not os.path.exists(self.config.home_path):
            logger.action("mkdir -p %s" % self.config.home_path)
            os.makedirs(self.config.home_path)
            
        if self.config.user_specified_package:
            archive_file = self.config.application_archive
            if not os.path.exists(archive_file):
                raise UserError(errors[ERR_USER_ARCHIVE_NOT_FOUND],
                                msg_args={"file":archive_file})
        else:
            archive_file = package.get_file()
        try:
            with engage_django_sdk.packager.archive_handlers.create_handler(archive_file) as f:
                (common_dirname, django_config) = engage_django_sdk.packager.run_safe_validations(f)
                f.extract(self.config.home_path)
        except engage_django_sdk.packager.errors.FileFormatError:
            raise UserError(errors[ERR_USER_ARCHIVE_WRONG_FORMAT],
                                msg_args={"file":archive_file})
        except engage_django_sdk.packager.errors.ArchiveStructureError, m:
            raise UserError(errors[ERR_USER_ARCHIVE_STRUCTURE],
                            msg_args={"file":archive_file,
                                      "msg":m})
        except engage_django_sdk.packager.errors.FileMissingError, m:
            raise UserError(errors[ERR_USER_ARCHIVE_MISSING_FILE],
                            msg_args={"file":archive_file,
                                      "msg":m})

        file_layout = create_file_layout(django_config, common_dirname,
                                         self.config.home_path,
                                         self.config.django_admin_script)
        file_layout.write_as_json_file(self.config.output_ports.django.layout_cfg_file)
        return (file_layout, django_config)
    
    def _wsgi_setup(self, file_layout):
        # setup the wsgi configuration files
        # TODO: eventually, this should go into a separate driver
        wsgi_deploy_dir_path = os.path.join(self.config.home_path, "wsgi_deploy")
        if not os.path.exists(wsgi_deploy_dir_path):
            logger.action("mkdir -p %s" % wsgi_deploy_dir_path)
            os.makedirs(wsgi_deploy_dir_path)
        wsgi_substitutions = {
            "install_path": self.config.home_path,
            "settings_file_directory": file_layout.get_settings_file_directory(),
            "python_path": file_layout.get_python_path(),
            "python_exe": self.config.input_ports.python.home,
            "genforma_home": self.config.input_ports.host.genforma_home,
            "django_settings_module": file_layout.get_deployed_settings_module(),
            "app_short_name": self.config.app_short_name
        }
        target_wsgi_file = os.path.join(wsgi_deploy_dir_path, "apache_wsgi.wsgi")
        wsgi_file_template = iufile.get_data_file_path(__file__,"apache_wsgi.wsgi")
        iufile.instantiate_template_file(wsgi_file_template, target_wsgi_file, wsgi_substitutions, logger=logger)
        # the app can override the apache config file by providing one at
        # <settings_file_dir>/wsgi_deploy/<app_short_name>_apache_wsgi.conf.
        app_specific_apache_conf_file = os.path.join(os.path.join(file_layout.get_settings_file_directory(), "wsgi_deploy"),
                                                     "%s_apache_wsgi.conf" % self.config.app_short_name)
        if os.path.exists(app_specific_apache_conf_file):
            conf_file_template = app_specific_apache_conf_file
        else:
            conf_file_template = iufile.get_data_file_path(__file__,"django_apache_wsgi.conf")
        target_conf_file = os.path.join(wsgi_deploy_dir_path, "%s_apache_wsgi.conf" % self.config.app_short_name)
        iufile.instantiate_template_file(conf_file_template, target_conf_file, wsgi_substitutions, logger=logger)
        # We install a shell script that can be used to configure the wsgi.conf file
        config_mod_wsgi_file = os.path.join(wsgi_deploy_dir_path, "config_mod_wsgi.sh")
        iufile.instantiate_template_file(iufile.get_data_file_path(__file__, "config_mod_wsgi.sh"),
                                         config_mod_wsgi_file,
                                         wsgi_substitutions, logger=logger)
        # now run the shell script
        try:
            iuprocess.run_sudo_program([config_mod_wsgi_file], self._get_sudo_password(), logger,
                                       cwd=wsgi_deploy_dir_path)
        except iuprocess.SudoExcept, e:
            exc_info = sys.exc_info()
            raise convert_exc_to_user_error(exc_info, errors[ERR_WSGI_SCRIPT],
                                            msg_args={"script":config_mod_wsgi_file},
                                            nested_exc_info=e.get_nested_exc_info())

    def install(self, package, upgrade=False):
        # verify that the django-admin.py utility was installed (as a part of the
        # Django package)
        if not os.path.exists(self.config.django_admin_script):
            raise UserError(errors[ERR_NO_DJANGO_ADMIN_SCRIPT],
                            msg_args={"file":self.config.django_admin_script})

        (file_layout, django_config) = self._extract_package(package)

        # if present, install any pip requirements
        requirements_file_path = os.path.join(file_layout.get_app_dir_path(), "requirements.txt")
        if os.path.exists(requirements_file_path):
            assert hasattr(self.config.input_ports, "pip") and hasattr(self.config.input_ports.pip, "pipbin"), \
                   "%s has a requirements file, but resource is not configured for installing dependencies via pip" % self.config.package_name
            self._install_pip_requirements(requirements_file_path)
        else:
            logger.debug("Requirements file '%s' not found, skipping requirements step" % requirements_file_path)
            
        # Instantiate the settings file
        substitutions = {
            gs.INSTALL_PATH: self.config.home_path,
            gs.HOSTNAME: self.config.config_port.websvr_hostname,
            gs.PRIVATE_IP_ADDRESS: (lambda x: "'%s'" % x if x else "None")(self.config.input_ports.host.private_ip),
            gs.PORT: self.config.input_ports.webserver_config.port,
            gs.SECRET_KEY: gen_password(50, chars=string.digits+string.letters+"!#%&()*+,-./:;<=>?@[]^_`{|}~"),
            gs.EMAIL_HOST:self.config.config_port.email_host,
            gs.EMAIL_HOST_USER:self.config.config_port.email_host_user,
            gs.EMAIL_FROM:self.config.config_port.email_from,
            gs.EMAIL_HOST_PASSWORD:self.config.config_port.email_password,
            gs.EMAIL_PORT:self.config.config_port.email_port,
            gs.ADMIN_NAME:self.config.config_port.admin_name,
            gs.ADMIN_EMAIL:self.config.config_port.admin_email,
            gs.TIME_ZONE:self.config.config_port.time_zone,
            gs.LOG_DIRECTORY:self.config.config_port.log_directory,
            gs.DATABASE_ENGINE:self.config.input_ports.django_db.ENGINE,
            gs.DATABASE_NAME:self.config.input_ports.django_db.NAME,
            gs.DATABASE_USER:self.config.input_ports.django_db.USER,
            gs.DATABASE_PASSWORD:
                self.install_context.password_repository.get_value(self.config.input_ports.django_db.PASSWORD) \
                if self.config.input_ports.django_db.PASSWORD else '',  
            gs.DATABASE_HOST:self.config.input_ports.django_db.HOST,
            gs.DATABASE_PORT:self.config.input_ports.django_db.PORT,
            gs.CACHE_BACKEND:'memcached',
            gs.CACHE_LOCATION:'localhost:11211',
            gs.CELERY_CONFIG_BROKER_HOST:'None',
            gs.CELERY_CONFIG_BROKER_PORT:0,
            gs.CELERY_CONFIG_BROKER_USER:'None',
            gs.CELERY_CONFIG_BROKER_PASSWORD:'None',
            gs.CELERY_CONFIG_BROKER_VHOST:'None',
            gs.CELERY_CONFIG_CELERY_RESULT_BACKEND:'amqp',
            gs.REDIS_HOST:"localhost",
            gs.REDIS_PORT:6379
        }

        # we need to check that the cache input port is present (it isn't if this is
        # the gfwebsite resource).
        if hasattr(self.config.input_ports, "ocache") and self.config.input_ports.ocache.provider == 'memcached':
            substitutions[gs.CACHE_BACKEND] = 'memcached'
            substitutions[gs.CACHE_LOCATION] = '%s:%s' % (self.config.input_ports.ocache.host, self.config.input_ports.ocache.port)
        else: # Dummy
            substitutions[gs.CACHE_BACKEND] = 'django.core.cache.backends.dummy.DummyCache'
            substitutions[gs.CACHE_LOCATION] = ''

        # set up with django-celery
        if hasattr(self.config.input_ports, "celery") and self.config.input_ports.celery.provider == "celery":
            # celery configuration
            logger.info('Adding celery config!')
            substitutions[gs.CELERY_CONFIG_BROKER_HOST] = self.config.input_ports.celery.BROKER_HOST
            substitutions[gs.CELERY_CONFIG_BROKER_PORT] = self.config.input_ports.celery.BROKER_PORT
            substitutions[gs.CELERY_CONFIG_BROKER_USER] = self.config.input_ports.celery.BROKER_USER
            substitutions[gs.CELERY_CONFIG_BROKER_PASSWORD] = self.config.input_ports.celery.BROKER_PASSWORD
            substitutions[gs.CELERY_CONFIG_BROKER_VHOST] = self.config.input_ports.celery.BROKER_VHOST
            substitutions[gs.CELERY_CONFIG_CELERY_RESULT_BACKEND] = 'amqp'
        else:
            logger.info('No input port for celery')


        gs.generate_settings_file(file_layout.get_app_dir_path(),
                                  file_layout.get_app_settings_module(),
                                  django_config.components,
                                  properties=substitutions)

        # Validate the settings file. We run the validation script as an external program, have the results
        # written to an external file, and then parse that file to get detailed results.
        validate_results = \
            engage_django_sdk.packager.run_installed_tests_as_subprocess(file_layout.get_app_dir_path(),
                                                                         file_layout.get_app_settings_module(),
                                                                         python_exe_path=self.config.input_ports.python.home,
                                                                         use_logger=logger)
        rc = validate_results.get_return_code()
        if validate_results.run_was_successful():
            logger.info("Django settings file validation successful")
        else:
            raise UserError(errors[ERR_DJANGO_VALIDATE_FAILED],
                            msg_args={"rc":validate_results.get_return_code_desc()},
                            developer_msg=validate_results.format_messages())

        # instantiate the admin script (startup/shutdown/status) from a template
        substitutions = {
            "app_short_name": self.config.app_short_name,
            "install_dir": self.config.home_path,
            "settings_file_dir": file_layout.get_settings_file_directory(),
            "python_path": file_layout.get_python_path(),
            "django_settings_module": file_layout.get_deployed_settings_module(),
            "python_bin_dir": self.config.python_bin_dir,
            "websvr_hostname": self.config.websvr_listen_host,
            "port": self.config.input_ports.webserver_config.port,
            "log_directory": self.config.config_port.log_directory
        }
        admin_script_tmpl_path = iufile.get_data_file_path(__file__, "django.sh.tmpl")
        iufile.instantiate_template_file(admin_script_tmpl_path, self.config.app_admin_script, substitutions,
                                         logger=logger)
        os.chmod(self.config.app_admin_script, 0755)

        # modify manage.py to point at the our local python version and to have the right PYTHONPATH
        manage_py_file = os.path.join(file_layout.get_settings_file_directory(), "manage.py")
        if os.path.exists(manage_py_file):
            logger.debug("Updating manage.py file with correct python path and python executable")
            # default first line is "#!/usr/bin/env python", but user could
            # replace this with a different path
            shbang_pattern = '^\\#\\!.+$'
            # python.home is the python executable
            # home_path is where any local modules should go
            shbang_replacement = "#!%s\nimport sys\nsys.path.extend(%s)" % \
                (self.config.input_ports.python.home, file_layout.get_python_path().split(":").__repr__())
            import_pattern = re.escape("import settings")
            import_replacement = "import deployed_settings"
            call_pattern = re.escape("execute_manager(settings)")
            call_replacement = "execute_manager(deployed_settings)"
            cnt = iufile.subst_in_file(manage_py_file,
                                       [(shbang_pattern, shbang_replacement),
                                        (import_pattern, import_replacement),
                                        (call_pattern, call_replacement)])
            if cnt != 3:
                logger.warning("Substitutions for %s did not match expected number (got %d, expecting 3). Your manage.py script might not be usable without hand-modifying it." % (manage_py_file, cnt))
        else:
            logger.debug("No manage.py file, skipping shbang replacement")

        # make the log directory
        if not os.path.exists(self.config.config_port.log_directory):
            logger.action("mkdir -p %s" % self.config.config_port.log_directory)
            os.makedirs(self.config.config_port.log_directory)
            
        # setup the database
        if self.config.input_ports.django_db.ENGINE=='django.db.backends.sqlite3':
            database_dir = os.path.dirname(self.config.input_ports.django_db.NAME)
            if not os.path.exists(database_dir):
                logger.action("mkdir -p %s" % database_dir)
                os.makedirs(database_dir)
        file_layout.run_admin_command("syncdb", ["--noinput"])
        if "south" in django_config.installed_apps:
            # We use the presence of South in INSTALLED_APPS to indicate that
            # we should run migrations. If South isn't there, migrate will fail.
            if upgrade:
                file_layout.run_admin_command("migrate", ["--no-initial-data"])
            else:
                file_layout.run_admin_command("migrate", [])
           
        # if we have fixtures and this is the initial install, load them
        if len(django_config.fixtures)>0 and not upgrade:
            file_layout.run_admin_command("loaddata", django_config.fixtures)

        # See if this application includes the admin password parameter.
        # If so, we set the password by running a script.
        try:
            app_pw = self.config.config_port.app_admin_password
        except:
            app_pw = None
        if app_pw:
            self._run_python_script("django_set_password.py", ["-c", "-e", self.config.config_port.admin_email, "-s"],
                                    file_layout, input=self.config.config_port.app_admin_password)

        # setup the webserver hooks
        if self.config.input_ports.webserver_config.webserver_type == "apache":
            self._wsgi_setup(file_layout)
            self.ctx.r(apache_utils.restart_apache, self.ctx.props.input_ports.webserver_config)

    def upgrade(self, package, old_metadata, backup_root_directory):
        """Upgrade django, which is mostly just re-installing. We skip the loading
        of initialization data in upgrades."""
        if not self.is_installed():
            self.install(package, upgrade=True)

    def get_pid_file_path(self):
        """If we aren't using apache, we have a pid file corresponding to
        the django webserver. Otherwise, return None, as the pidfile is associated
        with apache.
        """
        if self.config.input_ports.webserver_config.webserver_type != "apache":
            return os.path.join(self.config.home_path, "django.pid")
        else:
            return None
        
    def start(self):
        if self.config.input_ports.webserver_config.webserver_type == "apache":
            self.ctx.r(apache_utils.start_apache, self.ctx.props.input_ports.webserver_config)
        else: # need to start the development webserver
            if not os.path.exists(self.config.app_admin_script):
                raise UserError(errors[ERR_NO_DJANGO_SCRIPT],
                                msg_args={"file":self.config.app_admin_script, "appname":self.config.app_short_name})
            prog_and_args = [self.config.app_admin_script, "start"]
            rc = iuprocess.run_background_program(prog_and_args, {}, os.path.join(self.config.config_port.log_directory, "%s_startup.log" % self.config.app_short_name),
                                                  logger)
            if rc != 0:
                raise UserError(errors[ERR_DJANGO_STARTUP], msg_args={"appname":self.config.app_short_name},
                                developer_msg="script %s, rc was %d" % (self.config.app_admin_script, rc))

        # wait for startup
        self._check_server_response()
        logger.info("%s instance %s started successfully at %s:%d" %
                    (self.config.app_short_name, self.config.id, self.config.config_port.websvr_hostname,
                     self.config.input_ports.webserver_config.port))

    def stop(self):
        if self.config.input_ports.webserver_config.webserver_type == "apache":
            self.ctx.r(apache_utils.stop_apache, self.ctx.props.input_ports.webserver_config)
        else:
            if not os.path.exists(self.config.app_admin_script):
                raise UserError(errors[ERR_NO_DJANGO_SCRIPT],
                                msg_args={"file":self.config.app_admin_script, "appname":self.config.app_short_name})
            rc = iuprocess.run_and_log_program([self.config.app_admin_script, "stop"], {}, logger)
            if rc != 0:
                raise UserError(errors[ERR_DJANGO_SHUTDOWN], msg_args={"appname":self.config.app_short_name},
                                developer_msg="script %s, rc was %d" % (self.config.app_admin_script, rc))

    def is_running(self):
        if self.config.input_ports.webserver_config.webserver_type == "apache":
            return self.ctx.rv(apache_utils.apache_is_running, self.ctx.props.input_ports.webserver_config)
        else:
            if not os.path.exists(self.config.app_admin_script):
                raise UserError(errors[ERR_NO_DJANGO_SCRIPT],
                                msg_args={"file":self.config.app_admin_script, "appname":self.config.app_short_name})
            rc = iuprocess.run_and_log_program([self.config.app_admin_script, "status"], {}, logger)
            if rc == 0:
                # if we think it is running, check the webserver's url
                self._check_server_response()
                return True
            elif rc == 1:
                return False
            else:
                raise UserError(errors[ERR_DJANGO_STATUS], msg_args={"appname":self.config.app_short_name},
                                developer_msg="script %s, rc was %d" % (self.config.app_admin_script, rc))


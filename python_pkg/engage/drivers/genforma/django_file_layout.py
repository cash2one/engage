"""
Class to manage dynamic aspects of django installation. Some parts of the file layout
are determined by the specific django app. We compute all the values and store
them in a DjangoFileLayout object. This makes the code for the Django app driver
simpler and makes it available to components which depend on the django app.

This class can be converted to json and then reinstantiated. The django app driver
saves it on the filesystem in the location determined by the layout_cfg_file
output property of its resource definition.
"""

import os.path
import json
import urlparse

import fixup_python_path

import engage.utils.log_setup
logger = engage.utils.log_setup.setup_engage_logger(__name__)

from engage.utils.json_utils import JsonObject
import engage_utils.process as iuprocess
from engage.utils.user_error import EngageErrInf, UserError
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info


ERR_DJANGO_ADMIN_CMD_FAILED = 1
ERR_DJANGO_BACKGROUND_ADMIN_CMD_FAILED = 2

define_error(ERR_DJANGO_ADMIN_CMD_FAILED,
             _("Django administration command '%(cmd)s' failed"))
define_error(ERR_DJANGO_BACKGROUND_ADMIN_CMD_FAILED,
             _("Starting Django administration command '%(cmd)s' as a background process failed"))


# properties for use in the json representation
APP_DIR_PATH = "app_dir_path"
DEPLOYED_SETTINGS_MODULE = "deployed_settings_module"
APP_SETTINGS_MODULE = "app_settings_module"
SETTINGS_FILE_DIRECTORY = "settings_file_directory"
PYTHON_PATH_DIRECTORY = "python_path_directory"
DJANGO_ADMIN_PY = "django_admin_py"
MEDIA_ROOT = "media_root"
MEDIA_URL = "media_url"
STATIC_URL = "static_url"
STATIC_ROOT = "static_root"

_json_keys = [APP_DIR_PATH, DEPLOYED_SETTINGS_MODULE, APP_SETTINGS_MODULE,
              SETTINGS_FILE_DIRECTORY, PYTHON_PATH_DIRECTORY,
              DJANGO_ADMIN_PY, MEDIA_ROOT, MEDIA_URL, STATIC_URL, STATIC_ROOT]


class DjangoFileLayout(JsonObject):
    def __init__(self, json_props):
        JsonObject.__init__(self, _json_keys, required_properties=_json_keys,
                            prop_val_dict=json_props)

    def get_app_dir_path(self):
        """Returns full path to top level directory of the extracted app. This will
        be one level below the home_path
        """
        return self.app_dir_path

    def get_deployed_settings_module(self):
        """We set the django settings value to the name of this module.
        """
        return self.deployed_settings_module

    def get_app_settings_module(self):
        """The settings module for the application itself, provided by the
        app developer when they package the app.
        """
        return self.app_settings_module

    def get_settings_file_directory(self):
        """Directory containing the app's settings file. By default,
        we run settings scripts from here.
        """
        return self.settings_file_directory

    def get_python_path(self):
        """Value for PYTHONPATH in order for settings
        modules to be imported.
        """
        if self.get_settings_file_directory()==self.python_path_directory:
            return self.python_path_directory
        else:
            return self.python_path_directory + ":" + self.get_settings_file_directory()

    def get_django_admin_py(self):
        """Path to django-admin.py script. This is used to run management commands.
        """
        return self.django_admin_py

    def get_django_env_vars(self):
        """Return a map containing the correct values for the
        PYTHONPATH and DJANGO_SETTINGS_MODULE environment variables.
        """
        return {
            "PYTHONPATH":self.get_python_path(),
            "DJANGO_SETTINGS_MODULE": self.get_deployed_settings_module()
        }

    def has_media_url_mapping(self):
        return self.media_url!=None and self.media_root!=None and \
               self.media_root!=''
    
    def get_media_url_mapping(self):
        return (self.media_url, self.media_root)

    def has_static_url_mapping(self):
        if self.static_url==None or self.static_url=='':
            return False
        else:
            return True
    
    def get_static_url_mapping(self):
        return (self.static_url, self.static_root)
    
    def write_as_json_file(self, filename):
        with open(filename, "wb") as f:
            json.dump(self.to_json(), f)

    def run_admin_command(self, command, arglist, cwd=None):
        """Run a command of the django-admin.py script
        """
        prog_and_args = [self.django_admin_py, command] + arglist
        if not cwd:
            cwd = self.settings_file_directory
        rc = iuprocess.run_and_log_program(prog_and_args,
                                           self.get_django_env_vars(),
                                           logger, cwd=cwd)
        if rc != 0:
            raise UserError(errors[ERR_DJANGO_ADMIN_CMD_FAILED],
                            msg_args={"cmd":' '.join([command]+arglist)},
                            developer_msg="return code was %d, PYTHONPATH was %s, DJANGO_SETTINGS_MODULE was %s, current working directory was %s" %
                            (rc, self.python_path_directory,
                             self.deployed_settings_module, cwd))

    def run_admin_command_as_background_task(self, command, arglist,
                                             logfile, pidfile, cwd=None):
        """Start an admin command as an ongoing background task
        """
        prog_and_args = [self.django_admin_py, command] + arglist
        if not cwd:
            cwd = self.settings_file_directory
        try:
            iuprocess.run_server(prog_and_args,
                                 self.get_django_env_vars(),
                                 logfile, logger, pidfile_name=pidfile,
                                 cwd=cwd)
        except iuprocess.ServerStartupError, e:
            logger.exception("Error in startup of django admin command %s: %s" %
                             (command, e))
            raise UserError(errors[ERR_DJANGO_BACKGROUND_ADMIN_CMD_FAILED],
                            msg_args={"cmd":' '.join([command]+arglist)},
                            developer_msg="error was %s, PYTHONPATH was %s, DJANGO_SETTINGS_MODULE was %s, current working directory was %s" %
                            (e, self.get_python_path_director(),
                             self.deployed_settings_module, cwd))
    

def create_file_layout(django_config, common_dirname,
                       home_path, django_admin_py, public_hostname,
                       public_port):
    """Create a new file layout object, given the django_config read from
    the application package and other basic info about the install.
    """
    app_dir_path = os.path.join(home_path, common_dirname)
    if public_port==80 or public_port=="80":
        base_url = "http://%s" % public_hostname
    else:
        base_url = "http://%s:%s" % (public_hostname, public_port)
    json_props = {
        APP_DIR_PATH: app_dir_path,
        DEPLOYED_SETTINGS_MODULE: django_config.get_deployed_settings_module(),
        APP_SETTINGS_MODULE: django_config.django_settings_module,
        SETTINGS_FILE_DIRECTORY: django_config.get_settings_file_directory(home_path),
        PYTHON_PATH_DIRECTORY: django_config.get_python_path_directory(home_path),
        DJANGO_ADMIN_PY: django_admin_py,
        MEDIA_ROOT: os.path.join(app_dir_path, django_config.media_root_subdir) if django_config.media_root_subdir else None,
        MEDIA_URL: urlparse.urljoin(base_url, django_config.media_url_path) if django_config.media_url_path else None,
        STATIC_URL: urlparse.urljoin(base_url, django_config.static_url_path) if django_config.static_url_path else None,
        STATIC_ROOT: os.path.join(app_dir_path, django_config.static_root_subdir) if django_config.static_root_subdir else None,
    }
    return DjangoFileLayout(json_props)


def create_file_layout_from_json(json_dict):
    return DjangoFileLayout(json_dict)
    



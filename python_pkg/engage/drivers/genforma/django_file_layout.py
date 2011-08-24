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

import fixup_python_path

import engage.utils.log_setup
logger = engage.utils.log_setup.setup_engage_logger(__name__)

import engage.utils.process as iuprocess
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

_json_keys = [APP_DIR_PATH, DEPLOYED_SETTINGS_MODULE, APP_SETTINGS_MODULE,
              SETTINGS_FILE_DIRECTORY, PYTHON_PATH_DIRECTORY,
              DJANGO_ADMIN_PY]


class DjangoFileLayout(object):
    # create an instance from json representation
    def create_file_layout_from_json(json_dict):
        pass
    
    def __init__(self, app_dir_path, deployed_settings_module, app_settings_module,
                 settings_file_directory, python_path_directory,
                 django_admin_py):
        self.app_dir_path = app_dir_path
        self.deployed_settings_module = deployed_settings_module
        self.app_settings_module = app_settings_module
        self.settings_file_directory = settings_file_directory
        self.python_path_directory = python_path_directory
        self.django_admin_py = django_admin_py

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

    def to_json(self):
        """Return json in-memory (dict) representation.
        """
        return {
            APP_DIR_PATH: self.app_dir_path,
            DEPLOYED_SETTINGS_MODULE: self.deployed_settings_module,
            APP_SETTINGS_MODULE: self.app_settings_module,
            SETTINGS_FILE_DIRECTORY: self.settings_file_directory,
            DJANGO_ADMIN_PY: self.django_admin_py,
            PYTHON_PATH_DIRECTORY: self.python_path_directory
        }

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
        rc = iuprocess.run_background_program(prog_and_args,
                                              self.get_django_env_vars(),
                                              logfile, logger, cwd=cwd,
                                              pidfile=pidfile)
        if rc != 0:
            raise UserError(errors[ERR_DJANGO_BACKGROUND_ADMIN_CMD_FAILED],
                            msg_args={"cmd":' '.join([command]+arglist)},
                            developer_msg="return code was %d, PYTHONPATH was %s, DJANGO_SETTINGS_MODULE was %s, current working directory was %s" %
                            (rc, self.get_python_path_director(),
                             self.deployed_settings_module, cwd))
    

def create_file_layout(django_config, common_dirname,
                       home_path, django_admin_py):
    """Create a new file layout object, given the django_config read from
    the application package and other basic info about the install.
    """
    app_dir_path = os.path.join(home_path, common_dirname)
    deployed_settings_module = django_config.get_deployed_settings_module()
    app_settings_module = django_config.django_settings_module
    settings_file_directory = django_config.get_settings_file_directory(home_path)
    python_path_directory = django_config.get_python_path_directory(home_path)
    return DjangoFileLayout(app_dir_path, deployed_settings_module,
                            app_settings_module, settings_file_directory,
                            python_path_directory, django_admin_py)


def create_file_layout_from_json(json_dict):
    for key in _json_keys:
        if not json_dict.has_key(key):
            raise Exception("Django file layout missing required key %s" % key)
    return DjangoFileLayout(json_dict[APP_DIR_PATH],
                            json_dict[DEPLOYED_SETTINGS_MODULE],
                            json_dict[APP_SETTINGS_MODULE],
                            json_dict[SETTINGS_FILE_DIRECTORY],
                            json_dict[PYTHON_PATH_DIRECTORY],
                            json_dict[DJANGO_ADMIN_PY])
    



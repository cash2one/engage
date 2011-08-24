"""Service manager for PIL (Python Imaging Library)
"""
import os
import os.path
import shutil
import sys
import time

import engage.drivers.resource_manager as resource_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.utils.path as iupath
import engage.utils.process as iuprocess
import engage.utils.http as iuhttp
import engage.utils.log_setup
import engage.utils.file as iufile
import engage.utils.timeout as iutimeout

logger = engage.utils.log_setup.setup_script_logger(__name__)

from engage.utils.user_error import ScriptErrInf, UserError

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_PIL_BUILD_FAILED    = 1
ERR_PIL_NO_INSTALL_DIR  = 2


define_error(ERR_PIL_BUILD_FAILED,
             _("PIL (Python Imaging Library) build failed"))
define_error(ERR_PIL_NO_INSTALL_DIR,
             _("Post install check failed: missing installation directory '%(dir)s'"))


# timeouts for checking server liveness after startup
TIMEOUT_TRIES = 10
TIME_BETWEEN_TRIES = 2.0



class Config(resource_metadata.Config):
    def __init__(self, props_in, types, id, package_name):
        resource_metadata.Config.__init__(self, props_in, types)
        self._add_computed_prop("id", id)
        self._add_computed_prop("package_name", package_name)
        self._add_computed_prop("extract_target_path",
                                os.path.join(self.input_ports.host.genforma_home,"Imaging-1.1.7"))
                                
_config_type = { }

class Manager(resource_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.config = metadata.get_config(_config_type, Config, self.id,
                                          package_name)

    def validate_pre_install(self):
        iupath.check_installable_to_target_dir(self.config.extract_target_path,
                                               self.config.package_name)
        logger.debug("%s instance %s passed pre-install checks." %
                     (self.config.package_name, self.id))
        
    def install(self, package):
        extracted_dir = package.extract(self.config.input_ports.host.genforma_home)
        rc = iuprocess.system('cd %s; %s setup.py install' %
                              (self.config.extract_target_path,
                               self.config.input_ports.python.home), logger,
                              log_output_as_info=True)
        if rc != 0:
            raise UserError(errors[ERR_PIL_BUILD_FAILED])
        # check that everything is now in place
        self.validate_post_install()


    def is_installed(self):
        return os.path.exists(os.path.join(self.config.input_ports.python.PYTHONPATH,'PIL'))

    def validate_post_install(self):
        return True


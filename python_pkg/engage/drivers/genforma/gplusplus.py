"""Resource manager for g++. For mac, we check that it's installed. For ubuntu linux, we call the package manager if it isn't there.
"""
import os
import os.path
import shutil
import sys
import time

import engage.drivers.resource_manager as resource_manager
import engage.drivers.resource_metadata as resource_metadata
from engage.drivers.password_repo_mixin import PasswordRepoMixin
import aptget
import engage.utils.log_setup as log_setup

logger = log_setup.setup_script_logger(__name__)

from engage.utils.user_error import ScriptErrInf, UserError

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_GPP_UNSUPPORTED_OS_FOR_INSTALL = 1
ERR_GPP_NOT_FOUND                  = 2


define_error(ERR_GPP_UNSUPPORTED_OS_FOR_INSTALL,
             _("Unable to automatically install g++ on Mac-OSX. Please install XCode (Apple's developer tools)"))
define_error(ERR_GPP_NOT_FOUND,
             _("g++ executable not found at %(path)s after install"))


_config_type = {
    "input_ports": {
      "host": {
          "hostname": unicode,
          "os_type" : unicode,
          "os_user_name" : unicode,
          "sudo_password" : unicode,
          "cpu_arch" : unicode
        }
    }
}

class Config(resource_metadata.Config):
    def __init__(self, props_in, types, id, package_name):
        resource_metadata.Config.__init__(self, props_in, types)
        self._add_computed_prop("id", id)
        self._add_computed_prop("package_name", package_name)
                                

GPP_PATH = "/usr/bin/g++"

class Manager(resource_manager.Manager, PasswordRepoMixin):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.config = metadata.get_config(_config_type, Config, self.id,
                                          package_name)

    def validate_pre_install(self):
        pass

    def is_installed(self):
        # for now, just look in the default location
        if os.path.exists(GPP_PATH):
            logger.info("g++ found at %s" % GPP_PATH)
            return True
        else:
            logger.info("g++ not found")
            return False
        
    def install(self, package):
        if self.config.input_ports.host.os_type == "mac-osx":
            raise UserError(errors[ERR_GPP_UNSUPPORTED_OS_FOR_INSTALL])
        aptget.apt_get_install(["g++"], self._get_sudo_password())
                                              
        # check that everything is now in place
        self.validate_post_install()

    def validate_post_install(self):
        if not os.path.exists(GPP_PATH):
            raise UserError(ERR_GPP_NOT_FOUND, {"path": GPP_PATH})


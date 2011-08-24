"""Resource manager for git. Main purpose of this class
is to check that git is installed correctly.
"""

import os.path

import commands
import engage.drivers.resource_manager as resource_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.utils.log_setup

logger = engage.utils.log_setup.setup_script_logger("git")

from engage.utils.user_error import UserError, ScriptErrInf
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("git", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_GIT_NOT_FOUND      = 1

define_error(ERR_GIT_NOT_FOUND,
             _("GIT installation invalid: git executable '%(git)s' not found or is not runnable"))

_config_type = {
    "config_port": {
    "git_exe": unicode
    }
}

class Config(resource_metadata.Config):
    def __init__(self, props_in, types, id, package_name):
        resource_metadata.Config.__init__(self, props_in, types)


class Manager(resource_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.config = metadata.get_config(_config_type, Config,
                                          self.id, package_name)
    
    def validate_pre_install(self):
        raise UserError(errors[ERR_INSTALL_NOT_SUPPORTED])

    def install(self):
        raise UserError(errors[ERR_INSTALL_NOT_SUPPORTED])

    def patch(self):
	pass

    def uninstall(self):
	pass

    def backup(self):
	pass
    def restore(self):
	pass

    def validate_post_install(self):
        logger.info("%s: validate_post_install called"
		    % self.package_name)
        if not os.path.exists(self.config.config_port.git_exe):
            raise UserError(errors[ERR_GIT_NOT_FOUND],msg_args={"git":self.config.config_port.git_exe})

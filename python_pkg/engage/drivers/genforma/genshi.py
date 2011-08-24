"""Resource manager for genshi. 
"""

import commands
import os
import engage.drivers.resource_manager as resource_manager

from engage.utils.user_error import UserError, ScriptErrInf
import engage.utils.log_setup
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("setuptools", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_GENSHI = 1

define_error(ERR_GENSHI,
             _("error installing Genshi using easy_install"))

logger = engage.utils.log_setup.setup_script_logger("genshi")

_config_type = {
    "input_ports": {
        "setuptools": {
            "easy_install": unicode
        }
    }
}

class Manager(resource_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.config = metadata.get_config(_config_type, resource_metadata.Config,
                                          self.id, package_name)

    def validate_pre_install(self):
	pass

    def is_installed(self):
	return False

    def install(self, download_url):
        easy_install = self.config.input_ports.setuptools.easy_install
        easy_install_cmd = '%s Genshi' % easy_install
        logger.action(easy_install_cmd)
	if os.system(easy_install_cmd) != 0:
		raise UserError(errors[ERR_GENSHI])


    def validate_post_install(self):
	pass

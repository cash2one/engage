"""Resource manager for accountManagerPlugin. 
"""

import string
import re
import commands
import os

import engage.drivers.resource_manager as resource_manager
import engage.drivers.resource_metadata as resource_metadata

import engage.utils.path as iupath
import engage.utils.process as iuprocess
from engage.drivers.genforma.python_utils import is_python_package_installed

import engage.utils.log_setup
logger = engage.utils.log_setup.setup_script_logger("AccountManagerPlugin")

from engage.utils.user_error import UserError, ScriptErrInf
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("AccountManagerPlugin", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_ACCOUNTMANAGERPLUGIN = 1

define_error(ERR_ACCOUNTMANAGERPLUGIN,
             _("error installing AccountManagerPlugin"))


class Config(resource_metadata.Config):
    def __init__(self, props_in, types, id, package_name):
        resource_metadata.Config.__init__(self, props_in, types)
	self._add_computed_prop("PYTHONPATH", self.input_ports.python.PYTHONPATH)
	self._add_computed_prop("genforma_home", self.input_ports.host.genforma_home)
	self._add_computed_prop("easy_install", self.input_ports.setuptools.easy_install)

_config_type = {
    "input_ports": {
        "host": { "genforma_home": unicode },
        "python": { "PYTHONPATH": unicode, "home": unicode },
	"setuptools": { "easy_install" : unicode },
    }
}

class Manager(resource_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
	self.config = metadata.get_config(_config_type, Config, self.id, package_name)
    
    def validate_pre_install(self):
	pass

    def is_installed(self):
        return is_python_package_installed(self.config.PYTHONPATH,
                                           "TracAccountManager.*",
                                           self.package_name,
                                           logger)

    def install(self, download_url):
	logger.debug("Installing AccountManagerPlugin from %s" % download_url.location )
        install_prefix = string.join(["--prefix",self.config.genforma_home], '=')
        # XXX this needs to be in the resource defs!
        install_dir    = "--install-dir=" + self.config.PYTHONPATH
        install_cmd = self.config.easy_install
        rc = iuprocess.run_and_log_program([install_cmd, install_prefix, install_dir, download_url.location],
                                      {},
                                      logger,
                                      None, None)
	if rc != 0:
		raise UserError(errors[ERR_TRAC])
	logger.debug("Done installing AccountManagerPlugin")

    def validate_post_install(self):
	pass

"""Resource manager for trac v 0.11. 
"""

import string

import commands
import os
import os.path
import subprocess

import engage.drivers.resource_manager as resource_manager
import engage.drivers.service_manager as service_manager
import engage.drivers.resource_metadata as resource_metadata

import engage_utils.process as iuprocess
import engage.utils.path as iupath
import engage.utils.log_setup
import engage.utils.file as iufile
import engage.utils.http as iuhttp
from engage.drivers.patch_resource_mixin import PatchResourceMixin
from engage.drivers.genforma.python_utils import run_compileall


# TODO: this should somehow be configurable or automatically determined
TRAC_EGG_DIRNAME = "Trac-0.11.6-py2.6.egg"


from engage.utils.user_error import UserError, ScriptErrInf
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_TRAC = 1
ERR_TRACD_NOT_RUNNING = 2

define_error(ERR_TRAC,
             _("error installing Trac using easy_install"))
define_error(ERR_TRACD_NOT_RUNNING,
             _("Attempt to stop trac daemon: not running"))

logger = engage.utils.log_setup.setup_script_logger(__name__)

_config_type = {
    "config_port": {
        "home" : unicode
    },
    "input_ports": {
        "python": {
            "home": unicode,
            "PYTHONPATH" : unicode
        },
        "setuptools": {
            "easy_install": unicode
        }
    }
}

class Config(resource_metadata.Config):
    def __init__(self, props_in, types, id, package_name):
        resource_metadata.Config.__init__(self, props_in, types)
	self._add_computed_prop("home", os.path.abspath(self.config_port.home))
    
class Manager(resource_manager.Manager, PatchResourceMixin):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.config = metadata.get_config(_config_type, Config, self.id, package_name)
        self.logger = logger

    def validate_pre_install(self):
	"""check easy_install, genshi, sqlite3"""
	pass

    def is_installed(self):
	logger.debug("checking if trac is installed")
	trac_admin_exe = self.config.home + "/bin/trac-admin"
	if os.system('type ' + trac_admin_exe)	!= 0:
		return False
	else:
		return True

    def install(self, download_url):
	logger.debug("installing trac %s" % download_url.location )
	print self.config.home
	install_prefix = string.join(["--prefix",self.config.home], '=')
        # XXX this needs to be in the resource defs!
        install_dir    = "--install-dir=" + self.config.input_ports.python.PYTHONPATH
	install_cmd = self.config.input_ports.setuptools.easy_install
	rc = iuprocess.run_and_log_program([install_cmd, install_prefix, install_dir, download_url.location],
				      {},
				      logger,
				      None, None)
	if rc != 0:
		raise UserError(errors[ERR_TRAC])

        if self._has_patch():
            patch_dir = os.path.join(self.config.input_ports.python.PYTHONPATH,
                                     TRAC_EGG_DIRNAME)
            self._install_patch(patch_dir)
            # we need to recompile the python files after applying the patch
            run_compileall(self.config.input_ports.python.home,
                           patch_dir, logger)

    def validate_post_install(self):
	pass


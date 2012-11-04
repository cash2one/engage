"""Base resource manager class for Trac plugins. This class works for
plugins with the following properties:
 - Plugin comes as a local archive file (e.g. .tar.gz)
 - Plugin contains a subdirectory named after the trac version (e.g. 0.11)
 - The trac version subdirectory contains a setup.py script, compliant with
   setuputils.
 - To install the plugin, one runs:
   python setup.py install --prefix=$pythonpath

TODO: we should support downloading the plugin directly from trac-hacks.org
"""

import re
import commands
import os
import copy

import engage.drivers.resource_manager as resource_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.utils.path as iupath
import engage_utils.process as iuprocess
from engage.drivers.genforma.python_utils import is_python_package_installed
from engage.drivers.patch_resource_mixin import PatchResourceMixin

import engage.utils.log_setup
logger = engage.utils.log_setup.setup_script_logger("trac_plugin")

#from user_error import ScriptErrInf, UserError, convert_exc_to_user_error

from engage.utils.user_error import UserError, ScriptErrInf
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("trac_plugin", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_TRAC_PLUGIN_SETUP = 1

define_error(ERR_TRAC_PLUGIN_SETUP,
             _("Error in running setup script for Trac plugin '%{plugin}s'"))



class Config(resource_metadata.Config):
    def __init__(self, props_in, types, id, package_name):
        resource_metadata.Config.__init__(self, props_in, types)
        self._add_computed_prop("package_name", package_name)
	self._add_computed_prop("PYTHONPATH", self.input_ports.python.PYTHONPATH)
	self._add_computed_prop("genforma_home", self.input_ports.host.genforma_home)

_config_type = {
    "input_ports": {
        "host": { "genforma_home": unicode },
        "python": { "PYTHONPATH": unicode, "home": unicode }
    }
}


def get_config_type():
    """Return the metadata describing the expected properties
    for the config, input, and output ports of the associated
    resource. We make a deep copy so that individual resource
    managers can add any properties that are specific to that
    project type.
    """
    return copy.deepcopy(_config_type)


class Manager(resource_manager.Manager, PatchResourceMixin):
    def __init__(self,
                 metadata,     # metadata object containing resource instance
                 config_type,  # dictionary representation of config datatype
                 config_class, # class to instantiate for config (should be
                               # a subclass of trac_plugin.config)
                 installed_file_regexp, # Regexp string describing the
                                        # file/directory created in the python
                                        # site-packages directory if package
                                        # is installed
                 trac_version # string representation of trac version
                 ):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
	self.config = metadata.get_config(config_type, config_class,
                                          self.id, package_name)
        self.installed_file_regexp = installed_file_regexp
        self.trac_version = trac_version
        self.logger = logger
    
    def validate_pre_install(self):
	pass

    def is_installed(self):
        return is_python_package_installed(self.config.PYTHONPATH,
                                           self.installed_file_regexp,
                                           self.package_name,
                                           logger)

    def install(self, package):
	logger.debug("Installing %s" % self.package_name)
	extracted_dir = package.extract(self.config.genforma_home)
	logger.debug("Extracted directory is: " + extracted_dir)

        # if there is a patch, install it now
        if self._has_patch():
            self._install_patch(os.path.join(self.config.genforma_home,
                                             extracted_dir))

        #python setup.py install --prefix=pythonpath
        setup_script_dir = iupath.join_list([self.config.genforma_home,
                                             extracted_dir, self.trac_version])
        setup_script = os.path.join(setup_script_dir, "setup.py")
        args = [self.config.input_ports.python.home,
                setup_script, "install"]
        # must run setup from the setup script directory
        rc = iuprocess.run_and_log_program(args, {},logger,
                                           cwd=setup_script_dir)
        if rc != 0:
            raise UserError(errors[ERR_TRAC_PLUGIN_SETUP],
                            msg_args={'plugin': self.package_name},
                            developer_msg=' '.join(args))
	logger.debug("Done installing %s" % self.package_name)

    def validate_post_install(self):
	pass

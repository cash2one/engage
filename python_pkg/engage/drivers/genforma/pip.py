"""Resource manager for pip packages. 
"""

import commands
import os

import engage.drivers.resource_manager as resource_manager
import  engage.drivers.resource_metadata as resource_metadata
import engage.engine.library as library
import engage.utils.path as path
import engage.utils.process as iuproc
import engage.utils.log_setup as iulog_setup

from engage.utils.user_error import UserError, ScriptErrInf
import gettext
_ = gettext.gettext

logger = iulog_setup.setup_script_logger(__name__)

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("pip", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_PKG = 1

define_error(ERR_PKG,
             _("error installing %(pkg)s using pip"))

_config_type = {
    "input_ports": {
    "pip" : { "pipbin": unicode }
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
	try:
           self.prefix_dir = metadata.config_port["install_dir"]
        except:
           self.prefix_dir = None
	try:
           self.script_dir = metadata.config_port["script_dir"]
        except:
           self.script_dir = None
        self.pip = self.config.input_ports.pip.pipbin 
        self.editable = False

    
    def validate_pre_install(self):
	pass

    def is_installed(self):
	return False

    def install(self, package):
        cmd = [self.pip, 'install']
        if self.editable:
            cmd.append('-e')
        if self.prefix_dir != None:
            cmd.append("--prefix_dir=%s" % self.prefix_dir)
        if self.script_dir != None:
            cmd.append("--script-dir=%s" % self.script_dir)
            if not os.path.exists(self.script_dir):
                # TODO:
                # This is a workaround for the pygments package used by trac:
                # The script is supposed to be installed in trac's bin directory,
                # but that directory does not yet exist (since pygments is a
                # dependency for trac). To solve this, we just create the script
                # directory (in this case genforma_home/trac/bin) if it does
                # not already exist. We should see if there's a better solution
                # in how we model resources.
                logger.warn("Script directory '%s' for %s does not exist, attempting to create it" %
                            (self.script_dir, package.location))
                os.makedirs(self.script_dir)
        if package.type == library.Package.REFERENCE_TYPE:
            # reference package type should be used for package names (e.g. Django)
            # or URL's
            cmd.append(package.location)
        else:
            # if a file or archive, then we get the local location and pass that
            # to pip 
            filepath = package.get_file()
            cmd.append(filepath)
        rc = iuproc.run_and_log_program(cmd, { 'PATH': os.environ.get('PATH', []) }, logger)
	if rc != 0:
            raise UserError(errors[ERR_PKG], {"pkg":package.__repr__()} )


    def validate_post_install(self):
	pass

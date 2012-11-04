"""Resource manager for gitPlugin. 
"""

import re
import commands
import os

import engage.drivers.resource_manager as resource_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.utils.path as iupath
import engage_utils.process as iuprocess

import engage.utils.log_setup
logger = engage.utils.log_setup.setup_script_logger("GitPlugin")

#from user_error import ScriptErrInf, UserError, convert_exc_to_user_error

from engage.utils.user_error import UserError, ScriptErrInf
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("gitplugin", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_GITPLUGIN = 1
ERR_GIT_REPO_NOT_FOUND = 2


define_error(ERR_GITPLUGIN,
             _("error installing GitPlugin"))
define_error(ERR_GIT_REPO_NOT_FOUND,
             _("GIT repository invalid: git repository directory '%(repo)s' not found"))


class Config(resource_metadata.Config):
    def __init__(self, props_in, types, id, package_name):
        resource_metadata.Config.__init__(self, props_in, types)
	self._add_computed_prop("PYTHONPATH", self.input_ports.python.PYTHONPATH)
	self._add_computed_prop("genforma_home", self.input_ports.host.genforma_home)
        self._add_computed_prop("repo", self.config_port.repo)

_config_type = {
    "config_port": {
        "repo": unicode
    },
    "input_ports": {
        "host": { "genforma_home": unicode },
        "python": { "PYTHONPATH": unicode, "home": unicode }
    }
}

class Manager(resource_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
	self.config = metadata.get_config(_config_type, Config, self.id, package_name)
    
    def validate_pre_install(self):
        logger.debug("Gitplugin: validate_pre_install")
        # TODO: should eventually create a separate resource for the repository
        if not os.path.isdir(self.config.repo):
            raise UserError(errors[ERR_GIT_REPO_NOT_FOUND],
                            msg_args={"repo":self.config.repo})

    def is_installed(self):
	pythonpath = self.config.PYTHONPATH
	logger.debug("Python path is " + pythonpath)
        files = os.listdir(pythonpath)
        for f in files:
	   logger.debug("File " + f)
           if re.match("TracGit.*", f) != None:
	        logger.debug("Found the GitPlugin installation")
		return True
	logger.debug("Did not find the GitPlugin installation")
	return False

    def install(self, package):
	logger.debug("Installing GitPlugin")
        #wget http://trac-hacks.org/changeset/latest/gitplugin?old_path=/&amp;filename=gitplugin&amp;format=zip
	extracted_dir = package.extract(self.config.genforma_home)
	logger.debug("Extracted directory is: " + extracted_dir)
	#extract zip file
        #python setup.py install --prefix=pythonpath
        setup_script_dir = iupath.join_list([self.config.genforma_home,
                                             extracted_dir, "0.11"])
        setup_script = os.path.join(setup_script_dir, "setup.py")
        # must run setup from the setup script directory
        rc = iuprocess.run_and_log_program([self.config.input_ports.python.home,
                                            setup_script, "install"], {}, logger,
                                           cwd=setup_script_dir)
        if rc != 0:
            raise UserError(errors[ERR_GITPLUGIN],
                            developer_msg="Python setup failed");
	logger.debug("Done installing GitPlugin")

    def validate_post_install(self):
        logger.debug("Gitplugin: validate_post_install")
        # TODO: should eventually create a separate resource for the repository
        if not os.path.isdir(self.config.repo):
            raise UserError(errors[ERR_GIT_REPO_NOT_FOUND],
                            msg_args={"repo":self.config.repo})


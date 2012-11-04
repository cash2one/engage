"""Resource manager for python. Main purpose of this class
is to check that it is installed correctly.
"""

import commands
import os
import os.path
import copy

import fixup_python_path
import engage.drivers.resource_manager as resource_manager
import engage_utils.process as procutils
import engage.utils.log_setup
from engage.drivers.action import ValueAction

logger = engage.utils.log_setup.setup_script_logger(__name__)

from engage.utils.user_error import UserError, ScriptErrInf
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_INSTALL_NOT_SUPPORTED = 1
ERR_INSTALL_NOT_VALID     = 2
ERR_PYTHON_NOT_FOUND      = 3
ERR_PYTHON_OLD_VERSION    = 4

define_error(ERR_INSTALL_NOT_SUPPORTED,
             _("python installation not currently supported."))
define_error(ERR_INSTALL_NOT_VALID,
             _("python installation invalid: python home %(dir)s does not exist"))
define_error(ERR_PYTHON_NOT_FOUND,
             _("python installation invalid: python executable %(python)s not found or is not runnable"))
define_error(ERR_PYTHON_OLD_VERSION,
             _("python installation invalid: python version %(version) not supported. Need 2.6 or newer"))


def check_if_module_installed(python_exe, module_name, python_path_var=None):
    """Utility function to see if a python module is installed by trying
    to import it.
    """
    env = copy.deepcopy(os.environ)
    if python_path_var:
        env["PYTHONPATH"] = python_path_var
    # to ensure consistent results, we run with a working directory
    # equal to the directory containing the python executable. This
    # ensures that we don't accidentally pick up modules in the current
    # directory.
    cwd = os.path.dirname(python_exe)
    rc = procutils.run_and_log_program([python_exe, "-c", "import %s" % module_name],
                                       env, logger, cwd=cwd)
    if rc==0:
        logger.debug("Python module %s is installed" % module_name)
        return True
    else:
        logger.debug("Python module %s not found" % module_name)
        return False

class is_module_installed(ValueAction):
    """Boolean value action to check if a python module
    is installed.
    """
    NAME="python.is_module_installed"
    def __init__(self, ctx):
        super(is_module_installed, self).__init__(ctx)
        ctx.checkp("input_ports.python.home")

    def run(self, module_name, python_path_var=None):
        return check_if_module_installed(self.ctx.props.input_ports.python.home,
                                         module_name,
                                         python_path_var=python_path_var)

    def dry_run(self, module_name, python_path_var=None):
        return None
    
    
class Manager(resource_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.python_home = self.metadata.config_port["PYTHON_HOME"]
    
    def validate_pre_install(self):
        raise UserError(errors[ERR_INSTALL_NOT_SUPPORTED])

    def install(self):
        raise UserError(errors[ERR_INSTALL_NOT_SUPPORTED])

    def validate_post_install(self):
        logger.info("%s: validate_post_install called"
		    % self.package_name)
        if not os.path.isfile(self.python_home):
            raise UserError(errors[ERR_PYTHON_NOT_FOUND],msg_args={"python":self.python_home})	
  	version = commands.getoutput("%s --version 2>&1 | sed 's/^.*Python //'" % self.python_home)
  	logger.info("%s version is %s" % (self.package_name, version))
        split_version = version.split(".")
        assert(len(split_version) >= 2)
  	major = split_version[0]
	minor = split_version[1]
	if (major < 2 or (major == 2 and minor < 3) or major == 3 ):
		raise UserError(errors[ERR_PYTHON_OLD_VERSION],msg_args={"version":version})

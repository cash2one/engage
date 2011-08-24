"""Resource manager for java virtual machine. Main purpose of this class
is to check whether the JVM is already installed. In addition, it does some
post-install validation.
"""

import engage.drivers.resource_manager as resource_manager
import engage.utils.log_setup

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
ERR_JAVA_NOT_FOUND        = 3

define_error(ERR_INSTALL_NOT_SUPPORTED,
             _("JVM installation not currently supported."))
define_error(ERR_INSTALL_NOT_VALID,
             _("JVM installation invalid: Java home %(dir)s does not exist"))
define_error(ERR_JAVA_NOT_FOUND,
             _("JVM installation invalid: Java executable %(java)s not found or is not runnable"))


logger = engage.utils.log_setup.setup_script_logger(__name__)


class Manager(resource_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.java_home = self.metadata.config_port["JAVA_HOME"]
        self.java_exe = os.path.join(os.path.join(self.java_home, "bin"), "java")


    def is_installed(self):
        if not os.path.isdir(self.java_home):
            logger.debug("JVM not installed")
            return False
        elif not os.access(self.java_exe, os.X_OK):
            logger.warn("JAVA_HOME directory '%s' is present, but java executable is not. Assuming Java not installed." % self.java_home)
            return False
        else:
            logger.debug("Found JAVA_HOME and java executable, assuming installed")
            return True
        
    def validate_pre_install(self):
        raise UserError(errors[ERR_INSTALL_NOT_SUPPORTED])

    def install(self):
        raise UserError(errors[ERR_INSTALL_NOT_SUPPORTED])

    def validate_post_install(self):
        if not os.path.isdir(self.java_home):
            raise UserError(errors[ERR_INSTALL_NOT_VALID],
                            msg_args={"dir": self.java_home})
        if not os.access(self.java_exe, os.X_OK):
            raise UserError(errors[ERR_JAVA_NOT_FOUND],
                            msg_args={"java":self.java_exe})

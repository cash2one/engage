"""Just a subclass of service_manager.Manager for testing --
the methods don't do anything but print to a logfile.
"""

import engage.drivers.resource_manager as resource_manager
import engage.utils.log_setup

logger = engage.utils.log_setup.setup_script_logger("DummyResource")

from engage.utils.user_error import UserError, ScriptErrInf
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("DummyResource", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_ALREADY_INSTALLED = 1

define_error(ERR_ALREADY_INSTALLED,
             _("Package %(pkg): install called when package already installed"))
             

class Manager(resource_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s (dummy_resouce_manager)" % \
            (metadata.key["name"], metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)

    def validate_pre_install(self):
        logger.info("%s: validate_pre_install() called"
                    % self.package_name)

    def install(self, library_package):
        if self.is_installed():
            raise UserError(errors[ERR_ALREADY_INSTALLED],
                            msg_args={"pkg":self.package_name})
        logger.info("%s: install() called" % self.package_name)

    def validate_post_install(self):
        logger.info("%s: validate_post_install() called"
                    % self.package_name)
    

"""Just a subclass of service_manager.Manager for testing --
the methods don't do anything but print to a logfile.
"""

import engage.drivers.service_manager as service_manager

import engage.utils.log_setup

logger = engage.utils.log_setup.setup_script_logger("DummyService")

from engage.utils.user_error import UserError, ScriptErrInf
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("DummyService", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_START_ALREADY_CALLED  = 1
ERR_STOP_NOT_STARTED      = 2
ERR_ALREADY_INSTALLED     = 3

define_error(ERR_START_ALREADY_CALLED,
             _("Package %(pkg)s: start was already called"))
define_error(ERR_STOP_NOT_STARTED,
             _("Package %(pkg)s: attempt to start service that was not started"))
define_error(ERR_ALREADY_INSTALLED,
             _("Package %(pkg)s: install called when package already installed"))


class Manager(service_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s (dummy_service_manager)" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        self.started = False

    def start(self):
        if self.started:
            raise UserError(errors[ERR_START_ALREADY_CALLED],
                            msg_args={"pkg":self.package_name})
        logger.info("%s: start() called" %
                    self.package_name)
        self.started = True
    
    def stop(self):
        if not self.started:
            raise UserError(errors[ERR_STOP_NOT_STARTED],
                            msg_args={"pkg":self.package_name})
        logger.info("%s: stop() called" %
                    self.package_name)
        self.started = False

    def is_running(self):
        return self.started

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
    
    def uninstall(self):
        logger.info("%: uninstall() called" % self.package_name)

"""Resource manager for a preinstalled java virtual machine. Main purpose of this
class is to check whether the JVM is already installed. In addition, it does some
post-install validation.
"""

import os
import os.path

import engage.drivers.resource_manager as resource_manager
from engage.drivers.action import Context
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

def make_context(resource_json, sudo_password_fn, dry_run=False):
    """Create a Context object (defined in engage.utils.action). This contains
    the resource's metadata in ctx.props, references to the logger and sudo
    password function, and various helper functions. The context object is used
    by individual actions.

    If your resource does not need the sudo password, you can just pass in
    None for sudo_password_fn.
    """
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=sudo_password_fn,
                  dry_run=dry_run)
    ctx.check_port('config_port',
                  JAVA_HOME=unicode)
    ctx.check_port('input_ports.host',
                  cpu_arch=unicode,
                  os_type=unicode,
                  hostname=unicode,
                  os_user_name=unicode)
    ctx.check_port('output_ports.jvm',
                  home=unicode,
                  type=unicode)

    ctx.add("java_exe",
            os.path.join(os.path.join(ctx.props.config_port.JAVA_HOME,
                                      "bin"), "java"))
    return ctx


class Manager(resource_manager.Manager):
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(),
                                None,
                                dry_run=dry_run)


    def is_installed(self):
        jh = self.ctx.props.config_port.JAVA_HOME
        if self.ctx.dry_run: return
        if not os.path.isdir(jh):
            logger.debug("JVM not installed")
            return False
        elif not os.access(self.ctx.props.java_exe, os.X_OK):
            logger.warn("JAVA_HOME directory '%s' is present, but java executable is not. Assuming Java not installed." % jh)
            return False
        else:
            logger.debug("Found JAVA_HOME and java executable, assuming installed")
            return True
        
    def validate_pre_install(self):
        if not self.ctx.dry_run:
            raise UserError(errors[ERR_INSTALL_NOT_SUPPORTED])

    def install(self, package):
        if not self.ctx.dry_run:
            raise UserError(errors[ERR_INSTALL_NOT_SUPPORTED])

    def validate_post_install(self):
        jh = self.ctx.props.config_port.JAVA_HOME
        if self.ctx.dry_run: return
        if not os.path.isdir(jh):
            raise UserError(errors[ERR_INSTALL_NOT_VALID],
                            msg_args={"dir": jh})
        if not os.access(self.ctx.props.java_exe, os.X_OK):
            raise UserError(errors[ERR_JAVA_NOT_FOUND],
                            msg_args={"java":self.ctx.props.java_exe})

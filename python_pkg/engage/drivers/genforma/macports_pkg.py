"""macports_pkg-- utility functions to run port (macosx package manager),
along with a generic resource manager for macports packages. All resources
based on this resource manager should have a dependency on the macports
resource.
"""

import os
import os.path
import sys
import re

import fixup_python_path

import engage.drivers.resource_manager as resource_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.drivers.action as action
import engage.utils.process as iuprocess
import engage.utils.log_setup
from engage.utils.regexp import *
from engage.drivers.password_repo_mixin import PasswordRepoMixin
logger = engage.utils.log_setup.setup_script_logger(__name__)

from engage.utils.user_error import ScriptErrInf, UserError, convert_exc_to_user_error

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_MACPORTS_NOT_FOUND        = 1
ERR_MACPORTS_INSTALL          = 2
ERR_MACPORTS_PKG_QUERY        = 3
ERR_POST_INSTALL              = 4
ERR_MACPORTS_LOAD             = 5

define_error(ERR_MACPORTS_NOT_FOUND,
             _("port executable not found at %(path)s"))
define_error(ERR_MACPORTS_INSTALL,
             _("port install failed for packages %(pkg)s in resource %(id)s"))
define_error(ERR_MACPORTS_LOAD,
             _("port load failed for package %(pkg)s in resource %(id)s"))
define_error(ERR_MACPORTS_PKG_QUERY,
             _("'port installed' query for package %(pkg)s failed in resource %(id)s."))
define_error(ERR_POST_INSTALL,
             _("post install validation failed for package %(pkg)s in resource %(id)s"))


DEFAULT_PORT_EXE="/opt/local/bin/port"

class port_install(action.Action):
    NAME="macports_pkg.port_install"
    def __init__(self, ctx):
        super(port_install, self).__init__(ctx)
        ctx.checkp("input_ports.macports.macports_exe")
        
    def run(self, package_list):
        """Install the specified port(s). If you have variants, include them in
        the package list. Expects the context to have an input port "macports"
        with a property "macports_exe".
        """
        port_exe = self.ctx.props.input_ports.macports.macports_exe
        action._check_file_exists(port_exe, self)
        try:
            iuprocess.run_sudo_program([port_exe, "install"]+package_list,
                                       self.ctx._get_sudo_password(self),
                                       self.ctx.logger,
                                       cwd=os.path.dirname(port_exe))
        except iuprocess.SudoError, e:
            exc_info = sys.exc_info()
            self.ctx.logger.exception("Port install for %s failed, unexpected exception" % package_list)
            sys.exc_clear()
            raise convert_exc_to_user_error(exc_info, errors[ERR_MACPORTS_INSTALL],
                                            msg_args={"pkg":package_list.__repr__(),
                                                      "id":self.ctx.props.id},
                                            nested_exc_info=e.get_nested_exc_info())
        
    def dry_run(self, package_list):
        port_exe = self.ctx.props.input_ports.macports.macports_exe
        action._check_file_exists(port_exe, self)
        self.ctx.logger.action("sudo %s" % ([port_exe, "install"]+package_list).__repr__())


class port_load(action.Action):
    NAME="macports_pkg.port_load"
    def __init__(self, ctx):
        super(port_load, self).__init__(ctx)
        ctx.checkp("input_ports.macports.macports_exe")
    
    def run(self, package):
        """Run the load operation on the specified port(s).

        Unfortunately, there's no way to query if a port is already loaded.
        To get already this, we make the operation itempotent: we try the
        port load. If it fails, we scan the results to see if we get the error
        message indicating the port was already loaded. In that case, we ignore
        the error.
        """
        port_exe = self.ctx.props.input_ports.macports.macports_exe
        action._check_file_exists(port_exe, self)
        try:
            re_map = {"already_loaded": concat(lit("Error: Target org.macports.load returned:"),
                                               one_or_more(any_except_newline()),
                                               line_ends_with(lit("Already loaded"))).get_value()}
            (rc, result_map) = \
                 iuprocess.run_sudo_program_and_scan_results([port_exe, "load",
                                                              package],
                                                             re_map, self.ctx.logger,
                                                             self.ctx._get_sudo_password(self),
                                                             log_output=True)
        except iuprocess.SudoError, e:
            self.ctx.logger.exception("Port load for %s failed, unexpected exception" % package)
            exc_info = sys.exc_info()
            sys.exc_clear()
            raise convert_exc_to_user_error(exc_info, errors[ERR_MACPORTS_LOAD],
                                            msg_args={"pkg":package, "id":self.ctx.props.id},
                                            nested_exc_info=e.get_nested_exc_info())

        if rc==0:
            self.ctx.logger.debug("Port load of %s successful" % package)
        elif result_map["already_loaded"]==True:
            self.ctx.logger.debug("Port %s already loaded" % package)
        else:
            self.ctx.logger.debug("port load of %s got an rc of %d" % (package, rc))
            raise UserError(errors[ERR_MACPORTS_LOAD],
                            msg_args={"pkg":package.__repr__(), "id":self.ctx.props.id},
                            developer_msg="rc was %d" % rc)

    def dry_run(self, package):
        port_exe = self.ctx.props.input_ports.macports.macports_exe
        action._check_file_exists(port_exe, self)
        

class is_installed(action.ValueAction):
    NAME="macports_pkg.is_installed"
    def __init__(self, ctx):
        super(is_installed, self).__init__(ctx)
        ctx.checkp("input_ports.macports.macports_exe")
    
    def run(self, package):
        port_exe = self.ctx.props.input_ports.macports.macports_exe
        action._check_file_exists(port_exe, self)
        (rc, map) = iuprocess.run_program_and_scan_results([port_exe, "installed", package],
                                                           {"found": re.escape(package) + ".*" + re.escape("(active)"),
                                                            'not_found': re.escape("None of the specified ports are installed.")},
                                                            self.ctx.logger, log_output=True,
                                                            cwd=os.path.dirname(port_exe))
        if rc==0 and map['found']:
            return True
        elif rc==0 and map['not_found']:
            return False
        else:
            raise UserError(errors[ERR_MACPORTS_PKG_QUERY],
                            msg_args={"pkg":package, "id":self.ctx.props.id})

    def dry_run(self, package):
        port_exe = self.ctx.props.input_ports.macports.macports_exe
        action._check_file_exists(port_exe, self)
        return None

@action.make_action
def check_installed(self, package):
    """Validate that a macports package is installed (e.g. in a post-install check)
    """
    port_exe = self.ctx.props.input_ports.macports.macports_exe
    action._check_file_exists(port_exe, self)
    (rc, map) = iuprocess.run_program_and_scan_results([port_exe, "installed", package],
                                                       {"found": re.escape(package) + ".*" + re.escape("(active)"),
                                                        'not_found': re.escape("None of the specified ports are installed.")},
                                                        self.ctx.logger, log_output=True)
    if rc==0 and map['found']:
        return
    else:
        raise UserError(errors[ERR_POST_INSTALL],
                        msg_args={"pkg":package, "id":self.ctx.props.id})


def make_context(resource_json, sudo_password_fn, dry_run=False):
    ctx = action.Context(resource_json, logger, __file__,
                         sudo_password_fn=sudo_password_fn, dry_run=dry_run)
    ctx.checkp("input_ports.host.sudo_password")
    ctx.checkp("input_ports.macports.macports_exe")
    ctx.checkp("output_ports.port_cfg.package_name")
    return ctx


class Manager(resource_manager.Manager, PasswordRepoMixin):
    REQUIRES_ROOT_ACCESS = True
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(), self._get_sudo_password,
                                dry_run)

    def validate_pre_install(self):
        self.ctx.r(action.check_file_exists,
                   self.ctx.props.input_ports.macports.macports_exe)
    
    def is_installed(self):
        return self.ctx.rv(is_installed,
                           self.ctx.props.output_ports.port_cfg.package_name)

    def install(self, package):
        self.ctx.r(port_install,
                   [self.ctx.props.output_ports.port_cfg.package_name])
        self.validate_post_install()

    def validate_post_install(self):
        if not self.is_installed() and not self.ctx.dry_run:
            raise UserError(errors[ERR_POST_INSTALL],
                            msg_args={"pkg":self.ctx.props.output_ports.port_cfg.package_name,
                                      "id":self.ctx.props.id})

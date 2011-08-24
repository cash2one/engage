"""aptget -- utility functions to run apt-get (ubuntu/debian package manager),
along with a generic resource manager for apt packages"""

import os
import os.path
import sys
import re

import engage.drivers.resource_manager as resource_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.utils.process as iuprocess
import engage.utils.log_setup
from engage.drivers.password_repo_mixin import PasswordRepoMixin
from engage.drivers.action import Action, _check_file_exists, make_value_action, make_action
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
ERR_APT_GET_NOT_FOUND       = 1
ERR_APT_GET_INSTALL         = 2
ERR_DPKG_QUERY_NOT_FOUND    = 3
ERR_INSTALL_PKG_QUERY       = 4
ERR_PKG_NOT_INSTALLED       = 5

define_error(ERR_APT_GET_NOT_FOUND,
             _("apt-get executable not found at %(path)s"))
define_error(ERR_APT_GET_INSTALL,
             _("apt-get install failed for packages %(pkgs)s"))
define_error(ERR_DPKG_QUERY_NOT_FOUND,
             _("dpkg-query executable not found at %(path)s"))
define_error(ERR_INSTALL_PKG_QUERY,
             _("dpkg-query for installed package %(pkg)s failed."))
define_error(ERR_PKG_NOT_INSTALLED,
             _("aptget package %(pkg)s not found after install in resource %(id)s"))


APT_GET_PATH = "/usr/bin/apt-get"
DPKG_QUERY_PATH = "/usr/bin/dpkg-query"

def apt_get_install(package_list, sudo_password):
    if not os.path.exists(APT_GET_PATH):
        raise UserError(errors[ERR_APT_GET_NOT_FOUND],
                        msg_args={"path":APT_GET_PATH})
    
    try:
        iuprocess.run_sudo_program([APT_GET_PATH, "-q", "-y", "update"], sudo_password,
                                   logger)
        iuprocess.run_sudo_program([APT_GET_PATH, "-q", "-y", "install"]+package_list, sudo_password,
                                logger,
                                   env=None)
    except iuprocess.SudoError, e:
        exc_info = sys.exc_info()
        sys.exc_clear()
        raise convert_exc_to_user_error(exc_info, errors[ERR_APT_GET_INSTALL],
                                        msg_args={"pkgs":package_list.__repr__()},
                                        nested_exc_info=e.get_nested_exc_info())

class install(Action):
    """An action to install a list of packages via apt-get"""
    NAME="aptget.install"
    def __init__(self, ctx):
        super(install, self).__init__(ctx)

    def run(self, package_list):
        apt_get_install(package_list, self.ctx._get_sudo_password(self))

    def dry_run(self, package_list):
        _check_file_exists(APT_GET_PATH, self)


def is_installed(package):
    if not os.path.exists(DPKG_QUERY_PATH):
        raise UserError(errors[ERR_DPKG_QUERY_NOT_FOUND],
                        msg_args={"path":DPKG_QUERY_PATH})
    (rc, map) = iuprocess.run_program_and_scan_results([DPKG_QUERY_PATH, "-s", package],
                                                       {"status_ok": "^" + re.escape("Status: install ok installed")},
                                                        logger, log_output=True)
    if rc==0 and map['status_ok']:
        return True
    else:
        return False

@make_value_action
def is_pkg_installed(self, package):
    """Value action to see whether the specified apt package is installed"""
    return is_installed(package)

@make_action
def check_installed(self, package):
    """verify that a aptget package is installed
    """
    if not is_installed(package):
        raise UserError(errors[ERR_PKG_NOT_INSTALLED],
                        msg_args={"pkg":package, "id":self.ctx.props.id})

_config_type = {
    "input_ports": {
      "host": {
          "sudo_password" : unicode
        }
    },
    "output_ports": {
        "apt_cfg": {
            "package_name": unicode
        }
    }
}

class Config(resource_metadata.Config):
    def __init__(self, props_in, types, id, package_name):
        resource_metadata.Config.__init__(self, props_in, types)
        

class Manager(resource_manager.Manager, PasswordRepoMixin):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.config = metadata.get_config(_config_type, Config,
                                          self.id, package_name)

    def validate_pre_install(self):
        if not os.path.exists(APT_GET_PATH):
            raise UserError(errors[ERR_APT_GET_NOT_FOUND],
                            msg_args={"path":APT_GET_PATH})
    
    def is_installed(self):
        return is_installed(self.config.output_ports.apt_cfg.package_name)

    def install(self, package):
        apt_get_install([self.config.output_ports.apt_cfg.package_name],
                         self._get_sudo_password())
        self.validate_post_install()

    def validate_post_install(self):
        if not self.is_installed():
            raise UserError(errors[ERR_INSTALL_PKG_QUERY],
                            msg_args={"pkg":self.config.output_ports.apt_cfg.package_name})

"""aptget -- utility functions to run apt-get (ubuntu/debian package manager),
along with a generic resource manager for apt packages"""

import os
import os.path
import sys
import re
import copy

import engage.drivers.resource_manager as resource_manager
import engage.drivers.resource_metadata as resource_metadata
import engage_utils.process as iuprocess
import engage.utils.log_setup
from engage.drivers.password_repo_mixin import PasswordRepoMixin
from engage.drivers.action import Action, _check_file_exists, make_value_action, make_action
from engage.utils.file import NamedTempFile
import engage_utils.pkgmgr
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
ERR_DPKG_NOT_FOUND          = 6
ERR_PKG_FILE_NOT_FOUND      = 7
ERR_DPKG_INSTALL            = 8

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
define_error(ERR_DPKG_NOT_FOUND,
             _("dpkg executable not found at %(path)s"))
define_error(ERR_PKG_FILE_NOT_FOUND,
             _("package file not found at %(path)s"))
define_error(ERR_DPKG_INSTALL,
             _("dpkg install failed for package file %(path)s"))


APT_GET_PATH = "/usr/bin/apt-get"
DPKG_QUERY_PATH = "/usr/bin/dpkg-query"
DPKG_PATH = "/usr/bin/dpkg"

def _get_env_for_aptget():
    """The apt-get utility may in some cases require that the PATH environment
    variable be set. We take the current environment and then add a resonable
    default path if one is not already present.
    """
    env = copy.deepcopy(os.environ)
    if not env.has_key("PATH"):
        env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    return env

# We track whether this execution of Engage has run the apt-get update command.
# If so, we don't run it for any subsequent requests. The update command is
# slow and frequently fails due to server availability issues.
update_run_this_execution = False

def run_update_if_not_already_run(sudo_password, env):
    global update_run_this_execution
    if not update_run_this_execution:
        logger.info("Running apt-get update...")
        iuprocess.run_sudo_program([APT_GET_PATH, "-q", "-y", "update"], sudo_password,
                                   logger, env=env)
        update_run_this_execution=True

def apt_get_install(package_list, sudo_password):
    env = _get_env_for_aptget()
    if not os.path.exists(APT_GET_PATH):
        raise UserError(errors[ERR_APT_GET_NOT_FOUND],
                        msg_args={"path":APT_GET_PATH})
    
    try:
        run_update_if_not_already_run(sudo_password, env)
        iuprocess.run_sudo_program([APT_GET_PATH, "-q", "-y", "install"]+package_list, sudo_password,
                                   logger,
                                   env=env)
    except iuprocess.SudoError, e:
        exc_info = sys.exc_info()
        sys.exc_clear()
        raise convert_exc_to_user_error(exc_info, errors[ERR_APT_GET_INSTALL],
                                        msg_args={"pkgs":package_list.__repr__()},
                                        nested_exc_info=e.get_nested_exc_info())

def dpkg_install(package_file, sudo_password):
    """Given a package's .deb file, install using dpkg.
    """
    env = _get_env_for_aptget()
    if not os.path.exists(DPKG_PATH):
        raise UserError(errors[ERR_DPKG_NOT_FOUND],
                        msg_args={"path":DPKG_PATH})
    if not os.path.exists(package_file):
        raise UserError(errors[ERR_PKG_FILE_NOT_FOUND],
                        msg_args={"path":package_file})
    
    try:
        run_update_if_not_already_run(sudo_password, env)
        iuprocess.run_sudo_program([DPKG_PATH, "-i", package_file], sudo_password,
                                   logger, env=env)
    except iuprocess.SudoError, e:
        exc_info = sys.exc_info()
        sys.exc_clear()
        raise convert_exc_to_user_error(exc_info, errors[ERR_DPKG_INSTALL],
                                        msg_args={"path":package_file},
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


class debconf_set_selections(Action):
    """Run the debconf-set-selections utility. This can be used to set values
    that normally are prompted interactively from the user in apt-get.
    """
    NAME="aptget.debconf_set_selections"

    def run(self, selection_lines):
        with NamedTempFile(selection_lines) as f:
            iuprocess.run_sudo_program(["/usr/bin/debconf-set-selections",
                                        f.name],
                                       self.ctx._get_sudo_password(self),
                                       self.ctx.logger,
                                       cwd="/usr/bin")
            
    def dry_run(self, selection_lines):
        pass

    def format_action_args(self, selection_lines):
        return "%s <selection_lines>" % self.NAME

@make_action
def update(self, always_run=True):
    """ACTION: Run the apt-get update command to update the list of available
    packages. By default always run the update command, even if it was already
    run, as it is assumed that an explicit call readlly needs the update. This
    is the case for add_apt_repository, where subsequent packages won't
    even be visible.
    """
    global update_run_this_execution
    if always_run or (not update_run_this_execution):
        self.ctx.logger.info("Running apt-get update...")
        iuprocess.run_sudo_program([APT_GET_PATH, "-q", "-y", "update"],
                                   self.ctx._get_sudo_password(self),
                                   self.ctx.logger,
                                   env=_get_env_for_aptget())
        update_run_this_execution = True
    else:
        self.ctx.logger.info("ignoring request for apt-get update, as update was already run")


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

@make_action
def ensure_installed(self, package):
    """An action that checks if a single apt package is installed. If not, it
    performs the install
    """
    if not is_installed(package):
        apt_get_install([package], self.ctx._get_sudo_password(self))
    else:
        self.ctx.logger.debug("Skipping install of package %s - already installed" %
                              package)



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
    REQUIRES_ROOT_ACCESS = True
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
        if isinstance(package, engage_utils.pkgmgr.Package):
            local_repository = self.install_context.engage_file_layout.get_cache_directory()
            package_path = package.download([], local_repository, dry_run=self.ctx.dry_run)
            dpkg_install(package_path, self._get_sudo_password())
        else:
            apt_get_install([self.config.output_ports.apt_cfg.package_name],
                            self._get_sudo_password())
        self.validate_post_install()

    def validate_post_install(self):
        if not self.is_installed():
            raise UserError(errors[ERR_INSTALL_PKG_QUERY],
                            msg_args={"pkg":self.config.output_ports.apt_cfg.package_name})


"""Resource manager for using the add-apt-repository command (part of the
   python-software-properties package).
"""

# Common stdlib imports
import sys
import os
import os.path
## import commands

# fix path if necessary (if running from source or running as test)
try:
    import engage.utils
except:
    sys.exc_clear()
    dir_to_add_to_python_path = os.path.abspath((os.path.join(os.path.dirname(__file__), "../../..")))
    sys.path.append(dir_to_add_to_python_path)

import engage.drivers.resource_manager as resource_manager
import engage.drivers.utils
# Drivers compose *actions* to implement their methods.
from engage.drivers.action import *
from engage.drivers.password_repo_mixin import PasswordRepoMixin
from engage.drivers.genforma.aptget import update
import engage_utils.process as procutils

# setup errors
from engage.utils.user_error import UserError, EngageErrInf
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
# FILL IN
ERR_TBD = 0

define_error(ERR_TBD,
             _("Replace this with your error codes"))


# setup logging
from engage.utils.log_setup import setup_engage_logger
logger = setup_engage_logger(__name__)


# this is used by the package manager to locate the packages.json
# file associated with the driver
def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)

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
    ctx.check_port('input_ports.host',
                  sudo_password=unicode)
    ctx.check_port('input_ports.add_rep_exe_info',
                  add_apt_repository_exe=unicode)
    ctx.check_port('output_ports.repository',
                  repo_name=unicode)

    # add any extra computed properties here using the ctx.add() method.
    return ctx

ADD_APT_REPO_COMMAND="/usr/bin/add-apt-repository"

@make_action
def run_add_apt_repository(self, repository_name):
    procutils.run_sudo_program([ADD_APT_REPO_COMMAND, repository_name],
                               self.ctx._get_sudo_password(self),
                               self.ctx.logger)

#
# Now, define the main resource manager class for the driver.
# If this driver is a service, inherit from service_manager.Manager.
# If the driver is just a resource, it should inherit from
# resource_manager.Manager. If you need the sudo password, add
# PasswordRepoMixin to the inheritance list.
#
class Manager(resource_manager.Manager, PasswordRepoMixin):
    REQUIRES_ROOT_ACCESS = True 
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(),
                                self._get_sudo_password,
                                dry_run=dry_run)
        # TODO: should have a better way to tell if a repository has been added.
        # Should be harmless to add it multiple times.
        self._is_installed = False

    def validate_pre_install(self):
        pass


    def is_installed(self):
        return self._is_installed

    def install(self, package):
        p = self.ctx.props
        r = self.ctx.r
        r(check_file_exists, ADD_APT_REPO_COMMAND)
        r(run_add_apt_repository,
          p.output_ports.repository.repo_name)
        r(update)
        self._is_installed = True


    def validate_post_install(self):
        pass




"""Resource manager for master-password-file 1.0 
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
    dir_to_add_to_python_path = os.path.abspath((os.path.join(os.path.dirname(__file__), "../../../..")))
    sys.path.append(dir_to_add_to_python_path)

import engage.drivers.resource_manager as resource_manager
import engage.drivers.utils
from engage.drivers.password_repo_mixin import PasswordRepoMixin
# Drivers compose *actions* to implement their methods.
from engage.drivers.action import *

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
ERR_NO_MASTER_PW = 1

define_error(ERR_NO_MASTER_PW,
             _("Saving of master password was requested, but no master password needed for this configuration."))


# setup logging
from engage.utils.log_setup import setup_engage_logger
logger = setup_engage_logger(__name__)


# this is used by the package manager to locate the packages.json
# file associated with the driver
def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)

def make_context(resource_json, dry_run=False):
    """Create a Context object (defined in engage.utils.action). This contains
    the resource's metadata in ctx.props, references to the logger and sudo
    password function, and various helper functions. The context object is used
    by individual actions.
    """
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=None,
                  dry_run=dry_run)
    ctx.check_port('config_port',
                  password_file=unicode)
    ctx.check_port('input_ports.host',
                  genforma_home=unicode)

    # add any extra computed properties here using the ctx.add() method.
    return ctx

class write_pw_file(Action):
    NAME = "write_pw_file"
    def __init__(self, ctx):
        super(write_pw_file, self).__init__(ctx)
        
    def run(self, file_path, master_password):
        with open(file_path, "wb") as f:
            f.write(master_password)

    def dry_run(self, file_path, master_password):
        pass

    def format_action_args(self, file_path, master_password):
        return "%s %s *****" % (write_pw_file.NAME, file_path)


class Manager(resource_manager.Manager, PasswordRepoMixin):
    # We force the resource to always require root access and a password file.
    # This is done for situations where resources may be added after the fact
    # (e.g. Datablox), we don't have a good way to add in a password file later.
    REQUIRES_ROOT_ACCESS = True
    REQUIRES_PASSWORD_FILE = True
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(),
                                dry_run=dry_run)

    def validate_pre_install(self):
        pass
        ## p = self.ctx.props
        ## # whether there's a master password is determined by the
        ## # set of resources being installed. Thus, we can check,
        ## # even for dry_run mode.
        ## if self._get_master_password()==None:
        ##     raise UserError(errors[ERR_NO_MASTER_PW])

    def is_installed(self):
        return os.path.exists(self.ctx.props.config_port.password_file)

    def install(self, package):
        p = self.ctx.props
        r = self.ctx.r
        r(write_pw_file, p.config_port.password_file,
          self._get_master_password())
        r(set_file_mode_bits, p.config_port.password_file, 0400)


    def validate_post_install(self):
        p = self.ctx.props
        self.ctx.r(check_file_exists,  p.config_port.password_file)



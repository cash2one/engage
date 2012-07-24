
"""Resource manager for redis-apt 2.4 
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

import engage.drivers.service_manager as service_manager
import engage.drivers.utils
# Drivers compose *actions* to implement their methods.
from engage.drivers.action import *
import engage.drivers.genforma.aptget as aptget


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

    # add any extra computed properties here using the ctx.add() method.
    return ctx

PACKAGE_NAME = "redis-server"
REDIS_PID_FILE = "/var/run/redis.pid"

#
# Now, define the main resource manager class for the driver.
# If this driver is a service, inherit from service_manager.Manager.
# If the driver is just a resource, it should inherit from
# resource_manager.Manager. If you need the sudo password, add
# PasswordRepoMixin to the inheritance list.
#
class Manager(service_manager.Manager, PasswordRepoMixin):
    REQUIRES_ROOT_ACCESS = True 
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(),
                                self._get_sudo_password,
                                dry_run=dry_run)

    def validate_pre_install(self):
        pass


    def is_installed(self):
        return self.ctx.rv(is_pkg_installed, PACKAGE_NAME)

    def install(self, package):
        p = self.ctx.props
        self.ctx.r(ensure_installed, PACKAGE_NAME)


    def validate_post_install(self):
        self.ctx.r(check_installed, PACKAGE_NAME)


    def start(self):
        self.ctx.r(sudo_run_program, ["/etc/init.d/redis-server", "start"])

    def is_running(self):
        return self.ctx.rv_su(get_server_status,
                              REDIS_PID_FILE) != None

    def stop(self):
        self.ctx.r(sudo_run_program, ["/etc/init.d/redis-server", "stop"])


    def get_pid_file_path(self):
        # Method to return the path to the pid file for an installed service.
        # If there is no pid file for this service, just return None. This is
        # used by management tools (e.g. monit) to monitor the service.xs
        return REDIS_PID_FILE


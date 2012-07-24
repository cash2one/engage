
"""Resource manager for redis-macports 2.4 
"""

# Common stdlib imports
import sys
import os
import os.path
import shutil
import re

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
import engage.drivers.genforma.macports_pkg as macports_pkg
from engage.drivers.password_repo_mixin import PasswordRepoMixin

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
    """
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=sudo_password_fn,
                  dry_run=dry_run)
    ctx.check_port("input_ports.host",
                   genforma_home=str,
                   sudo_password=str,
                   log_directory=str)
    ctx.check_port("input_ports.macports",
                   macports_exe=str)
    ctx.check_port("config_port",
                   home=str)
    ctx.add("pid_file", os.path.join(ctx.props.config_port.home, "redis.pid"))
    ctx.add("cfg_file", os.path.join(ctx.props.config_port.home, "redis.conf"))
    ctx.add("log_file", os.path.join(ctx.props.input_ports.host.log_directory, "redis.log"))

    # add any extra computed properties here using the ctx.add() method.
    return ctx


PACKAGE_NAME="redis"
REDIS_EXE="/opt/local/bin/redis-server"
REDIS_ORIG_CFG_FILE="/opt/local/etc/redis.conf"
REDIS_ORIG_PID_FILE="/opt/local/var/run/redis.pid"
REDIS_ORIG_WORKING_DIR="/opt/local/var/db/redis/"

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
        p = self.ctx.props
        return self.ctx.rv(macports_pkg.is_installed, PACKAGE_NAME) and \
               os.path.exists(p.cfg_file)

    def install(self, package):
        p = self.ctx.props
        self.ctx.r(macports_pkg.port_install, [PACKAGE_NAME,])
        self.ctx.r(check_file_exists, REDIS_ORIG_CFG_FILE)
        self.ctx.r(mkdir, p.config_port.home)
        self.ctx.r(copy_file, REDIS_ORIG_CFG_FILE, p.cfg_file)
        pattern_list = [
            (re.escape("dir %s" % REDIS_ORIG_WORKING_DIR),
             "dir %s" % p.config_port.home),
            (re.escape("pidfile %s" % REDIS_ORIG_PID_FILE),
             "pidfile %s" % p.pid_file)
        ]
        substs = self.ctx.r(subst_in_file_and_check_count, p.cfg_file,
                            pattern_list, 2)

    def validate_post_install(self):
        p = self.ctx.props
        self.ctx.r(macports_pkg.check_installed, PACKAGE_NAME)
        self.ctx.r(check_file_exists, p.cfg_file)

    def start(self):
        p = self.ctx.props
        self.ctx.r(start_server, [REDIS_EXE, p.cfg_file],
                   p.log_file, p.pid_file)

    def is_running(self):
        p = self.ctx.props
        return self.ctx.rv(get_server_status,
                           p.pid_file) != None

    def stop(self):
        p = self.ctx.props
        self.ctx.r(stop_server, p.pid_file)

    def get_pid_file_path(self):
        return self.ctx.props.pid_file


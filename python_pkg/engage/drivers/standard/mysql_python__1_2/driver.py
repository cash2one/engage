
"""Resource manager for mysql-python 1.2 
"""

# Common stdlib imports
import sys
import os
import os.path
import copy

# fix path if necessary (if running from source or running as test)
try:
    import engage.utils
except:
    sys.exc_clear()
    dir_to_add_to_python_path = os.path.abspath((os.path.join(os.path.dirname(__file__), "../../../..")))
    sys.path.append(dir_to_add_to_python_path)

import engage.drivers.resource_manager as resource_manager
import engage.drivers.utils
# Drivers compose *actions* to implement their methods.
from engage.drivers.action import *

import engage.drivers.genforma.easy_install as easy_install

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
ERR_MYSQL_CONFIG_EXE = 1

define_error(ERR_MYSQL_CONFIG_EXE,
             _("Resource definition error in resource %(id)s: mysql_config executable must be named 'mysql_config', actual name was '%(exe)s'"))


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
    ctx.checkp("input_ports.setuptools.easy_install") # path to executable
    ctx.checkp("input_ports.python.home")
    ctx.checkp("output_ports.pkg_info.test_module")
    ctx.checkp("input_ports.mysql_admin.mysql_config_exe")
    p = ctx.props
    mysql_config = p.input_ports.mysql_admin.mysql_config_exe
    # The setup.py file for mysql-python has the name of mysql_config
    # hard-coded.
    if os.path.basename(mysql_config)!="mysql_config":
        raise UserError(errors[ERR_MYSQL_CONFIG_EXE],
                        msg_args={"id":p.id, "exe":os.path.basename(mysql_config)})
    # we don't use prefix_dir or script_dir
    ctx.add("prefix_dir", None)
    ctx.add("script_dir", None)
    # To tell whether the package is installed, we need to know the python
    # executable and a test module to try to import.
    ctx.add("python_exe", p.input_ports.python.home)
    ctx.add("test_module", p.output_ports.pkg_info.test_module)
    return ctx


# We get most of the methods from easy_install, but need to handling setting
# the path before running the install_package action
class Manager(easy_install.Manager):
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        # note that we don't run the __init__ function for easy_install,
        # as we want to create our own context here.
        self.ctx = make_context(metadata.to_json(),
                                None,
                                dry_run=dry_run)

    def install(self, package):
        p = self.ctx.props
        # we first need to add the directory containing mysql_config to the
        # path or else setup.py will fail.
        mysql_config_dir = \
            os.path.dirname(p.input_ports.mysql_admin.mysql_config_exe)
        env = copy.deepcopy(os.environ)
        if env.has_key('PATH'):
            env['PATH'] = env['PATH'] + ":" + mysql_config_dir
        else:
            env['PATH'] = mysql_config_dir
        self.ctx.r(easy_install.install_package, package, env_mapping=env)

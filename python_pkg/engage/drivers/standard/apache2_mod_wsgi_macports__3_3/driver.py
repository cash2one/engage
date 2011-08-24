
"""Resource manager for apache-mod-wsgi-macports 3.3.
This version of mod_wsgi is just a package under macports. However,
we need to pick the correct variant to match the version of python we
are using. In addition, we create a new config file mod_wsgi.conf in the
module config directory that contains the LoadModule line to load the
shared library.
"""

# Common stdlib imports
import sys
import os
import os.path

# fix path if necessary (if running from source or running as test)
try:
    import engage.utils
except:
    sys.exc_clear()
    dir_to_add_to_python_path = os.path.abspath((os.path.join(os.path.dirname(__file__), "../../../..")))
    sys.path.append(dir_to_add_to_python_path)

import engage.drivers.resource_manager as resource_manager
import engage.drivers.utils
from engage.drivers.action import Context
from engage.drivers.genforma.macports_pkg import port_install, is_installed
from engage.drivers.genforma.apache_utils import apache_is_running, restart_apache, \
                                                 add_apache_config_file
from engage.utils.cfg_file import is_config_line_present
from engage.drivers.password_repo_mixin import PasswordRepoMixin
import engage.utils.file as fileutils

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
ERR_INSTALL_PKG_QUERY          = 1
ERR_UNSUPPORTED_PYTHON_VERSION = 2

define_error(ERR_INSTALL_PKG_QUERY,
             _("After installing MacPorts package %(pkg)s, query did not find that package was installed"))
define_error(ERR_UNSUPPORTED_PYTHON_VERSION,
             _("Unsupported python version %(pyver)s, expecting one of %(supported_vers)s"))


# setup logging
from engage.utils.log_setup import setup_engage_logger
logger = setup_engage_logger(__name__)


# this is used by the package manager to locate the packages.json
# file associated with the driver
def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)

PORTS_PACKAGE_NAME = "mod_wsgi"
APACHE_CONFIG_LINE = "LoadModule wsgi_module modules/mod_wsgi.so"

# mapping from python version to the associated python variant
variants = {
    "2.5":"+python25",
    "2.6":"+python26",
    "2.7":"+python27"
}

def make_context(resource_json, sudo_password_fn, dry_run=False):
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=sudo_password_fn,
                  dry_run=dry_run)
    ctx.checkp("input_ports.macports.macports_exe")
    ctx.checkp("input_ports.python.version")
    ctx.check_port("input_ports.apache",
                   config_file=str,
                   module_config_dir=str,
                   controller_exe=str)
    python_version = ctx.props.input_ports.python.version
    if python_version not in variants.keys():
        raise UserError(errors[ERR_UNSUPPORTED_PYTHON_VERSION],
                        msg_args={"pyver":python_version,
                                  "supported_vers":variants.keys().__repr__()})
    ctx.add("variant", variants[python_version])
    ctx.add("mod_wsgi_cfg_file",
            os.path.join(ctx.props.input_ports.apache.module_config_dir, "mod_wsgi.conf"))
    return ctx


class Manager(resource_manager.Manager, PasswordRepoMixin):
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(),
                                sudo_password_fn=self._get_sudo_password,
                                dry_run=dry_run)

    def validate_pre_install(self):
        pass

    def is_installed(self):
        rv = self.ctx.rv
        p = self.ctx.props
        if not rv(is_installed, PORTS_PACKAGE_NAME):
            return False
        elif not os.path.exists(p.mod_wsgi_cfg_file):
            return False
        elif not is_config_line_present(p.mod_wsgi_cfg_file,
                                        APACHE_CONFIG_LINE):
            return False
        else:
            return True
                                      
    def install(self, package):
        r = self.ctx.r
        rv = self.ctx.rv
        p = self.ctx.props
        r(port_install, [PORTS_PACKAGE_NAME, p.variant])
        # create the new configuration file
        apache_config = p.input_ports.apache
        with fileutils.NamedTempFile(data=APACHE_CONFIG_LINE+"\n") as f:
            r(add_apache_config_file, f.name, apache_config,
                       new_name="mod_wsgi.conf")
        if rv(apache_is_running, apache_config, timeout_tries=2):
            logger.info("%s: restarting apache after updating config file" %
                        p.id)
            r(restart_apache, apache_config)
    
    def validate_post_install(self):
        if not self.is_installed() and not self.ctx.dry_run:
            raise UserError(errors[ERR_INSTALL_PKG_QUERY],
                            msg_args={"pkg":PORTS_PACKAGE_NAME})



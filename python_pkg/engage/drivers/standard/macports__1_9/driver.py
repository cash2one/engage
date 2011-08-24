
"""Resource manager for macports 1.9

This is the driver for the macports software itself (http://www.macports.org/),
not for individual ports. We currently don't support installing macports itself,
it must be preinstalled by the developer. This resource manager just acts as a
check that macports is installed. To build drivers which install macports packages,
see engage.drivers.genforma.macports_pkg.
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
ERR_MACPORTS_NOT_INSTALLED = 1

define_error(ERR_MACPORTS_NOT_INSTALLED,
             _("MacPorts (http://www.macports.org) is not installed on this machine. Please install MacPorts manually and rerun this install."))


# setup logging
from engage.utils.log_setup import setup_engage_logger
logger = setup_engage_logger(__name__)


# this is used by the package manager to locate the packages.json
# file associated with the driver
def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)

class Manager(resource_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.macports_exe = self.metadata.output_ports['macports']['macports_exe']

    def validate_pre_install(self):
        pass


    def is_installed(self):
        return os.path.exists(self.macports_exe)

    def install(self, package):
        if not os.path.exists(self.macports_exe):
            raise UserError(errors[ERR_MACPORTS_NOT_INSTALLED],
                            developer_msg="Looked for port executable at %s" % self.macports_exe)

    def validate_post_install(self):
        assert self.is_installed()



"""Resource manager for java-virtual-machine-linux 1.6

This just inherits from the jvm_preinstalled driver.
"""


import sys
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
import engage.drivers.genforma.jvm_preinstalled as jvm_preinstalled
import engage.drivers.genforma.aptget as aptget
from engage.utils.system_info import get_platform
from engage.utils.user_error import UserError


# this is used by the package manager to locate the packages.json
# file associated with the driver
def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)

JVM_APT_PACKAGE = "default-jre-headless"

def check_linux_java_1_6_installed():
    """Function for resource in discovery mechanism in preprocess_resources.py.
    """
    if get_platform()!="linux64":
        return False # this resource only valid for ubuntu
    return aptget.is_installed(JVM_APT_PACKAGE)


class Manager(jvm_preinstalled.Manager):
    REQUIRES_ROOT_ACCESS = True
    def __init__(self, metadata, dry_run=False):
        jvm_preinstalled.Manager.__init__(self, metadata,
                                          dry_run=dry_run)

    def validate_pre_install(self):
        pass

    def is_installed(self):
        return check_linux_java_1_6_installed()

    def install(self, package):
        self.ctx.r(aptget.install, [JVM_APT_PACKAGE,])

    def validate_post_install(self):
        if not os.access(self.ctx.props.output_ports.jvm.java_exe, os.X_OK):
            raise UserError(jvm_preinstalled.errors[jvm_preinstalled.ERR_JAVA_NOT_FOUND],
                            msg_args={"java":self.ctx.props.output_ports.jvm.java_exe})

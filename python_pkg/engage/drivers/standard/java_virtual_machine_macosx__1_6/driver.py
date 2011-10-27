
"""Resource manager for java-virtual-machine-macosx 1.6

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

# this is used by the package manager to locate the packages.json
# file associated with the driver
def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)


class Manager(jvm_preinstalled.Manager):
    def __init__(self, metadata, dry_run=False):
        jvm_preinstalled.Manager.__init__(self, metadata,
                                          dry_run=dry_run)

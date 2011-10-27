"""Resource manager for sqlite3-connector for django. 
"""

import os.path

import commands
import engage.drivers.resource_manager as resource_manager
from engage.drivers.backup_file_resource_mixin import BackupFileMixin
import engage.drivers.utils
import engage.utils.backup as backup
import engage.utils.log_setup

from engage.utils.user_error import UserError, EngageErrInf
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EnageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
# no errors yet

def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)


logger = engage.utils.log_setup.setup_engage_logger(__name__)

class Manager(BackupFileMixin, resource_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)

    def _get_backup_file_list(self):
        return [os.path.dirname(self.metadata.config_port['database_file_name']),]
    
    def validate_pre_install(self):
        pass

    def is_installed(self):
        # the actual file is created via the django driver
	return True

    def install(self, download_url):
        pass

    def validate_post_install(self):
        pass

    def upgrade(self, package, old_metadata, backup_root_directory):
        """For the upgrade of a django sqlite database, we restore the previous version
        and let the django app resource manager handle the schema upgrade (if needed).
        """
        backup_file = self._find_backup_archive(backup_root_directory, old_metadata.id)
        logger.info("Upgrading %s by restoring file at %s" % (self.id, backup_file))
        backup.restore(backup_file, move=False)

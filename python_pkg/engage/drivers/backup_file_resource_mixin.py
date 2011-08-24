import os
import os.path
import sys

import resource_metadata
import engage.utils.backup as backup
from engage.utils.log_setup import setup_engage_logger
from password_repo_mixin import PasswordRepoMixin
from engage.utils.decorators import require_methods
logger = setup_engage_logger(__name__)

from engage.utils.user_error import UserError, EngageErrInf, convert_exc_to_user_error

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
BACKUP_FILE_NOT_FOUND_ERROR = 1
EXC_IN_BACKUP_CALL          = 2
EXC_IN_RESTORE_CALL         = 3
ERR_BACKUP_FILE_LIST_EMPTY  = 4

define_error(BACKUP_FILE_NOT_FOUND_ERROR,
             _("Unable to find backup file for resource '%(id)s', tried '%(file)s' and '%(compressed_file)s'"))
define_error(EXC_IN_BACKUP_CALL,
             _("An exception was thrown during backup of resource '%(id)s' to %(file)s: %(exc_typ)s(%(exc_val)s"))
define_error(EXC_IN_RESTORE_CALL,
             _("An exception was thrown during restore of resource '%(id)s' from %(file)s: %(exc_typ)s(%(exc_val)s"))
define_error(ERR_BACKUP_FILE_LIST_EMPTY,
             _("Resource '%s(id)s' returned an empty list of backup files"))


@require_methods("_get_backup_file_list", "_get_sudo_password")
class BackupFileMixin(PasswordRepoMixin):
    """This is a mixin class for resource managers which implements
    the resource's backup and restore methods by getting a list of
    files from the subclass and calling the appropriate functions
    in engage.utils.back.

    Note that you MUST include this class AHEAD of the base resource_manager.Manager
    class in your subclasses inheritance list. Otherwise, the backup() and restore()
    methods won't be overridden.
    
    This mixin requires the following members be present on the subclass:
      self._get_backup_file_list() - returns a list of files and directories
                                     to be backed up.
      self.install_context         - used to get the sudo password
      self.id                      - resource id, used to create unique package names
      self.package_name            - package name of the resource (for log messages)
    """
    def _get_backup_location(self, backup_to_directory, resource_id, compress=True):
        if compress:
            backup_archive = "%s.tar.gz" % resource_id.replace("/", "_")
        else:
            backup_archive = "%s.tar" % resource_id.replace("/", "_")
        return os.path.join(backup_to_directory, backup_archive)

    def _find_backup_file(self, backup_to_directory, resource_id=None):
        # look for the backup file. first, we try to find an uncompressed version.
        if not resource_id:
            resource_id = self.id
        backup_location = self._get_backup_location(backup_to_directory, resource_id, compress=False)
        if not os.path.exists(backup_location):
            compressed_backup_location = self._get_backup_location(backup_to_directory, resource_id, compress=True)
            if not os.path.exists(backup_location):
                raise UserError(errors[BACKUP_FILE_NOT_FOUND_ERROR],
                                msg_args={"id":self.id, "file":backup_location,
                                          "compressed_file":compressed_backup_location})
            backup_location = compressed_backup_location
        return backup_location
        
    def _backup(self, backup_to_directory, is_uninstall, is_incomplete_install, compress=True):
        backup_location = self._get_backup_location(backup_to_directory, self.id, compress)
        logger.debug("Saving resource %s files to %s" % (self.id, backup_location))
        files = self._get_backup_file_list()
        if len(files)==0:
            raise UserError(errors[ERR_BACKUP_FILE_LIST_EMPTY],
                            msg_args={"id": self.id})
        if is_incomplete_install:
            # if the install was incomplete, we look through the file
            # list and only try to backup the files actually present
            candidate_files = files
            files = []
            for file in candidate_files:
                if os.path.exists(file):
                    files.append(file)
                else:
                    logger.debug("Incomplete install of %s: %s missing" % (self.id, file))
            if len(files)==0:
                logger.debug("Incomplete install: nothing to install for %s" % self.id)
                return
        try:
            if os.geteuid()!=0 and backup.check_if_save_requires_superuser(files):
                logger.info("Running backup via sudo for resource %s" % self.id)
                backup.save_as_sudo_subprocess(files, backup_location, self._get_sudo_password(), move=is_uninstall)
            else:
                backup.save(files, backup_location, move=is_uninstall)
        except:
            exc_info = (exc_tp, exc_v, ecx_tb) =  sys.exc_info()
            raise convert_exc_to_user_error(exc_info, errors[EXC_IN_BACKUP_CALL],
                                            msg_args={"id":self.id, "file":backup_location,
                                                      "exc_typ":exc_tp.__name__, "exc_val":exc_v})

    def uninstall(self, backup_to_directory, incomplete_install=False, compress=True):
        self._backup(backup_to_directory, True, incomplete_install, compress)

    def backup(self, backup_to_directory, compress=True):
        self._backup(backup_to_directory, False, False, compress=compress)
        
    def restore(self, backup_to_directory, package):
        backup_location = self._find_backup_file(backup_to_directory)
        try:
            logger.debug("Restoring resource %s from %s" % (self.id, backup_location))
            if os.geteuid()!=0 and backup.check_if_restore_requires_superuser(backup_location):
                logger.info("Running restore via sudo for resource %s" % self.id)
                backup.restore_as_sudo_subprocess(backup_location, self._get_sudo_password(), move=False)
            else:
                backup.restore(backup_location, move=False)
        except:
            exc_info = (exc_tp, exc_v, ecx_tb) = sys.exc_info()
            raise convert_exc_to_user_error(exc_info, errors[EXC_IN_RESTORE_CALL],
                                            msg_args={"id":self.id, "file":backup_location,
                                                      "exc_typ":exc_tp.__name__, "exc_val":exc_v})
        

"""Resource manager to just copy a file
"""
import sys
import os
import os.path
import shutil

import engage.drivers.resource_manager as resource_manager
import engage.utils.log_setup
import engage.utils.file
from engage.drivers.backup_file_resource_mixin import BackupFileMixin

from engage.utils.user_error import UserError, EngageErrInf, convert_exc_to_user_error
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_INSTALL_COPY_ERROR    = 1
ERR_INSTALL_NOT_VALID     = 2
ERR_INSTALL_PERMSET_ERROR = 3

define_error(ERR_INSTALL_COPY_ERROR,
             _("An error occurred during the copying of file '%(file)s'"))
define_error(ERR_INSTALL_PERMSET_ERROR,
             _("An error occurred adjusting the permissions and group of file '%(file)s', target group was '%(group)s'"))
define_error(ERR_INSTALL_NOT_VALID,
             _("File installation invalid: file %(file)s does not exist"))


logger = engage.utils.log_setup.setup_engage_logger(__name__)


class Manager(BackupFileMixin, resource_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.file_path = self.metadata.output_ports["file_info"]["file_path"]
        # the file group is optional. If not None, then we attempt to set the group
        # id of the file to the specified group and add group read (and potentially execute)
        # permissions.
        if self.metadata.output_ports["file_info"].has_key("file_group"):
            self.file_group = self.metadata.output_ports["file_info"]["file_group"]
        else:
            self.file_group = None
        self.ran_install = False

    def _get_backup_file_list(self):
        return [self.file_path]
    
    def is_installed(self):
        if not os.path.exists(self.file_path):
            return False
        else:
            # TODO: Need to validate checksum of file. To enable that, we'd have
            # to get the checksum from the package manager or put it in the
            # resource definition. For now, we hack around this issue by saying
            # that the file is only installed if we ran the install in the same
            # session.
            return self.ran_install
        
    def validate_pre_install(self):
        pass

    def install(self, package):
        source_path = package.get_file()
        target_dirname = os.path.dirname(self.file_path)
        try:
            if not os.path.exists(target_dirname):
                logger.action("mkdir -p %s" % target_dirname)
                os.makedirs(target_dirname)
                if self.file_group:
                    engage.utils.file.set_shared_file_group_and_permissions(target_dirname, self.file_group, logger)
            logger.action("cp %s %s" % (source_path, self.file_path))
            shutil.copy(source_path, self.file_path)
        except:
            logger.exception("File copy for %s failed" % package.get_file())
            error = convert_exc_to_user_error(sys.exc_info(),
                                              errors[ERR_INSTALL_COPY_ERROR],
                                              msg_args={"file":self.file_path})
            raise error
        if self.file_group:
            try:
                engage.utils.file.set_shared_file_group_and_permissions(self.file_path, self.file_group, logger)
            except:
                error = convert_exc_to_user_error(sys.exc_info(),
                                                  errors[ERR_INSTALL_PERMSET_ERROR],
                                                  msg_args={"file":self.file_path, "group":self.file_group})
                raise error
        self.ran_install = True
        self.validate_post_install()
            
    def validate_post_install(self):
        if not os.path.exists(self.file_path):
            raise UserError(errors[ERR_INSTALL_NOT_VALID],
                            msg_args={"file": self.file_path})

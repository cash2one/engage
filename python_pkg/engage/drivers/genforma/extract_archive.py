"""Resource manager to extract an archive to the specified location
"""
import sys
import os
import os.path
import shutil

import engage.drivers.resource_manager as resource_manager
import engage.utils.log_setup
import engage.utils.file

from engage.utils.user_error import UserError, EngageErrInf, convert_exc_to_user_error
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_EXTRACT_ERROR    = 1
ERR_INSTALL_NOT_VALID     = 2
ERR_PERMSET_ERROR = 3

define_error(ERR_EXTRACT_ERROR,
             _("An error occurred during the extraction of '%(archive)s' to '%(dir)s'"))
define_error(ERR_PERMSET_ERROR,
             _("An error occurred recursively adjusting the permissions and group of directory '%(dir)s', target group was '%(group)s'"))
define_error(ERR_INSTALL_NOT_VALID,
             _("Installation of archive invalid: directory %(dir)s does not exist"))


logger = engage.utils.log_setup.setup_engage_logger(__name__)


class Manager(resource_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.extract_path = os.path.abspath(os.path.expanduser(self.metadata.output_ports["archive_info"]["extract_path"]))
        # the archive group is optional. If not None, then we attempt to set the group
        # id of the extracted archive to the specified group and add group read (and potentially execute)
        # permissions.
        if self.metadata.output_ports["archive_info"].has_key("group"):
            self.group = self.metadata.output_ports["archive_info"]["group"]
        else:
            self.group = None
        self.ran_install = False

    def is_installed(self):
        if not os.path.exists(self.extract_path):
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
        target_dirname = os.path.dirname(self.extract_path)
        try:
            extract_parent_dir = os.path.dirname(self.extract_path)
            extract_dirname = os.path.basename(self.extract_path)
            if not os.path.exists(extract_parent_dir):
                logger.action("mkdir -p %s" % extract_parent_dir)
                os.makedirs(extract_parent_dir)
            elif os.path.exists(self.extract_path):
                # old version present, remove it
                logger.action("rm -rf %s" % self.extract_path)
                shutil.rmtree(self.extract_path)
            package.extract(extract_parent_dir, extract_dirname)
        except:
            logger.exception("Extract for %s failed" % package.get_file())
            error = convert_exc_to_user_error(sys.exc_info(),
                                              errors[ERR_EXTRACT_ERROR],
                                              msg_args={"archive":package.get_file(),
                                                        "dir":self.extract_path})
            raise error
        try:
            if self.group:
                engage.utils.file.set_shared_directory_group_and_permissions(self.extract_path, self.group, logger)
        except:
            logger.exception("Recursive permission set for %s failed" % self.extract_path)
            error = convert_exc_to_user_error(sys.exc_info(),
                                              errors[ERR_PERMSET_ERROR],
                                              msg_args={"dir":self.extract_path, "group":self.group})
            raise error
        self.ran_install = True
        self.validate_post_install()
            
    def validate_post_install(self):
        if not os.path.isdir(self.extract_path):
            raise UserError(errors[ERR_INSTALL_NOT_VALID],
                            msg_args={"dir": self.extract_path})

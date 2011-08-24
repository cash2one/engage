"""
Resource manager for resources which can be targets of an overall install.
This is usually representing a physical machine. It could also be a virtual
machine or a subdirectory within a given machine.
"""
import os.path
import shutil
import json

import resource_manager
from engage.utils.log_setup import setup_engine_logger

from engage.utils.user_error import InstErrInf, UserError

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = InstErrInf("InstallTargetResource", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_RESOURCE_DB_ALREADY_EXISTS   = 1

define_error(ERR_RESOURCE_DB_ALREADY_EXISTS,
             _("Installed resource database file '%(file)s' already exists. Are you overwriting an existing install?"))


logger = setup_engine_logger(__name__)


class InstallNotSupported(Exception):
    def __init__(self, resource_mgr):
        Exception.__init__(self, "Installation not supported for %s.%s" %
                           (resource_mgr.__module__,
                            resource_mgr.__class__.__name__))


class InstallTargetConfigError(Exception):
    def __init__(self, resource_mgr, msg):
        Exception.__init__(self, "Configuration error in %s.%s: %s" %
                           (resource_mgr.__module__,
                            resource_mgr.__class__.__name__,
                            msg))

HOST_PORT = u"host"
GENFORMA_HOME = u"genforma_home"
USE_AS_INSTALL_TARGET = u"use_as_install_target"
RESOURCE_FILENAME = "installed_resources.json"


def write_resources_to_file(mgr_list, filename):
    resources = [mgr.metadata.to_json() for mgr in mgr_list]
    file = open(filename, "wb")
    json.dump(resources, file, sort_keys=True, indent=2)
    file.close()


class Manager(resource_manager.Manager):
    def __init__(self, metadata):
        """We validate that the install target resource's definition
        has a "host" output port with a "genforma_home" property.
        Also, the properties of the resource instance are checked to see
        if "use_as_install_target" is true.
        """
        package_name = "%s %s (install_target_resource)" % \
            (metadata.key["name"], metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        if not metadata.is_installed():
            raise InstallNotSupported(self)
        if not metadata.output_ports.has_key(HOST_PORT):
            raise InstallTargetConfigError(self,
                                           "Resource '%s' missing '%s' output port" %
                                           (package_name, HOST_PORT))
        host_port = metadata.output_ports[HOST_PORT]
        if not host_port.has_key(GENFORMA_HOME):
            raise InstallTargetConfigError(self,
                                           "Resource '%s' output port '%s' missing property '%s'" %
                                           (package_name, HOST_PORT, GENFORMA_HOME))
        self.genforma_home = host_port[GENFORMA_HOME]
        if metadata.properties.has_key(USE_AS_INSTALL_TARGET) and \
           metadata.properties[USE_AS_INSTALL_TARGET]:
            self.use_as_install_target_prop = True
        else:
            self.use_as_install_target_prop = False

    def can_be_install_target(self):
        return True

    def use_as_install_target(self):
        """Return true if we should use this resource as THE install target.
        Only one resource per install should return true (until we support
        multi-machine installs).
        """
        return self.use_as_install_target_prop

    def get_genforma_home(self):
        """Return the genforma_home directory.
        """
        return self.genforma_home

    def _get_target_config_dir(self):
        """Return the directory that will contain configuration data
        (the installed resource database and password database).
        """
        return os.path.join(self.genforma_home, "config")

    def _get_resource_db_filename(self):
        """Return the full path for the resource database file.
        """
        return os.path.join(self._get_target_config_dir(),
                            RESOURCE_FILENAME)

    ## We no longer need to move the passowrd db and salt files, as
    ## they are created in the <deployment_home>/config directory
    ## def move_config_data_to_target(self, mgr_list):
    ##     """Move the installed resource db and password db from the installer
    ##     to the target configuration directory.
    ##     """
    ##     target_config_dir = self._get_target_config_dir()
    ##     if not os.path.exists(target_config_dir):
    ##         logger.action("mkdir -p %s" % target_config_dir)
    ##         os.makedirs(target_config_dir)
    ##     logger.action("Write out installed resources database file '%s'" %\
    ##                   self._get_resource_db_filename())
    ##     write_resources_to_file(mgr_list, self._get_resource_db_filename())
    ##     if self.install_context.cipher_file != None:
    ##         # if there is a password database, copy it to the config dir
    ##         logger.action("cp %s %s" % (self.install_context.cipher_file,
    ##                                     target_config_dir))
    ##         shutil.copy(self.install_context.cipher_file, target_config_dir)
    ##         logger.action("cp %s %s" % (self.install_context.salt_file,
    ##                                     target_config_dir))
    ##         shutil.copy(self.install_context.salt_file, target_config_dir)

    def write_resources_to_file(self, mgr_list):
        write_resources_to_file(mgr_list, self._get_resource_db_filename())
        
    def validate_pre_install(self):
        pass

    def install(self, library_package):
        raise InstallNotSupported(self)

    def validate_post_install(self):
        """We check that an install resource database does not already exist.
        """
        if self.use_as_install_target():
            resource_path = self._get_resource_db_filename()
            if os.path.exists(resource_path):
                raise UserError(errors[ERR_RESOURCE_DB_ALREADY_EXISTS],
                                {"file":resource_path})

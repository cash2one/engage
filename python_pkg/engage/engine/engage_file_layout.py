import os
import os.path
import sys
import unittest

# fix path if necessary (if running from source or running as test)
try:
    import engage.utils
except:
    dir_to_add_to_python_path = os.path.abspath(os.path.expanduser(os.path.join(os.path.dirname(__file__), "../..")))
    if not (dir_to_add_to_python_path in sys.path):
        sys.path.append(dir_to_add_to_python_path)


import engage.utils.system_info
from engage.extensions import installed_extensions
from engage.utils.user_error import UserError, InstErrInf

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = InstErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
FILE_NOT_FOUND_ERROR = 1
DIR_NOT_FOUND_ERROR  = 2
INSTALLER_NOT_FOUND  = 3
ERR_UNKNOWN_LAYOUT   = 4

define_error(FILE_NOT_FOUND_ERROR,
             _("Unable to find file '%(filename)s'. Your engage environment may be set up incorrectly."))
define_error(DIR_NOT_FOUND_ERROR,
             _("Unable to find directory '%(dir)s'. Your engage environment may be set up incorrectly."))
define_error(INSTALLER_NOT_FOUND,
             _("No installer for '%(name)s' was found. Valid installers are %(installers)s"))
define_error(ERR_UNKNOWN_LAYOUT,
             _("Unable to determine Engage file layout, running engage.engine package from '%(dir)s'"))


if __name__ == '__main__': # setup logging for tests
    import logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(name)s %(levelname)s %(message)s')
    logger = logging.getLogger(__name__)
else: # setup logging for running as part of installer
    from engage.utils.log_setup import setup_engine_logger
    logger = setup_engine_logger(__name__)


class NotImplementedError(Exception):
    pass

def _find_list_of_installers(metadata_dir):
    """Helper to find the set of installers in a
    deployment home
    """
    installers = []
    for d in os.listdir(metadata_dir):
        p = os.path.join(metadata_dir, d)
        if os.path.isdir(p) and \
           os.path.exists(os.path.join(p, "installer_config.json")):
            installers.append(d)
    return installers


class BaseFileLayout(object):
    """Base class for caching file layout information
    """
    def __init__(self, installer_name=None):
        self.installer_name = installer_name
        self.configurator_exe = None
        self.metadata_directory = None
        self.installer_metadata_directory = None
        self.installer_config_file = None
        self.installer_config = None
        self.resource_def_file = None
        self.software_library_file = None
        self.install_script_file = None
        self.cache_directory = None
        self.deployment_config_directory = None
        self.log_directory = None
        self.password_database_file = None
        self.password_salt_file = None

    def _check_for_directory(self, dirname):
        if not os.path.isdir(dirname):
            raise UserError(errors[DIR_NOT_FOUND_ERROR],
                            msg_args={"dir":dirname},
                            developer_msg="File layout is %s" % self.LAYOUT_TYPE)

    def _check_for_file(self, filename):
        if not os.path.exists(filename):
            raise UserError(errors[FILE_NOT_FOUND_ERROR],
                            msg_args={"filename":filename},
                            developer_msg="File layout is %s" % self.LAYOUT_TYPE)

    def _get_installer_metadata_directory(self):
        assert self.installer_name
        if not self.installer_metadata_directory:
            metadata_dir = self._get_metadata_directory()
            self.installer_metadata_directory = os.path.join(metadata_dir,
                                                             self.installer_name)
            # if we cannot find the installer, we provide a useful error
            # message to the user
            if not os.path.isdir(self.installer_metadata_directory):
                raise UserError(errors[INSTALLER_NOT_FOUND],
                                msg_args={"name":self.installer_name,
                                          "installers":', '.join(_find_list_of_installers(metadata_dir))})
        return self.installer_metadata_directory

    def _get_installer_config_file(self):
        assert self.installer_name, "Install name must be specified"
        if not self.installer_config_file:
            self.installer_config_file = os.path.join(self._get_installer_metadata_directory(),
                                                     "installer_config.json")
            self._check_for_file(self.installer_config_file)
        return self.installer_config_file

    def get_install_spec_template_file(self, config_option_num):
        filename = os.path.join(self._get_installer_metadata_directory(),
                                self.get_installer_config().install_spec_options[config_option_num]['file_name'] + ".tmpl")
        self._check_for_file(filename)
        return filename

    # we now do this in the subclasses. We put the install spec file in either build_output or <dh>/config,
    # depending on whether we're building from source. This keeps any generated files out of <dh>/engage.
    ## def get_install_spec_file(self, config_option_num):
    ##     """ We don't check for the filename in advance, as it might not yet have been created"""
    ##     filename = os.path.join(self._get_installer_metadata_directory(),
    ##                             self.get_installer_config().install_spec_options[config_option_num]['file_name'])
    ##     return filename

    def get_installer_config(self):
        if not self.installer_config:
            import engage.engine.installer_config
            self.installer_config = engage.engine.installer_config.parse_installer_config(self._get_installer_config_file())
        return self.installer_config

    def get_resource_def_file(self):
        if not self.resource_def_file:
            if self.installer_name:
                self.resource_def_file = os.path.join(self._get_metadata_directory(),
                                                      self.get_installer_config().resource_def_file_name)
            else:
                self.resource_def_file = os.path.join(self._get_metadata_directory(),
                                                      "resource_definitions.json")
            self._check_for_file(self.resource_def_file)
        return self.resource_def_file

    def get_software_library_file(self):
        if not self.software_library_file:
            if self.installer_name:
                self.software_library_file = os.path.join(self._get_metadata_directory(),
                                                          self.get_installer_config().software_library_file_name)
            else:
                self.software_library_file = os.path.join(self._get_metadata_directory(),
                                                          "resource_library.json")
            self._check_for_file(self.software_library_file)
        return self.software_library_file

    def get_deployment_home(self):
        """By default, return None, indicating we don't know
        where the app is deployed.
        """
        return None

    def get_installed_resources_file(self, deployment_home_directory):
        """We don't check for presence of file as it only exists
        after a successful deployment.

        We require that the deployment home directory gets passed in as a parameter -
        for the source file layout, the layout manager doesn't know where the deployment
        home will be. Any utilities needing this will have to require it as a command line
        option when running from source.
        """
        return os.path.join(deployment_home_directory, "config/installed_resources.json")

    def get_config_choices_file(self, deployment_home_directory):
        """The interactive installer will write the users config choices to a file,
        for use in future upgrades. Like get_installed_resources_file(), we need
        the deployment home.
        """
        return os.path.join(deployment_home_directory, "config/config_choices.json")

    def has_deployment_home(self):
        """Return true if the layout includes
        a deployment home. Return false if
        the deployment home must be specified
        on the command line.
        """
        return False

    def _get_extension_files(self, filename):
        """Find instances of the specified filename under
        the associated extension metadata directories.
        """
        metadata_dir = self._get_metadata_directory()
        matches = []
        for ext in installed_extensions:
            filepath = os.path.join(os.path.join(metadata_dir, ext), filename)
            if os.path.exists(filepath):
                matches.append(filepath)
        return matches

    def get_extension_resource_files(self):
        """Each extension may have a resource file at
        metadata/<extn_name>/resource_definitions.json.
        Return the list of such files that exist.
        """
        return self._get_extension_files("resource_definitions.json")

    def get_extension_library_files(self):
        """Each extension may have a library file at
        metadata/<extn_name>/resource_library.json.
        Return the list of such files that exist.
        """
        return self._get_extension_files("resource_library.json")

    def get_password_database_file(self):
        if not self.password_database_file:
            import engage.utils.pw_repository
            self.password_database_file = \
                os.path.join(self.get_password_file_directory(),
                             engage.utils.pw_repository.REPOSITORY_FILE_NAME)
        return self.password_database_file

    def get_password_salt_file(self):
        if not self.password_salt_file:
            import engage.utils.pw_repository
            self.password_salt_file = \
                os.path.join(self.get_password_file_directory(),
                             engage.utils.pw_repository.SALT_FILE_NAME)
        return self.password_salt_file

    # Public apis implemented by subclasses
    def get_configurator_exe(self):
        raise NotImplementedError()
    def get_password_file_directory(self):
        raise NotImplementedError()
    def get_cache_directory(self):
        raise NotImplementedError()
    def get_log_directory(self):
        raise NotImplementedError()
    def get_install_spec_file(self, config_option_no=None):
        raise NotImplementedError()
    def get_preprocessed_resource_file(self):
        """The resource definition file is preprocessed before being used
        by the config engine. This method returns the location to put
        the preprocessed file.
        """
        raise NotImplementedError()
    def get_preprocessed_library_file(self):
        """The library file is preprocessed before being used
        by the config engine. This method returns the location to put
        the preprocessed file.
        """
        raise NotImplementedError()

class DeployedFileLayout(BaseFileLayout):
    """Layout when we've done a bootstrap install into
    deployment home.
    """
    LAYOUT_TYPE = "deployed"
    def __init__(self, installer_name=None):
        BaseFileLayout.__init__(self, installer_name)
        # We use the location of the current file to figure out where
        # everything else is.
        # Need to follow symlinks for the current directory, due to issues
        # with how virtualenv works on Ubuntu 11.10 (library files are picked up
        # under local symlink path).
        current_dir = os.path.realpath(os.path.dirname(__file__))
        site_packages_dir = \
            os.path.abspath(os.path.expanduser(os.path.join(current_dir,
                                                            "../../..")))
        assert os.path.basename(site_packages_dir)=="site-packages"
        self.engage_home = os.path.abspath(os.path.join(site_packages_dir,
                                                        "../../.."))
        assert os.path.basename(self.engage_home)=="engage", \
               "Expecting engage home at %s" % self.engage_home
        self.bin_directory = os.path.join(self.engage_home, "bin")
        self._check_for_directory(self.bin_directory)
        # deployment hone is one level up from engage home
        self.deployment_home = os.path.abspath(os.path.join(self.engage_home, ".."))
        self.installed_resources_file = None

    def has_deployment_home(self):
        """Return true if the layout includes
        a deployment home. Return false if
        the deployment home must be specified
        on the command line.
        """
        return True

    def get_configurator_exe(self):
        if not self.configurator_exe:
            self.configurator_exe = os.path.join(self.bin_directory, "configurator")
            self._check_for_file(self.configurator_exe)
        return self.configurator_exe

    def _get_metadata_directory(self):
        if not self.metadata_directory:
            self.metadata_directory = os.path.join(self.engage_home, "metadata")
            self._check_for_directory(self.metadata_directory)
        return self.metadata_directory
    
    def _get_deployment_config_directory(self):
        if not self.deployment_config_directory:
            self.deployment_config_directory = os.path.join(self.deployment_home, "config")
            self._check_for_directory(self.deployment_config_directory)
        return self.deployment_config_directory
    
    def get_password_file_directory(self):
        return self._get_deployment_config_directory()

    def get_install_script_file(self):
        if not self.install_script_file:
            self.install_script_file = os.path.join(self._get_deployment_config_directory(), "install.script")
        return self.install_script_file

    def get_cache_directory(self):
        if not self.cache_directory:
            self.cache_directory = os.path.join(self.engage_home, "sw_packages")
            self._check_for_directory(self.cache_directory)
        return self.cache_directory

    def get_deployment_home(self):
        return self.deployment_home

    def get_log_directory(self):
        # when the environment is bootstrapped, we save the location
        # of the log directory in <deployment_home>/config/log_directory.txt
        if not self.log_directory:
            log_info_file = os.path.join(self._get_deployment_config_directory(),
                                         "log_directory.txt")
            self._check_for_file(log_info_file)
            with open(log_info_file, "r") as f:
                self.log_directory = f.read().rstrip()
            self._check_for_directory(self.log_directory)
        return self.log_directory

    def get_install_spec_file(self, config_option_num=None):
        """ We don't check for the filename in advance, as it might not yet have been created"""
        if config_option_num:
            filename = os.path.join(self._get_deployment_config_directory(),
                                    self.get_installer_config().install_spec_options[config_option_num]['file_name'])
        else:
            filename = os.path.join(self._get_deployment_config_directory(),
                                    "install_spec.json")
        return filename

    def get_preprocessed_resource_file(self):
        """The resource definition file is preprocessed before being used
        by the config engine. This method returns the location to put
        the preprocessed file.
        """
        return os.path.join(self._get_deployment_config_directory(),
                            "resource_definitions.json")

    def get_preprocessed_library_file(self):
        """The library file is preprocessed before being used
        by the config engine. This method returns the location to put
        the preprocessed file.
        """
        return os.path.join(self._get_deployment_config_directory(),
                            "resource_library.json")
    

class SrcFileLayout(BaseFileLayout):
    LAYOUT_TYPE = "src" # used when running directly from the src tree
    def __init__(self, installer_name=None):
        BaseFileLayout.__init__(self, installer_name)
        self.src_engage_dir = os.path.abspath(os.path.expanduser(os.path.join(os.path.dirname(__file__), "../../..")))
        assert os.path.basename(self.src_engage_dir)=="engage", "Expecting %s to be engage source directory" % self.src_engage_dir
        self.src_dir = os.path.abspath(os.path.join(self.src_engage_dir, ".."))
        self.code_dir = os.path.abspath(os.path.join(self.src_dir, ".."))
        self.build_output_directory = None
        self.config_engine_dir = None

    def _get_config_engine_dir(self):
        if not self.config_engine_dir:
            self.config_engine_dir = os.path.join(self.src_engage_dir,
                                                  "config_src/config/c_wrapper")
            self._check_for_directory(self.config_engine_dir)
        return self.config_engine_dir
    
    def get_configurator_exe(self):
        if not self.configurator_exe:
            self.configurator_exe = os.path.join(self._get_config_engine_dir(), "configurator")
            self._check_for_file(self.configurator_exe)
        return self.configurator_exe

    def _get_metadata_directory(self):
        if not self.metadata_directory:
            self.metadata_directory = os.path.join(self.src_engage_dir, "metadata")
            self._check_for_directory(self.metadata_directory)
        return self.metadata_directory

    def _get_build_output_directory(self):
        if not self.build_output_directory:
            self.build_output_directory = os.path.join(self.code_dir, "build_output")
            if not os.path.exists(self.build_output_directory):
                os.makedirs(self.build_output_directory)
        return self.build_output_directory
    
    def get_password_file_directory(self):
        return self._get_build_output_directory()

    def get_install_script_file(self):
        if not self.install_script_file:
            self.install_script_file = os.path.join(self._get_build_output_directory(), "install.script")
        return self.install_script_file

    def get_cache_directory(self):
        if not self.cache_directory:
            self.cache_directory = os.path.abspath(os.path.join(self.code_dir, "../sw_packages"))
            self._check_for_directory(self.cache_directory)
        return self.cache_directory

    def get_log_directory(self):
        if not self.log_directory:
            self.log_directory = os.path.join(self._get_build_output_directory(), "log")
            if not os.path.exists(self.log_directory):
                os.makedirs(self.log_directory)
        return self.log_directory

    def get_install_spec_file(self, config_option_num=None):
        """ We don't check for the filename in advance, as it might not yet have been created"""
        if config_option_num:
            filename = os.path.join(self._get_build_output_directory(),
                                    self.get_installer_config().install_spec_options[config_option_num]['file_name'])
        else:
            filename = os.path.join(self._get_build_output_directory(),
                                    "install_spec.json")
        return filename

    def get_preprocessed_resource_file(self):
        """The resource definition file is preprocessed before being used
        by the config engine. This method returns the location to put
        the preprocessed file.
        """
        return os.path.join(self._get_build_output_directory(),
                            "resource_definitions.json")

    def get_preprocessed_library_file(self):
        """The library file is preprocessed before being used
        by the config engine. This method returns the location to put
        the preprocessed file.
        """
        return os.path.join(self._get_build_output_directory(),
                            "resource_library.json")


class DistFileLayout(BaseFileLayout):
    LAYOUT_TYPE = "dist" # used when running from distribution home
    def __init__(self, installer_name=None):
        BaseFileLayout.__init__(self, installer_name)
        self.engage_dir = os.path.abspath(os.path.expanduser(os.path.join(os.path.dirname(__file__), "../../..")))
        assert os.path.basename(self.engage_dir).startswith("engage"), \
           "Expecting %s to start with 'engage'" % self.engage_dir
        # we might not really be running under build_output, but we use whatever is the
        # parent directory as the place for generated files.
        self.build_output_directory = os.path.abspath(os.path.join(self.engage_dir, ".."))
        self.bin_dir = None

    def _get_bin_dir(self):
        if not self.bin_dir:
            self.bin_dir = os.path.join(self.engage_dir, "bin")
            self._check_for_directory(self.bin_dir)
        return self.bin_dir
    
    def get_configurator_exe(self):
        if not self.configurator_exe:
            
            self.configurator_exe = os.path.join(self._get_bin_dir(),
                                                 "configurator-" +
                                                 engage.utils.system_info.get_platform())
            self._check_for_file(self.configurator_exe)
        return self.configurator_exe

    def _get_metadata_directory(self):
        if not self.metadata_directory:
            self.metadata_directory = os.path.join(self.engage_dir, "metadata")
            self._check_for_directory(self.metadata_directory)
        return self.metadata_directory

    
    def get_password_file_directory(self):
        return self.build_output_directory

    def get_install_script_file(self):
        if not self.install_script_file:
            self.install_script_file = os.path.join(self.build_output_directory, "install.script")
        return self.install_script_file

    def get_cache_directory(self):
        if not self.cache_directory:
            self.cache_directory = os.path.join(self.engage_dir, "sw_packages")
            self._check_for_directory(self.cache_directory)
        return self.cache_directory

    def get_log_directory(self):
        if not self.log_directory:
            self.log_directory = os.path.join(self.build_output_directory, "log")
            if not os.path.exists(self.log_directory):
                os.makedirs(self.log_directory)
        return self.log_directory

    def get_install_spec_file(self, config_option_num=None):
        """ We don't check for the filename in advance, as it might not yet have been created"""
        if config_option_num:
            filename = os.path.join(self.build_output_directory,
                                    self.get_installer_config().install_spec_options[config_option_num]['file_name'])
        else:
            filename = os.path.join(self.build_output_directory,
                                    "install_spec.json")
        return filename

    def get_preprocessed_resource_file(self):
        """The resource definition file is preprocessed before being used
        by the config engine. This method returns the location to put
        the preprocessed file.
        """
        return os.path.join(self.build_output_directory,
                            "resource_definitions.json")

    def get_preprocessed_library_file(self):
        """The library file is preprocessed before being used
        by the config engine. This method returns the location to put
        the preprocessed file.
        """
        return os.path.join(self.build_output_directory,
                            "resource_library.json")


layout_mgrs = {
    DeployedFileLayout.LAYOUT_TYPE: DeployedFileLayout,
    SrcFileLayout.LAYOUT_TYPE: SrcFileLayout,
    DistFileLayout.LAYOUT_TYPE: DistFileLayout
}


valid_layouts = layout_mgrs.keys()


def get_engine_layout_mgr(installer_name=None):
    """This is the main entry point for this module. It returns a layout manager object.
    The installer_name has to be specified if you are going to access files that are specific
    to each installer (e.g. installer_config.json and the install spec files).

    To determine whether this is a deployed file layout vs. a source file layout, we look at
    whether we are underneath a site_packages directory.
    """
    # need to follow symlinks for the current directory, due to issues
    # with how virtualenv works on Ubuntu 11.10 (library files are picked up
    # under local symlink path).
    current_dir = os.path.realpath(os.path.dirname(__file__))
    possible_site_packages_dir = os.path.abspath(os.path.expanduser(os.path.join(current_dir, "../../..")))
    if os.path.basename(possible_site_packages_dir)=="site-packages":
        layout_type = DeployedFileLayout.LAYOUT_TYPE
    else:
        possible_code_dir = os.path.abspath(os.path.expanduser(os.path.join(current_dir, "../../../../..")))
        src_sw_packages_dir = os.path.abspath(os.path.join(possible_code_dir, "../sw_packages"))
        dist_sw_packages_dir = os.path.abspath(os.path.join(current_dir, "../../../sw_packages"))
        if os.path.exists(possible_code_dir) and os.path.basename(possible_code_dir)=="code" and \
           os.path.exists(src_sw_packages_dir) and (not os.path.exists(dist_sw_packages_dir)):
            layout_type = SrcFileLayout.LAYOUT_TYPE
        else:
            possible_engage_dir = os.path.abspath(os.path.expanduser(os.path.join(current_dir, "../../..")))
            if os.path.exists(possible_engage_dir) and \
               os.path.basename(possible_engage_dir).startswith("engage") and \
               os.path.exists(dist_sw_packages_dir):
                layout_type = DistFileLayout.LAYOUT_TYPE
            else:
                raise UserError(errors[ERR_UNKNOWN_LAYOUT],
                                msg_args={"dir":current_dir})
    logger.debug("Using installer file layout type %s" % layout_type)
    return (layout_mgrs[layout_type])(installer_name)


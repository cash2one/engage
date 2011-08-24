"""Service manager for gearman
"""
import os
import os.path
import shutil
import sys
import time

import engage.drivers.service_manager as service_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.drivers.utils
import engage.utils.path as iupath
import engage.utils.process as iuprocess
import engage.utils.http as iuhttp
import engage.utils.log_setup
import engage.utils.file as iufile
import engage.utils.timeout as iutimeout
import engage.drivers.genforma.aptget as aptget
# PasswordRepoMixin is included in BackupFileMixin
#from engage.drivers.password_repo_mixin import PasswordRepoMixin
from engage.drivers.backup_file_resource_mixin import BackupFileMixin

logger = engage.utils.log_setup.setup_script_logger(__name__)

from engage.utils.user_error import ScriptErrInf, UserError

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_GEARMAN_BUILD_FAILED    = 1
ERR_GEARMAN_NO_INSTALL_DIR  = 2
ERR_GEARMAN_PY_SETUP_FAILED = 3
ERR_NO_GEARMAN_SCRIPT       = 4
ERR_GEARMAN_SCRIPT_FAILED   = 5
ERR_GEARMAN_EXITED          = 6


define_error(ERR_GEARMAN_BUILD_FAILED,
             _("Gearman build failed"))
define_error(ERR_GEARMAN_NO_INSTALL_DIR,
             _("Post install check failed: missing installation directory '%(dir)s'"))
define_error(ERR_GEARMAN_PY_SETUP_FAILED,
             _("Install of Gearman Python client failed."))
define_error(ERR_NO_GEARMAN_SCRIPT,
             _("Missing Gearman administration script %(file)s"))
define_error(ERR_GEARMAN_SCRIPT_FAILED,
             _("Gearman administration script failed for action '%(action)s'"))
define_error(ERR_GEARMAN_EXITED,
             _("Gearman daemon appears to have exited after startup"))


def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)

# timeouts for checking server liveness after startup
TIMEOUT_TRIES = 10
TIME_BETWEEN_TRIES = 2.0


_config_type = {
    "output_ports": {
      "gearman": {
        "home": unicode
      }      
    },
    "input_ports": {
      "host": {
          "hostname": unicode,
          "os_type" : unicode,
          "os_user_name" : unicode,
          "sudo_password" : unicode,
          "cpu_arch" : unicode
        }
    }    
}

class Config(resource_metadata.Config):
    def __init__(self, props_in, types, id, package_name):
        resource_metadata.Config.__init__(self, props_in, types)
        self._add_computed_prop("id", id)
        self._add_computed_prop("package_name", package_name)
        self._add_computed_prop("home_path",
                                os.path.abspath(self.output_ports.gearman.home))
        self._add_computed_prop("gearman_admin_script",
                                os.path.join(self.home_path, "gearmand.sh"))
        self._add_computed_prop("log_dir",
                                os.path.join(self.home_path, "log"))
        self._add_computed_prop("pid_file",
                                os.path.join(self.log_dir, "gearmand.pid"))
                                

class Manager(service_manager.Manager, BackupFileMixin):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        self.config = metadata.get_config(_config_type, Config, self.id,
                                          package_name)

    def validate_pre_install(self):
        iupath.check_installable_to_target_dir(self.config.home_path,
                                               self.config.package_name)
        logger.debug("%s instance %s passed pre-install checks." %
                     (self.config.package_name, self.id))
        
    def install(self, package):
        # if this is a linux system, we need to make sure that uuid/uuid.h is present
        if self.config.input_ports.host.os_type == "linux":
            if not os.path.exists("/usr/include/uuid/uuid.h"):
                aptget.apt_get_install(["uuid-dev"], self._get_sudo_password())
        base_name = os.path.basename(self.config.home_path)
        parent_dir = os.path.dirname(self.config.home_path)
        extracted_dir = package.extract(parent_dir)
	assert extracted_dir == base_name
        # configure with prefix self.confg.home_path, make and make install
        logger.info("Building gearman daemon")
        rc = iuprocess.run_and_log_program(["/usr/bin/make", "all"],
                                           {"PATH":"/usr/bin:/bin:/usr/sbin"},
                                           logger,
                                           cwd=self.config.home_path)
        if rc != 0:
            raise UserError(errors[ERR_GEARMAN_BUILD_FAILED])
        
        gearman_pyclient_dir = os.path.join(os.path.join(self.config.home_path, "src"),
                                            "gearman-1.5.0")
        logger.info("Installing gearman python client")
        # TODO: this should really be done using easy_install. Even better,
        # we should upgrade to the latest version of Gearman and install the
        # version of the client on PyPi.
        rc = iuprocess.run_and_log_program([self.config.input_ports.python.home,
                                            "setup.py", "install"],
                                           {}, logger, cwd=gearman_pyclient_dir)
        if rc != 0:
            raise UserError(errors[ERR_GEARMAN_PY_SETUP_FAILED])

        # instantiate the startup/shutdown script for gearmand
        script_tmpl_path = iufile.get_data_file_path(__file__,
                                                     "gearmand.sh.tmpl")
        iufile.instantiate_template_file(script_tmpl_path,
                                         self.config.gearman_admin_script,
                                         {"gearman_home":self.config.home_path,
                                          "log_dir":self.config.log_dir,
                                          "pid_file":self.config.pid_file},
                                         logger=logger)
                                              
        # check that everything is now in place
        self.validate_post_install()


    def is_installed(self):
        if not os.path.exists(self.config.home_path):
            return False
        rc = iuprocess.run_and_log_program([self.config.input_ports.python.home,
                                            "-c", "import gearman"],
                                           {}, logger)
        if rc == 0:
            return True
        else:
            logger.debug("%s: directory %s exists, but gearman package not found" %
                         (self.id, self.config.home_path))
            return False

    def validate_post_install(self):
        if not os.path.exists(self.config.home_path):
            raise UserError(ERR_GEARMAN_NO_INSTALL_DIR, {"dir":self.config.home_path})

    def _run_admin_script(self, action):
        if not os.path.exists(self.config.gearman_admin_script):
            raise UserError(errors[ERR_NO_GEARMAN_SCRIPT],
                            msg_args={"file":self.config.gearman_admin_script})
        prog_and_args = [self.config.gearman_admin_script, action]
        rc = iuprocess.run_and_log_program(prog_and_args, {}, logger)
        if rc != 0:
            raise UserError(errors[ERR_GEARMAN_SCRIPT_FAILED],
                            msg_args={"action":action},
                            developer_msg="script %s, rc was %d" % (self.config.gearman_admin_script, rc))

    def _run_admin_script_in_background(self, action):
        if not os.path.exists(self.config.gearman_admin_script):
            raise UserError(errors[ERR_NO_GEARMAN_SCRIPT],
                            msg_args={"file":self.config.gearman_admin_script})
        prog_and_args = [self.config.gearman_admin_script, action]
        rc = iuprocess.run_background_program(prog_and_args, {}, os.path.join(self.config.log_dir, "gearman_%s.log" % action),
                                              logger)
        if rc != 0:
            raise UserError(errors[ERR_GEARMAN_SCRIPT_FAILED],
                            msg_args={"action":action},
                            developer_msg="script %s (run in background), rc was %d" % (self.config.gearman_admin_script, rc))

    def start(self):
        self._run_admin_script_in_background("start")
        for i in range(TIMEOUT_TRIES):
            pid = iuprocess.check_server_status(self.config.pid_file, logger,
                                                self.config.id)
            if pid:
                return
            time.sleep(TIME_BETWEEN_TRIES)
        if not pid:
            raise UserError(errors[ERR_GEARMAN_EXITED])

    def is_running(self):
        if iuprocess.check_server_status(self.config.pid_file, logger,
                                         self.config.id) != None:
            return True
        else:
            return False

    def stop(self):
        self._run_admin_script("stop")

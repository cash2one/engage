"""Service manager for redis
"""
import os
import os.path
import shutil
import sys
import time

import engage.drivers.service_manager as service_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.utils.path as iupath
import engage.utils.process as iuprocess
import engage.utils.http as iuhttp
import engage.utils.log_setup
import engage.utils.file as iufile
import engage.utils.timeout as iutimeout
import engage.drivers.utils

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
ERR_REDIS_BUILD_FAILED    = 1
ERR_REDIS_NO_INSTALL_DIR  = 2
ERR_REDIS_PY_SETUP_FAILED = 3
ERR_NO_REDIS_SCRIPT       = 4
ERR_REDIS_SCRIPT_FAILED   = 5
ERR_REDIS_EXITED          = 6


define_error(ERR_REDIS_BUILD_FAILED,
             _("Redis build failed"))
define_error(ERR_REDIS_NO_INSTALL_DIR,
             _("Post install check failed: missing installation directory '%(dir)s'"))
define_error(ERR_REDIS_PY_SETUP_FAILED,
             _("Install of Redis Python client failed."))
define_error(ERR_NO_REDIS_SCRIPT,
             _("Missing Redis administration script %(file)s"))
define_error(ERR_REDIS_SCRIPT_FAILED,
             _("Redis administration script failed for action '%(action)s'"))
define_error(ERR_REDIS_EXITED,
             _("Redis daemon appears to have exited after startup"))


# timeouts for checking server liveness after startup
TIMEOUT_TRIES = 10
TIME_BETWEEN_TRIES = 2.0


_config_type = {
    "output_ports": {
      "redis": {
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
                                os.path.abspath(self.output_ports.redis.home))
        self._add_computed_prop("conf_file",
                                os.path.join(self.home_path, "redis.conf"))
        self._add_computed_prop("log_dir",
                                os.path.join(self.home_path, "log"))
        self._add_computed_prop("pid_file",
                                os.path.join(self.log_dir, "redis.pid"))
                                
def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)

class Manager(service_manager.Manager):
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
        base_name = os.path.basename(self.config.home_path)
        parent_dir = os.path.dirname(self.config.home_path)
        extracted_dir = package.extract(parent_dir)
	assert extracted_dir == base_name, "base_name is %s, and extracted_dir is %s" % (base_name, extracted_dir)
        # configure with prefix self.confg.home_path, make and make install
        rc = iuprocess.system('cd %s; /usr/bin/make ' % 
                              self.config.home_path, logger,
                              log_output_as_info=True)
        if rc != 0:
            raise UserError(errors[ERR_REDIS_BUILD_FAILED])
        # check that everything is now in place
        self.validate_post_install()


    def is_installed(self):
        return os.path.exists(self.config.home_path)

    def validate_post_install(self):
        if not os.path.exists(self.config.home_path):
            raise UserError(ERR_REDIS_NO_INSTALL_DIR, {"dir":self.config.home_path})

    def start(self):
        redis_server = os.path.join(self.config.home_path, 'src/redis-server')
        log_file = os.path.join(self.config.log_dir, 'redis.log')
        iuprocess.run_server([redis_server, self.config.conf_file], { }, log_file,
                             logger, self.config.pid_file)
        for i in range(TIMEOUT_TRIES):
            pid = iuprocess.check_server_status(self.config.pid_file, logger,
                                                self.config.id)
            if pid:
                return
            time.sleep(TIME_BETWEEN_TRIES)
        if not pid:
            raise UserError(errors[ERR_REDIS_EXITED])

    def is_running(self):
        if iuprocess.check_server_status(self.config.pid_file, logger,
                                         self.config.id) != None:
            return True
        else:
            return False

    def stop(self):
        redis_client = os.path.join(self.config.home_path, 'src/redis-cli')
        rc = iuprocess.run_and_log_program([redis_client, 'shutdown'], {}, logger) 
        if rc != 0:
            raise UserError(errors[ERR_REDIS_SCRIPT_FAILED],
                            msg_args={"action":'stop'},
                            developer_msg="redis server shutdown failed (run in background), rc was %d" % rc)

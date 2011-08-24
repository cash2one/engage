"""Service manager for apache tomcat
"""

import os
import os.path
import shutil
import sys
import time

import engage.drivers.resource_metadata as resource_metadata
import engage.drivers.service_manager as service_manager
import engage.utils.path
import engage.utils.process
import engage.utils.http
import engage.utils.log_setup
import engage.utils.file
import xml.etree.ElementTree as et
import engage.engine.install_context as install_context

logger = engage.utils.log_setup.setup_script_logger("Tomcat")

from engage.utils.user_error import ScriptErrInf, UserError, convert_exc_to_user_error

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("Tomcat", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_NO_WINDOWS         = 1
ERR_BAD_CONFIG_FILE    = 2
ERR_FILE_CHG_EXC       = 3
ERR_MISSING_CONN_DEF   = 4
ERR_NO_HOME_DIR        = 5
ERR_NO_STARTUP_SCRIPT  = 6
ERR_NO_SHUTDOWN_SCRIPT = 7
ERR_PORT_TAKEN         = 8
ERR_STARTUP_EXC        = 9
ERR_STARTUP_FAIL       = 0
ERR_STARTUP_ERR_IN_LOG = 11
ERR_STARTUP_TIMEOUT    = 12
ERR_SHUTDOWN_EXC       = 13
ERR_SHUTDOWN_FAIL      = 14

define_error(ERR_NO_WINDOWS,
             _("Installation to Windows currently not supported"))
define_error(ERR_BAD_CONFIG_FILE,
             _("Unable to configure Tomcat: configuration file %(file)s does not have expected format."))
define_error(ERR_FILE_CHG_EXC,
             _("Unable to configure Tomcat: error in changing file %(file)s"))
define_error(ERR_MISSING_CONN_DEF,
             _("Unable to configure Tomcat: unable to find connector definition in file %(file)s"))
define_error(ERR_NO_HOME_DIR,
             _("Home directory '%(dir)s' does not exist"))
define_error(ERR_NO_STARTUP_SCRIPT,
             _("Missing startup script %(script)s for Tomcat"))
define_error(ERR_NO_SHUTDOWN_SCRIPT,
             _("Missing shutdown script %(script)s for Tomcat"))
define_error(ERR_PORT_TAKEN,
             _("It appears that something is already running on Tomcat's port (%(port)d)"))
define_error(ERR_STARTUP_EXC,
             _("Error in running Tomcat startup script."))
define_error(ERR_STARTUP_FAIL,
             _("Startup of Tomcat failed, return code was %(rc)d."))
define_error(ERR_STARTUP_ERR_IN_LOG,
             _("There appears to be an error in starting Tomcat, see, see logfile %(file)s for details"))
define_error(ERR_STARTUP_TIMEOUT,
             _("Startup of Tomcat timed out, see logfile %(file)s"))
define_error(ERR_SHUTDOWN_EXC,
             _("Unable to stop Tomcat using script %(script)s"))
define_error(ERR_SHUTDOWN_FAIL,
             _("Shutdown of Tomcat failed, return code was %(rc)d"))

class TomcatError(UserError):
    def __init__(self, error_id, action, mgr, msg_args=None, developer_msg=None):
        context = ["%s of %s, instance %s" % 
                   (action, mgr.config.package_name, mgr.id)]
        UserError.__init__(self, errors[error_id], msg_args, developer_msg, context)

TIMEOUT_TRIES = 10
TIME_BETWEEN_TRIES = 2.0

_config_type = {
  "config_port": {
    "home": unicode,
    "manager_port": int,
    "admin_user":unicode,
    "admin_password":unicode
  },
  "input_ports": {
    "java": {
      "type": unicode,
      "home": unicode
     },
    "host" : {
      "hostname": unicode
    }
   },
   "output_ports": {
     "tomcat": {
       "environment_vars":[{"name":unicode, "value":unicode}]
     }
  }
}

class Config(resource_metadata.Config):
    def __init__(self, props_in, types, package_name):
        resource_metadata.Config.__init__(self, props_in, types)
        self._add_computed_prop("package_name", package_name)
        self._add_computed_prop("home_path",
                                os.path.abspath(self.config_port.home))
        self._add_computed_prop("home_dir_parent",
                                os.path.dirname(self.home_path))
        self._add_computed_prop("home_dir",
                                os.path.basename(self.home_path))
        self._add_computed_prop("bin_dir", os.path.join(self.home_path, "bin"))
        self._add_computed_prop("startup_script",
                                os.path.join(self.bin_dir, "startup.sh"))
        self._add_computed_prop("shutdown_script",
                                os.path.join(self.bin_dir, "shutdown.sh"))
        env_mapping = {"CATALINA_HOME":self.home_path}
        if self.input_ports.java.type=="jdk":
            env_mapping["JAVA_HOME"] = self.input_ports.java.home
        else:
            env_mapping["JRE_HOME"] = self.input_ports.java.home
        for env_var_def in self.output_ports.tomcat.environment_vars:
            env_mapping[env_var_def.name] = env_var_def.value
        self._add_computed_prop("env_mapping", env_mapping)
                                


class Manager(service_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        self.config = metadata.get_config(_config_type, Config, package_name)


    def validate_pre_install(self):
        if sys.platform=="win32":
            raise TomcatError(ERR_NO_WINDOWS, "Pre-install validation",
                              self)
        engage.utils.path.check_installable_to_target_dir(self.config.home_path,
                                                          self.config.package_name)
        logger.debug("%s instance %s passed pre-install checks." %
                     (self.config.package_name, self.id))
 
    def _add_admin_user(self, user_cfg_file):
        """Add the admin to the tomcat-users config file"""
        try:
            orig_file = user_cfg_file + ".orig"
            shutil.move(user_cfg_file, orig_file)
            shutil.copy(orig_file, user_cfg_file)
            tree = et.parse(user_cfg_file)
            root = tree.getroot()
            if root.tag != "tomcat-users":
                raise TomcatError(ERR_BAD_CONFIG_FILE, "Install", self,
                                  {"file": user_cfg_file})
            role = et.Element("role", {"rolename":"manager"})
            root.append(role)
            admin_password = install_context.password_repository.get_value(self.config.config_port.admin_password)
            user = et.Element("user",
                              {"username":self.config.config_port.admin_user,
                               "password":admin_password,
                               "roles":"manager"})
            root.append(user)
            tree.write(user_cfg_file)
        except IOError, msg:
            raise convert_exc_to_user_error(sys.exc_info(),
                                            errors[ERR_FILE_CHG_EXC],
                                            {"file":user_cfg_file})
    def _set_port(self, server_file):
        pat = '(\\<Connector\\ port\\=\\")(8080)(\\"\\ protocol\\=\\"HTTP\\/1\\.1\\")'
        def replace_fn(mo):
            return mo.group(1) + self.config.config_port.manager_port.__str__() + mo.group(3)
        cnt = engage.utils.file.subst_in_file(server_file,
                                              [(pat, replace_fn)])
        if cnt!=1:
            raise TomcatError(ERR_MISSING_CONN_DEF, "Install", self,
                              {"file":server_file})
                                              
    def install(self, package):
        extracted_dir = package.extract(self.config.home_dir_parent)
        if extracted_dir != self.config.home_dir:
            # make the final name of the tomcat dir equivalent to the
            # one specified in the resource instance
            shutil.move(os.path.join(self.config.home_dir_parent,
                                     extracted_dir),
                        self.config.home_path)
        # check that everything is now in place
        self.validate_post_install()
        # update configuraiton files
        cfg_dir = os.path.join(self.config.home_path, "conf")
        user_cfg_file = os.path.join(cfg_dir, "tomcat-users.xml")
        self._add_admin_user(user_cfg_file)
        server_cfg_file = os.path.join(cfg_dir, "server.xml")
        self._set_port(server_cfg_file)
        logger.info("Extracted %s to %s\n" % (self.config.package_name,
                                              self.config.home_path))
 
    def validate_post_install(self):
        if not os.path.exists(self.config.home_path):
            raise TomcatError(ERR_NO_HOME_DIR, "Post install validation",
                              self, {"dir":self.config.home_path})
        if not os.access(self.config.startup_script, os.X_OK):
            raise TomcatError(ERR_NO_STARTUP_SCRIPT,
                              "Post install validation",
                              self, {"script":self.config.startup_script})
        if not os.access(self.config.shutdown_script, os.X_OK):
            raise TomcatError(ERR_NO_SHUTDOWN_SCRIPT,
                              "Post install validation",
                              self, {"script":self.config.shutdown_script})

    def is_installed(self):
        return os.path.exists(self.config.home_path)

    def start(self):
        if engage.utils.http.ping_webserver(self.config.input_ports.host.hostname, self.config.config_port.manager_port):
            raise TomcatError(ERR_PORT_TAKEN,
                              "Startup", self,
                              {"port":self.config.config_port.manager_port})

        # there isn't anything running on that port. Now, scan to the end of
        # the logfile, if there is one.
        logfile = os.path.join(os.path.join(self.config.home_path, "logs"),
                               "catalina.out")
        scan_map = {
            "Stopped":"INFO: Stopping Coyote",
            "Error": "error"
            }
        log_scanner = \
            engage.utils.file.FilePatternScan(logfile, scan_map,
                                              seek_to_end_before_scan=True)
        
        # run the startup script
        try:
            rc = \
             engage.utils.process.run_and_log_program([self.config.startup_script],
                                                      self.config.env_mapping, logger,
                                                      cwd=self.config.bin_dir)
        except OSError, msg:
            raise convert_exc_to_user_error(sys.exc_info(),
                                            errors[ERR_STARTUP_EXC])
        if rc != 0:
            raise TomcatError(ERR_STARTUP_FAIL, "Startup", self,
                              {"rc":rc})

        # wait for startup
        for i in range(TIMEOUT_TRIES):
            scan_result = log_scanner.scan()
            if scan_result["Stopped"] or scan_result["Error"]:
                raise TomcatError(ERR_STARTUP_ERR_IN_LOG, "Startup", self,
                                  {"file":logfile})
            if engage.utils.http.check_url(self.config.input_ports.host.hostname, self.config.config_port.manager_port, "/",
                                           logger):
                # tomcat has been started
                logger.info("%s startup successful." % self.config.package_name)
                return
            time.sleep(TIME_BETWEEN_TRIES)
        # if we get here, startup timed out
        raise TomcatError(ERR_STARTUP_TIMEOUT, "Startup", self,
                          {"file":logfile})

    def is_running(self):
        """Try to figure out whether tomcat is running. For now, we
        just do this by retrieving the default tomcat page. There's
        a chance that some other web server could be running on this
        port, but we'll ignore that for now."""
        if engage.utils.http.check_url(self.config.input_ports.host.hostname,
                                       self.config.config_port.manager_port, "/",
                                       logger):
            return True
        else:
            return False

    def stop(self):
        try:
            rc = \
             engage.utils.process.run_and_log_program([self.config.shutdown_script],
                                                      self.config.env_mapping,
                                                      logger,
                                                      cwd=self.config.bin_dir)
        except OSError:
            raise convert_exc_to_user_error(sys.exc_info(),
                                            errors[ERR_SHUTDOWN_EXC],
                                            {"script": self.config.shutdown_script})
        if rc != 0:
            raise TomcatError(ERR_SHUTDOWN_FAIL, "Shutdown", self,
                              {"rc":rc})

"""Service manager for mysql
"""
import os
import os.path
import shutil
import sys
import time
import tempfile
import stat
import urllib2

import engage.drivers.service_manager as service_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.utils.path as iupath
import engage.utils.process as iuprocess
import engage.utils.log_setup
import engage.utils.file as iufile
import engage.utils.http as iuhttp
import engage.utils.timeout as iutimeout
from engage.utils.user_error import ScriptErrInf, UserError

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("OpenMRS", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_CALL_MYSQL     =  1
ERR_NO_DBSCHEMA    =  2
ERR_RUNTIME_PROPS  =  3
ERR_DEPLOY_RSP     =  4
ERR_NO_INSTALL_DIR =  5
ERR_NO_WAR_FILE    =  6
ERR_TOMCAT_STARTUP =  7
ERR_TOMCAT_STARTRSP = 8
ERR_TOMCAT_STOPRSP  = 9
ERR_TOMCAT_STOPREQ  = 10

define_error(ERR_CALL_MYSQL,
             _("Unexpected error in running query against MySQL."))
define_error(ERR_NO_DBSCHEMA,
             _("It appears that the openmrs database schema was not created."))
define_error(ERR_RUNTIME_PROPS,
             _("File '%(file)s' did not contain the expected configuration properties."))
define_error(ERR_DEPLOY_RSP,
             _("Unexpected deployment response from Tomcat."))
define_error(ERR_NO_INSTALL_DIR,
             _("Install directory '%(dir)s' does not exist."))
define_error(ERR_NO_WAR_FILE,
             _("WAR file for OpenMRS has not been deployed to Tomcat server."))
define_error(ERR_TOMCAT_STARTRSP,
             _("Unexpected startup response from Tomcat."))
define_error(ERR_TOMCAT_STARTUP,
             _("Error in making startup request to Tomcat."))
define_error(ERR_TOMCAT_STOPRSP,
             _("Unexpected shutdown response from Tomcat manager."))
define_error(ERR_TOMCAT_STOPREQ,
             _("Error in making shutdown request to Tomcat."))

class OpenmrsError(UserError):
    def __init__(self, error_id, action, config, msg_args=None, developer_msg=None):
        context = ["%s of %s, instance %s" % 
                   (action, config.package_name, config.id)]
        UserError.__init__(self, errors[error_id], msg_args, developer_msg, context)
        self.config = config # keep this around just in case we want it later



CREATE_DB_FILENAME = "1.3.4-createdb-from-scratch-with-demo-data.sql"

logger = engage.utils.log_setup.setup_script_logger("OpenMRS")

_deploy_req_uri = "http://%s:%d/manager/deploy?path=/openmrs&war=file:%s/openmrs.war"
_deploy_rsp = "OK - Deployed application at context path /openmrs"
_start_req_uri = "http://%s:%d/manager/start?path=/openmrs"
_start_rsp = "OK - Started application at context path /openmrs"
_stop_req_uri = "http://%s:%d/manager/stop?path=/openmrs"
_stop_rsp = "OK - Stopped application at context path /openmrs"
_tomcat_mgr_realm = "Tomcat Manager Application"


TIMEOUT_TRIES = 10
TIME_BETWEEN_TRIES = 2.0

_config_type = {
  "config_port": {
    "database_user": unicode,
    "database_password": unicode,
    "home": unicode
  },
  "input_ports": {
    "java": {
      "type": unicode,
      "home": unicode
    },
    "tomcat": {
      "admin_user": unicode,
      "admin_password": unicode,
      "hostname": unicode,
      "manager_port": int,
      "home": unicode
    },
    "mysql": {
      "host": unicode,
      "port": int
    },
    "mysql_admin": {
      "root_password": unicode,
      "install_dir": unicode
    }
  }
}                              


class Config(resource_metadata.Config):
    def __init__(self, props_in, types, id, package_name):
        resource_metadata.Config.__init__(self, props_in, types)
        self._add_computed_prop("id", id)
        self._add_computed_prop("package_name", package_name)
        self._add_computed_prop("home_path",
                                os.path.abspath(self.config_port.home))
        self._add_computed_prop("home_dir_parent",
                                os.path.dirname(self.home_path))
        self._add_computed_prop("home_dir",
                                os.path.basename(self.home_path))
        self._add_computed_prop("mysql_path",
                                os.path.join(
                                  os.path.join(
                                    self.input_ports.mysql_admin.install_dir,
                                    "bin"), "mysql"))
        self._add_computed_prop("socket_file",
                                os.path.join(
                                  self.input_ports.mysql_admin.install_dir,
                                    "mysql.sock"))
        self._add_computed_prop("createdb_sql_path",
                                os.path.join(self.home_path,
                                             CREATE_DB_FILENAME))
        self._add_computed_prop("runtime_properties",
                                os.path.join(self.home_path,
                                             "runtime.properties"))
        self._add_computed_prop("deployment_target_path",
          os.path.join(
                os.path.join(os.path.abspath(self.input_ports.tomcat.home),
                             "webapps"),
                "openmrs"))


def call_mysql(config, input, continue_on_error=False):
    cfg_filename = \
      iufile.make_temp_config_file(
        "[mysql]\nuser=root\npassword=%s\nport=%d\n" %
        (config.input_ports.mysql_admin.root_password,
         config.input_ports.mysql.port),
        dir=config.home_path)
    defaults_file = "--defaults-file=%s" % cfg_filename
    socket_file = "--socket=%s" % config.socket_file
    try:
        rc = iuprocess.run_and_log_program([config.mysql_path, defaults_file,
                                            socket_file],
                                           {},
                                           logger,
                                           cwd=config.home_path,
                                           input=input)
    finally:
        os.remove(cfg_filename)
    if rc!=0 and not continue_on_error:
        raise OpenmrsError(ERR_CALL_MYSQL, "Install", config,
                           developer_msg="Return code: '%d', Input: '%s'" % (rc, input))
    return rc


def check_for_database(config):
    rc = call_mysql(config, "use openmrs;\n", continue_on_error=True)
    if rc!=0:
        raise OpenmrsError(ERR_NO_DBSCHEMA,
                           "Validate install", config,
                           developer_msg="mysql 'use openmrs' failed")


def setup_runtime_properties(config):
    cnt = \
        iufile.subst_in_file(config.runtime_properties,
                             [('\\{database\\_user\\}',
                               config.config_port.database_user),
                              ('\\{database\\_password\\}',
                               config.config_port.database_password),
                              ('\\{db\\_hostname\\}',
                               config.input_ports.mysql.host),
                              ('\\{db\\_port\\}',
                               config.input_ports.mysql.port.__str__())])
    if cnt != 4:
        raise OpenmrsError(ERR_RUNTIME_PROPS, "Install", config,
                           msg_args={"file":config.runtime_properties})

def check_status(config):
    return iuhttp.check_url(config.input_ports.tomcat.hostname,
                            config.input_ports.tomcat.manager_port,
                            "/openmrs/index.htm", logger)

_mysql_cmds = \
"""source {0}
GRANT ALL ON openmrs.* TO '{1}'@'%' IDENTIFIED BY '{2}';
exit
"""

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
        extracted_dir = package.extract(self.config.home_dir_parent)
        if extracted_dir != self.config.home_dir:
            # make the final name of the tomcat dir equivalent to the
            # one specified in the resource instance
            shutil.move(os.path.join(self.config.home_dir_parent,
                                     extracted_dir),
                        self.config.home_path)

        # initialize the database
        call_mysql(self.config,
                   _mysql_cmds.format(self.config.createdb_sql_path,
                                      self.config.config_port.database_user,
                                      self.config.config_port.database_password))

        # setup the runtime properties file
        setup_runtime_properties(self.config)
        # copy the war file
        #shutil.copyfile(self.config.warfile_source_path,
        #                self.config.warfile_target_path)
        uri = _deploy_req_uri % (self.config.input_ports.tomcat.hostname,
                                 self.config.input_ports.tomcat.manager_port,
                                 self.config.home_path)
        logger.debug("Attempting to deploy openmrs:\nuri=%s" % uri)
        result = iuhttp.make_request_with_basic_authentication(uri,
                       _tomcat_mgr_realm,
                       self.config.input_ports.tomcat.admin_user,
                       self.config.input_ports.tomcat.admin_password)
        if result.find(_deploy_rsp)==-1:
            raise OpenmrsError(ERR_DEPLOY_RSP, "Install", self.config,
                               developer_msg="Response was: '%s'" % result)
        # check that everything is now in place
        self.validate_post_install()
        #if not iutimeout.retry(check_status, TIMEOUT_TRIES,
        #                       TIME_BETWEEN_TRIES, self.config):
        #    raise InstallError, \
        #        "%s: OpenMRS installed but not responding" % \
        #        self.config.package_name

    def is_installed(self):
        return os.path.exists(self.config.home_path)

    def validate_post_install(self):
        if not os.path.exists(self.config.home_path):
            raise OpenmrsError(ERR_NO_INSTALL_DIR, "Validate post install",
                               self.config, {"dir":self.config.home_path})
        check_for_database(self.config)
        if not os.path.exists(self.config.deployment_target_path):
            raise OpenmrsError(ERR_NO_WAR_FILE, "Validate post install",
                               self.config,
                               developer_msg="Expected file at '%s'" %
                                              self.config.deployment_target_path)

    def start(self):
        uri = _start_req_uri % \
            (self.config.input_ports.tomcat.hostname,
             self.config.input_ports.tomcat.manager_port)
        try:
            result = iuhttp.make_request_with_basic_authentication(uri,
                       _tomcat_mgr_realm,
                       self.config.input_ports.tomcat.admin_user,
                       self.config.input_ports.tomcat.admin_password)
            if result.find(_start_rsp)==-1:
                raise OpenmrsError(ERR_TOMCAT_STARTRSP, "Startup",
                                   self.config,
                                   developer_msg="Response was '%s'" % result)
        except urllib2.URLError, msg:
            raise OpenmrsError(ERR_TOMCAT_STARTUP, "Startup", self.config,
                               developer_msg="Tomcat error was '%s'" % msg)

    def is_running(self):
        return check_status(self.config)

    def stop(self):
        uri = _stop_req_uri % \
            (self.config.input_ports.tomcat.hostname,
             self.config.input_ports.tomcat.manager_port)
        try:
            result = iuhttp.make_request_with_basic_authentication(uri,
                       _tomcat_mgr_realm,
                       self.config.input_ports.tomcat.admin_user,
                       self.config.input_ports.tomcat.admin_password)
            if result.find(_stop_rsp)==-1:
                raise OpenmrsError(ERR_TOMCAT_STOPRSP, "Stop",
                                    self.config,
                                    developer_msg="Response was '%s'" % result)
        except urllib2.URLError, msg:
            raise OpenmrsError(ERR_TOMCAT_STOPREQ, "Stop",
                                self.config,
                                developer_msg="URL error was: '%s'" % msg)

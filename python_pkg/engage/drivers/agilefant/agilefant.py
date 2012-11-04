"""Service manager for agilefant
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
import engage.utils
import engage.utils.path as iupath
import engage_utils.process as iuprocess
import engage.utils.log_setup
import engage.utils.file as iufile
import engage.utils.http as iuhttp
import engage.utils.timeout as iutimeout
from engage.utils.user_error import ScriptErrInf, UserError

import xml.etree.ElementTree as et
import engage.engine.install_context as install_context

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("Agilefant", error_code, msg)
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
             _("It appears that the agilefant database schema was not created."))
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

class AgilefantError(UserError):
    def __init__(self, error_id, action, config, msg_args=None, developer_msg=None):
        context = ["%s of %s, instance %s" % 
                   (action, config.package_name, config.id)]
        UserError.__init__(self, errors[error_id], msg_args, developer_msg, context)
        self.config = config # keep this around just in case we want it later



logger = engage.utils.log_setup.setup_script_logger("Agilefant")

_deploy_req_uri = "http://%s:%d/manager/deploy?path=/agilefant&war=file:%s/agilefant.war"
_deploy_rsp = "OK - Deployed application at context path /agilefant"
_start_req_uri = "http://%s:%d/manager/start?path=/agilefant"
_start_rsp = "OK - Started application at context path /agilefant"
_stop_req_uri = "http://%s:%d/manager/stop?path=/agilefant"
_stop_rsp = "OK - Stopped application at context path /agilefant"
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
        self._add_computed_prop("deployment_target_path",
          os.path.join(
                os.path.join(os.path.abspath(self.input_ports.tomcat.home),
                             "webapps"),
                "agilefant"))


def call_mysql(config, user, pwd, input, continue_on_error=False):
    cfg_filename = \
      iufile.make_temp_config_file(
        "[mysql]\nuser=%s\npassword=%s\nport=%d\n" %
        (user, pwd,
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
        raise AgilefantError(ERR_CALL_MYSQL, "Install", config,
                           developer_msg="Return code: '%d', Input: '%s'" % (rc, input))
    return rc


def check_for_agilefant_db(config):
    root_password = install_context.password_repository.get_value(config.input_ports.mysql_admin.root_password)
    rc = call_mysql(config, 
                    "root", root_password, 
                    "use agilefant;\n", continue_on_error=True)
    if rc!=0:
        raise AgilefantError(ERR_NO_DBSCHEMA,
                           "Validate install", config,
                           developer_msg="mysql 'use agilefant' failed")


def check_status(config):
    return iuhttp.check_url(config.input_ports.tomcat.hostname,
                            config.input_ports.tomcat.manager_port,
                            "/agilefant/", logger)

_mysql_cmds = \
"""CREATE DATABASE agilefant;
GRANT ALL ON agilefant.* TO '{0}'@'%' IDENTIFIED BY '{1}';
exit
"""

_mysql_createdb = \
"""use agilefant;
source {0}/create-db.ddl;
/*source {0}/insert-users.sql;*/
exit
"""

#TODO: set up apache forwarding
_apache_forward = \
"""ProxyPass         /agilefant  http://{0}:{1}/agilefant
ProxyPassReverse  /agilefant  http://{0}:{1}/agilefant
"""
_apache_connector = \
"""<Connector port="{1}" 
    protocol="HTTP/1.1" connectionTimeout="20000" redirectPort="8443"
    proxyName="{0}" proxyPort="80"/>
"""


class Manager(service_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        self.config = metadata.get_config(_config_type, Config, self.id,
                                          package_name)

    def validate_pre_install(self):
        # iupath.check_installable_to_target_dir(self.config.home_path,
        #                                        self.config.package_name)
        logger.debug("%s instance %s passed pre-install checks." %
                     (self.config.package_name, self.id))
        
    def install(self, package):
        extracted_dir = package.extract(self.config.home_dir_parent, desired_common_dirname=self.config.home_dir)

        # initialize the database
        root_password = install_context.password_repository.get_value(self.config.input_ports.mysql_admin.root_password)
        db_password = install_context.password_repository.get_value(self.config.config_port.database_password)
        call_mysql(self.config,
                   "root", root_password,
                   _mysql_cmds.format(self.config.config_port.database_user,
                                      db_password))

	call_mysql(self.config,
                   self.config.config_port.database_user,
                   db_password,
                   _mysql_createdb.format(self.config.home_path))
        # deploy the war file
        uri = _deploy_req_uri % (self.config.input_ports.tomcat.hostname,
                                 self.config.input_ports.tomcat.manager_port,
                                 self.config.home_path)
        logger.debug("Attempting to deploy agilefant:\nuri=%s" % uri)
        tomcat_password = install_context.password_repository.get_value(self.config.input_ports.tomcat.admin_password)
        result = iuhttp.make_request_with_basic_authentication(uri,
                       _tomcat_mgr_realm,
                       self.config.input_ports.tomcat.admin_user,
                       tomcat_password)
        if result.find(_deploy_rsp)==-1:
            raise AgilefantError(ERR_DEPLOY_RSP, "Install", self.config,
                               developer_msg="Response was: '%s'" % result)

        # write out the init.d startup script
        # we just stick it in the install directory for now and leave it to 
        # the user to manually copy it to /etc/init.d and enable it.
        agilefant_initd_file = iufile.get_data_file_contents(__file__, "agilefant.sh")
        startup_script = agilefant_initd_file % {
                "mysql_install_dir":self.config.input_ports.mysql_admin.install_dir,
                "tomcat_install_dir":self.config.input_ports.tomcat.home,
                "os_user":self.config.input_ports.tomcat.os_user_name
            }
        start_script_filepath = os.path.join(self.config.home_path, "agilefant.sh")
        start_script_file = open(start_script_filepath, "wb")
        start_script_file.write(startup_script)
        start_script_file.close()
        os.chmod(start_script_filepath, 0755)

        # check that everything is now in place
        self.validate_post_install()

    def is_installed(self):
        #return os.path.exists(self.config.home_path)
        return False 

    def validate_post_install(self):
	logger.debug('validate post install')
        if not os.path.exists(self.config.home_path):
            raise AgilefantError(ERR_NO_INSTALL_DIR, "Validate post install",
                               self.config, {"dir":self.config.home_path})
        check_for_agilefant_db(self.config)
        if not os.path.exists(self.config.deployment_target_path):
            raise AgilefantError(ERR_NO_WAR_FILE, "Validate post install",
                               self.config,
                               developer_msg="Expected file at '%s'" %
                                              self.config.deployment_target_path)

    def start(self):
        uri = _start_req_uri % \
            (self.config.input_ports.tomcat.hostname,
             self.config.input_ports.tomcat.manager_port)
        tomcat_password = install_context.password_repository.get_value(self.config.input_ports.tomcat.admin_password)
        try:
            result = iuhttp.make_request_with_basic_authentication(uri,
                       _tomcat_mgr_realm,
                       self.config.input_ports.tomcat.admin_user,
                       tomcat_password)
            if result.find(_start_rsp)==-1:
                raise AgilefantError(ERR_TOMCAT_STARTRSP, "Startup",
                                   self.config,
                                   developer_msg="Response was '%s'" % result)
        except urllib2.URLError, msg:
            raise AgilefantError(ERR_TOMCAT_STARTUP, "Startup", self.config,
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
                raise AgilefantError(ERR_TOMCAT_STOPRSP, "Stop",
                                    self.config,
                                    developer_msg="Response was '%s'" % result)
        except urllib2.URLError, msg:
            raise AgilefantError(ERR_TOMCAT_STOPREQ, "Stop",
                                self.config,
                                developer_msg="URL error was: '%s'" % msg)

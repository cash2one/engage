"""Resource and service manager for trac projects 
"""

import string
import re
import cStringIO
import ConfigParser

import commands
import shutil
import os
import os.path
import tempfile
import sys

import subprocess
import json

import engage.drivers.resource_manager as resource_manager
import engage.drivers.service_manager as service_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.utils.process as iuprocess
import engage.utils.path as iupath
import engage.utils.log_setup
import engage.utils.file as iufile
import engage.utils.http as iuhttp
import engage.engine.install_context as install_context

from engage.drivers.trac.trac_proj_common import TracConfig, get_config_type, ResourceMgrConfigCommon, BaseResourceMgr

from engage.utils.user_error import UserError, ScriptErrInf, convert_exc_to_user_error
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("trac-project", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_TRAC = 1
ERR_TRACD_NOT_RUNNING = 2
ERR_TRAC_INI_NOT_FOUND = 3
ERR_TRACADMIN_FAILURE = 4
ERR_TRAC_DEPLOY = 5
ERR_TRACD_STARTUP = 6
ERR_TRACD_STOP_ERROR = 7
ERR_TRAC_APACHE_CONFIG_FILE_EXISTS=8
ERR_TRAC_SUDO_CALL=9

define_error(ERR_TRAC,
             _("error installing Trac using easy_install"))
define_error(ERR_TRACD_NOT_RUNNING,
             _("Attempt to stop trac daemon: not running"))
define_error(ERR_TRAC_INI_NOT_FOUND,
             _("Configuration file trac.ini not found"))
define_error(ERR_TRACADMIN_FAILURE,
             _("Failure running trac-admin"))
define_error(ERR_TRAC_DEPLOY,
             _("Failure deploying trac project: trac-admin failed"))
define_error(ERR_TRACD_STARTUP,
             _("Error in starting tracd server"))
define_error(ERR_TRACD_STOP_ERROR,
             _("Error in stopping tracd server"))
define_error(ERR_TRAC_APACHE_CONFIG_FILE_EXISTS,
             _("Apache configuration file already exists. Please remove and try again."))
define_error(ERR_TRAC_SUDO_CALL,
             _("An operation failed when run under sudo. Perhaps the sudo password is incorrect."))

logger = engage.utils.log_setup.setup_script_logger("trac-project")


class Config(ResourceMgrConfigCommon):
    """We get the configuration data from the common class. Any project-specific
    configuration can be added in the __init__() method via self.__add_computed_prop()
    """
    def __init__(self, props_in, types, id, package_name):
        ResourceMgrConfigCommon.__init__(self, props_in, types, id, package_name)



class Manager(BaseResourceMgr):
    def __init__(self, metadata):
        BaseResourceMgr.__init__(self, metadata, get_config_type(), Config)

    def install(self, download_url):
	logger.debug("installing trac project %s" % self.config.projectname )
        # get the passwords that we will need from the repository
        sudo_password = \
            install_context.password_repository.get_value(self.config.sudo_password)
        admin_password = \
            install_context.password_repository.get_value(self.config.admin_password)
        try:
            trac_admin_exe = os.path.join(self.config.trachome, "bin/trac-admin")
            rc = iuprocess.run_and_log_program([trac_admin_exe, self.config.projecthome, "initenv", 
                                                self.config.projectname,
                                                self.config.projectdb,
                                                self.config.version_control,
                                                self.config.repository],
                                                   {}, logger, None, None)
            if rc != 0:
                raise UserError(errors[ERR_TRACADMIN_FAILURE])
            logger.debug("trac-admin ran successfully.")
	    permissions = [ "BROWSER_VIEW",
			    "CHANGESET_VIEW",
			    "FILE_VIEW",
			    "LOG_VIEW",
			    "MILESTONE_VIEW",
			    "REPORT_SQL_VIEW",
			    "REPORT_VIEW",
			    "ROADMAP_VIEW",
			    "SEARCH_VIEW",
			    "TICKET_CREATE",
			    "TICKET_APPEND",
			    "TICKET_MODIFY",
			    "TICKET_VIEW",
			    "TIMELINE_VIEW",
			    "WIKI_CREATE",
			    "WIKI_MODIFY",
			    "WIKI_DELETE",
			    "WIKI_VIEW" ]
	    # drop permissions for anonymous
            rc = iuprocess.run_and_log_program([trac_admin_exe, self.config.projecthome, 
                                                "permission", "remove", "anonymous"] + permissions, 
						{}, logger, None, None)
            if rc != 0:
                raise UserError(errors[ERR_TRACADMIN_FAILURE])
            logger.debug("trac-admin removed permissions for anonymous.")
	    # add permissions for authenticated
            iuprocess.run_and_log_program([trac_admin_exe, self.config.projecthome, 
                                                "permission", "remove", "authenticated", '*'],
						{}, logger, None, None)
            rc = iuprocess.run_and_log_program([trac_admin_exe, self.config.projecthome, 
                                                "permission", "add", "authenticated"] + permissions, 
						{}, logger, None, None)
            logger.debug("trac-admin added permissions for authenticated.")
            # now add permission for admin user
            rc = iuprocess.run_and_log_program([trac_admin_exe, self.config.projecthome, "permission", "add",
                                           self.config.administrator, "TRAC_ADMIN"],
                                          {}, logger, None, None)
            logger.debug("trac-admin added permissions successfully.")
            if os.path.exists(self.config.password_file) == False:
               # set up the password file and add admin with initial password
               logger.debug("about to make password file")
               # TODO: htpasswd_exe is the program installed with Apache to create/update passwords.
               # This causes us to have an implicit dependency on apache. Need to figure out
               # a way to remove this dependency. Perhaps we can provide generic methods on the webserver
               # service class or in the engage.utils package.
               htpasswd_exe = self.config.input_ports.webserver.htpasswd_exe
               rc = iuprocess.run_and_log_program([htpasswd_exe, "-cbm", self.config.password_file,
                                                   self.config.administrator, admin_password], 
                                                  {}, logger, None, None)
            else: 
               pass # XXX: check user administrator exists
            trac_ini_file = os.path.abspath(os.path.join(self.config.projecthome, "conf/trac.ini"))
            logger.debug("Looking for ini file " + trac_ini_file)
            if os.path.exists(trac_ini_file) == False:
            	raise UserError(errors[ERR_TRAC_INI_NOT_FOUND])
	     
            # now hack the trac.ini file for git plugin
            if self.config.version_control == "git":
                trac_ini_file_changed = trac_ini_file + ".changed" 
                git_bin = self.config.input_ports.repository.git_exe
                escaped_git_bin = string.replace(git_bin, "/", "\/")
                logger.debug("git path is " + git_bin)
                f = open(trac_ini_file, "r")
                (tmpf, tmpn) = tempfile.mkstemp()
                for line in f :
                   cline = line.replace("cached_repository = false", "cached_repository = true")
                   cline = cline.replace("persistent_cache = false", "persistent_cache = true")
                   cline = re.sub("git_bin = .*$", "git_bin = " + git_bin, cline)
                   os.write(tmpf, cline)
                os.write(tmpf, "[components]\ntracext.git.* = enabled\n");
                f.close()
                os.close(tmpf)
                shutil.copyfile(tmpn, trac_ini_file) 

            cfg = TracConfig(trac_ini_file)
            # basic setup
            cfg.update("trac", "base_url", self.get_base_url())
	    # set up notification
	    # By default, use SMTP
	    # See http://trac.edgewall.org/wiki/TracNotification 
	    notification_string = self.config.get_smtp_notification_string()
	    cfg.set_config(json.loads(notification_string))
            #plugins
            logger.debug(self.config.acctmgrconf)
	    conf = json.loads((self.config.acctmgrconf).__str__())
	    logger.debug(conf)
	    cfg.set_config(conf) 
	    cfg.update("account-manager", "password_file", self.config.password_file)
	    # disable new users registering on the web
	    cfg.update("components", "acct_mgr.web_ui.registrationmodule", "disabled")
            logger.debug(self.config.gitpluginconf)
	    conf = json.loads((self.config.gitpluginconf).__str__())
	    cfg.set_config(conf) 
            logger.debug(self.config.iniadminconf)
	    conf = json.loads((self.config.iniadminconf).__str__())
	    cfg.set_config(conf) 
            logger.debug(self.config.themeengineconf)
	    conf = json.loads((self.config.themeengineconf).__str__())
	    cfg.set_config(conf) 
            logger.debug(self.config.permredirectconf)
            conf = json.loads((self.config.permredirectconf).__str__())
            cfg.set_config(conf)
            logger.debug(self.config.gfdownloadconf)
            conf = json.loads((self.config.gfdownloadconf).__str__())
            cfg.set_config(conf)

                    
            menu_string = self.config.get_menu_string()
            menu_f = cStringIO.StringIO(menu_string)
            menu_cfg = ConfigParser.SafeConfigParser()
            menu_cfg.readfp(menu_f)
            menu_f.close()
            for section in menu_cfg.sections():
                for (menuname, menuval) in menu_cfg.items(section):
                    cfg.update(section, menuname, menuval) 


	    cfg.writeback()
            logger.debug("Done updating trac.ini file")
	    # upgrade trac environment
            rc = iuprocess.run_and_log_program([trac_admin_exe, self.config.projecthome,
                                                "upgrade"],
                                                {}, logger, None, None)
            if rc != 0:
            	raise UserError(errors[ERR_TRAC_DEPLOY])

            # set up Apache + Fastcgi
            if self.config.webserver == "apache-fastcgi" :
                logger.debug("setting up apache fastcgi")
                # trac deploy
                # make fastcgi config file
                rc = iuprocess.run_and_log_program([trac_admin_exe, self.config.projecthome,
                                                    "deploy",
                                                    os.path.join(self.config.projecthome, "www")],
                                                   {}, logger, None, None)
                if rc != 0:
                    raise UserError(errors[ERR_TRAC_DEPLOY])
                fcgi_config_file_path = os.path.join(self.config.additional_config_dir,
                                                     self.config.projectname + ".conf")
                if os.path.exists(fcgi_config_file_path):
                   logger.warn("Apache configuration file already exists. Will be overwritten.")
                httpd_config_string = self.config.get_httpd_config_string([("TRAC_ENV", self.config.projecthome)])
                (tmpf, tmpn) = tempfile.mkstemp()
                os.write(tmpf, httpd_config_string)
                if self.config.protocol == "https":
                       https_config_string = self.config.get_https_config_string()
                       os.write(tmpf, https_config_string)
                os.close(tmpf)
                iuprocess.sudo_copy([tmpn,
                                     fcgi_config_file_path],
                                     sudo_password, logger)

                self._update_and_copy_fcgi_file(sudo_password)

                # make sure the project directory is writeable by apache user
                iuprocess.sudo_chown(self.config.input_ports.webserver.apache_user,
                                     [self.config.projecthome], sudo_password, logger, recursive=True)
                # XXX: hack: need to fix. tracd runs as current user and needs access to log directory
                # but apache does not
                iuprocess.sudo_chown(os.environ["LOGNAME"], [self.config.logdir], sudo_password, logger,
                                     recursive=True)
                logger.debug("Done installing httpd configuration files")
        except iuprocess.SudoError, e:
            exc_info = sys.exc_info()
            sys.exc_clear()
            raise convert_exc_to_user_error(exc_info, errors[ERR_TRAC_SUDO_CALL],
                                            nested_exc_info=e.get_nested_exc_info())


# The following code was left over from when we used tracd instead of Apache. If we ever
# want to use tracd again, we should split this into a separate tracd service.
#     def start(self):
#         sudo_askpass = self.config.trachome + "/bin/askpass"
# 	hostname = self.config.tracdhost
# 	port = self.config.tracdport
# 	projectpath = self.config.projecthome
# 	tracd = os.path.join(os.path.join(self.config.trachome,"bin"), "tracd")
# 	sport = repr(port)
#         process = iuprocess.run_server([tracd, "--hostname", hostname, "-p", sport,
#                                         projectpath],
#                                        { "SUDO_ASKPASS" : sudo_askpass }, self.config.tracd_stdout,
#                                        logger, self.config.pidfile)
#         rc = process.poll()
#         if rc!=None or iuprocess.is_process_alive(process.pid)==False:
#             raise UserError(errors[ERR_TRACD_STARTUP],
#                             developer_msg="return code %d" % rc)
#
#        
#     def stop(self):
#         pid = iuprocess.check_server_status(self.config.pidfile)
#         if pid != None:
#             try:
#         	os.kill(pid)
#             except:
# 		raise UserError(errors[ERR_TRACD_STOP_ERROR],
#                                 developer_msg="pid %d" % pid)
#         else: # eventually this should just log the fact that trac isn't started
#             # and return without raising an error
#             raise UserError(errors[ERR_TRACD_NOT_RUNNING])

#     def is_running(self):
# 	"""Check if there is a trac process running by using its pidfile"""
# 	return iuprocess.check_server_status(self.config.pidfile, logger,
#                                              self.id) != None
	

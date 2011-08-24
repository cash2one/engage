"""Common code for trac project-related resource managers.
Currently used in trac_project and trac_pm (project manager).
"""

import ConfigParser
import copy
import os
import os.path


import engage.drivers.resource_manager as resource_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.utils.log_setup
import engage.utils.process as iuprocess
import engage.utils.file as iufile


logger = engage.utils.log_setup.setup_script_logger("trac_proj_common")

from engage.utils.user_error import UserError, ScriptErrInf, convert_exc_to_user_error
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("trac_proj_common", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_TRAC_FCGI_SETUP = 1


define_error(ERR_TRAC_FCGI_SETUP,
             _("An error occurred when configuring fcgi for trac"))



class TracConfig:    
    """Representation of Trac configurtion file
    """
    def __init__(self, configfile):
        self.configfile = configfile 
        self.config = ConfigParser.SafeConfigParser()
        readfiles = self.config.read([configfile])
        if configfile not in readfiles :
            raise FileNotFound(configfile)
  
    def update (self, section, option, val):
        if not (self.config.has_section(section)):
            self.config.add_section(section)
        self.config.set(section, option, val)
  

    def writeback (self): 
        with open(self.configfile, 'wb') as cfile:
            self.config.write(cfile) 

    def set_config(self, jdata):
        for sec in jdata:
            for op in jdata[sec]:
                self.update(sec, op, jdata[sec][op])
   

_config_type = {
    "config_port": {
	"projectname": unicode,
	"projecthome": unicode,
	"projectdb": unicode,
        "version_control" : unicode,
#        "repository" : unicode,
        "password_file" : unicode,
        "administrator" : unicode,
        "admin_password" : unicode,
        "protocol" : unicode,
        "host" :  unicode,
        "port" : int
    },
    "input_ports" : {
        "trachome" : { "trachome" : unicode, "python_exe": unicode },
        "repository": {"repo": unicode, "git_exe": unicode},
        "host": { "sudo_password": unicode, "cpu_arch": unicode, "os_type": unicode },
        "webserver": {
            "config_file": unicode,
            "additional_config_dir": unicode,
            "cgi_dir": unicode,
            "htpasswd_exe": unicode,
            "apache_user": unicode
        }
    }
}


def get_config_type():
    """Return the metadata describing the expected properties
    for the config, input, and output ports of the associated
    resource. We make a deep copy so that individual resource
    managers can add any properties that are specific to that
    project type.
    """
    return copy.deepcopy(_config_type)


_httpd_config_string_fcgi = \
"""<IfModule !fastcgi_module>
 <IfModule mod_fastcgi.c>
  AddHandler fastcgi-script .fcgi
  FastCgiIpcDir /var/lib/apache2/fastcgi
 </IfModule>
  LoadModule fastcgi_module %(module_lib)s
</IfModule>
%(env_vars)s
ScriptAlias /%(projectname)s %(cgidir)s/%(projectname)s.fcgi
"""

_httpd_config_string_fcgid = \
"""
%(env_vars)s
ScriptAlias /%(projectname)s %(cgidir)s/%(projectname)s.fcgi
"""

_https_config_string = \
"""

<Location "/%(projectname)s">
 SetEnv TRAC_ENV "%(projecthome)s"
 SSLRequireSSL
 #AuthType Basic
 #AuthName "Login for trac project: %(projectname)s"
 #AuthUserFile "%(pwfile)s"
 #Require valid-user
</Location>
"""

_smtp_notification_string = \
"""
{ "trac" : { "base_url" : "%(url)s" },
  "notification" : {
    "smtp_enabled" : "true",
    "mime_encoding": "base64",
    "smtp_server"  : "%(smtp_server)s", 
    "smtp_port"  : "%(smtp_server_port)s", 
    "smtp_from"    : "%(email)s",
    "smtp_replyto" : "%(email)s", 
    "use_tls"      : "true",
    "smtp_user"    : "%(user)s",
    "smtp_password": "%(password)s"
  }
}
"""

_menu_string = \
"""
[components]
tracmenus.web_ui.menumanagermodule = enabled

[mainnav] 
tags = disabled
genforma = disabled
search = disabled
timeline = disabled
roadmap = disabled

home = enabled
home.href = /
home.label = Home
home.parent = top
home.order = 10

wiki.label = Wiki
wiki.order = 20

wiki_newpage = enabled
wiki_newpage.href = /wiki/newpage
wiki_newpage.parent = wiki
wiki_newpage.label = New Wiki Page
wiki_newpage.order = 1

wiki_titleindex = enabled
wiki_titleindex.href = /wiki/TitleIndex
wiki_titleindex.label = Wiki Index
wiki_titleindex.parent = wiki
wiki_titleindex.order = 2

wiki_timeline = enabled
wiki_timeline.href = /timeline?wiki=on
wiki_timeline.label = Recent Changes
wiki_timeline.parent = wiki
wiki_timeline.order = 3

ticketgrp = enabled
ticketgrp.href = /report
ticketgrp.label = Tickets
ticketgrp.order = 30
ticketgrp.parent = top
ticketgrp.hide_if_no_children = true

tickets.parent = ticketgrp
tickets.order = 1
tickets.label = View Reports

newticket.parent = ticketgrp
newticket.order = 2


ticket_defect = enabled
ticket_defect.href = /newticket?type=defect
ticket_defect.parent = newticket
ticket_defect.label = New Defect
ticket_defect.order = 1

ticket_enhancement = enabled
ticket_enhancement.href = /newticket?type=enhancement
ticket_enhancement.parent = newticket
ticket_enhancement.label = New Enhancement
ticket_enhancement.order = 2

ticket_task = enabled
ticket_task.href = /newticket?type=task
ticket_task.parent = newticket
ticket_task.label = New Task
ticket_task.order = 3

ticket_timeline = enabled
ticket_timeline.href = /timeline?ticket=on
ticket_timeline.label = Recent Changes
ticket_timeline.parent = ticketgrp
ticket_timeline.order = 4
ticket_timeline.perm = TICKET_VIEW

#query = enabled
#query.href = /query
#query.label = Custom Query
#query.parent = ticketgrp
#query.order = 3

browsergrp = enabled
browsergrp.parent = top
browsergrp.href = /browser
browsergrp.label = Code
browsergrp.order = 40
browsergrp.hide_if_no_children = true

browser.label = Browse Repository
browser.parent = browsergrp
browser.order = 10
browser.perm = BROWSER_VIEW

browser_log = enabled
browser_log.label = Revision Log
browser_log.href = /log
browser_log.parent = browsergrp
browser_log.order = 20
browser_log.perm = LOG_VIEW


browser_timeline = enabled
browser_timeline.label = Recent Changes
browser_timeline.href = /timeline?changeset=on
browser_timeline.parent = browsergrp
browser_timeline.order = 30
browser_timeline.perm = CHANGESET_VIEW

download = enabled
download.label = Download Sources
download.href = /download
download.parent = browsergrp
download.order = 30
download.perm = TRAC_ADMIN

processgrp = enabled
processgrp.href = #
processgrp.label = Management
processgrp.order = 70
processgrp.parent = top
processgrp.hide_if_no_children = true

process_gfapp = enabled
process_gfapp.label = ProjectManager
process_gfapp.href = /genforma
process_gfapp.parent = processgrp
process_gfapp.order = 1
process_gfapp.perm = TRAC_ADMIN

process_roadmap = enabled
process_roadmap.label = Roadmap
process_roadmap.href = /roadmap
process_roadmap.parent = processgrp
process_roadmap.order = 2
process_roadmap.perm = ROADMAP_VIEW

process_timeline = enabled
process_timeline.label = Timeline
process_timeline.href = /timeline
process_timeline.parent = processgrp
process_timeline.order = 3
process_timeline.perm = TIMELINE_VIEW

tools = enabled
tools.href = #
tools.label = Team Tools
tools.order = 60
tools.parent = top
tools.hide_if_no_children = true
"""


class ResourceMgrConfigCommon(resource_metadata.Config):
    """Class representing common configuration data from resource manager
    """
    def __init__(self, props_in, types, id, package_name):
        resource_metadata.Config.__init__(self, props_in, types)
        self._add_computed_prop("id", id)
        self._add_computed_prop("package_name", package_name)
	self._add_computed_prop("projectname", self.config_port.projectname)
	self._add_computed_prop("projecthome", os.path.abspath(self.config_port.projecthome))
	self._add_computed_prop("projectdb", self.config_port.projectdb)
	self._add_computed_prop("version_control", self.config_port.version_control)
	self._add_computed_prop("repository", self.config_port.repository)
	self._add_computed_prop("password_file", os.path.abspath(self.config_port.password_file))
	self._add_computed_prop("administrator", self.config_port.administrator)
	self._add_computed_prop("admin_password", self.config_port.admin_password)
	self._add_computed_prop("smtp_server", self.config_port.smtp_server)
	self._add_computed_prop("smtp_server_port", self.config_port.smtp_server_port)
	self._add_computed_prop("smtp_user", self.config_port.smtp_user)
	self._add_computed_prop("smtp_password", self.config_port.smtp_password)

	#self._add_computed_prop("webserver", "tracd")
	#self._add_computed_prop("webserver", "apache-cgi")
	self._add_computed_prop("webserver", "apache-fastcgi")
	self._add_computed_prop("protocol", self.config_port.protocol) # http or https

	#self._add_computed_prop("tracdhost", self.config_port.tracdhost)
	#self._add_computed_prop("tracdport", self.config_port.tracdport)
	self._add_computed_prop("host", self.config_port.host)
	self._add_computed_prop("port", self.config_port.port)

	self._add_computed_prop("trachome", self.input_ports.trachome.trachome)
	self._add_computed_prop("config_file", self.input_ports.webserver.config_file)
	self._add_computed_prop("sudo_password", self.input_ports.host.sudo_password)
	self._add_computed_prop("cpu_arch", self.input_ports.host.cpu_arch)
	self._add_computed_prop("os_type", self.input_ports.host.os_type)
	self._add_computed_prop("additional_config_dir", self.input_ports.webserver.additional_config_dir)
	self._add_computed_prop("cgi_dir", self.input_ports.webserver.cgi_dir)
        self._add_computed_prop("module_lib", self.input_ports.webserver.module_lib)
        logdir = os.path.join(self.projecthome, "log")
        self._add_computed_prop("logdir", logdir)
        self._add_computed_prop("pidfile", os.path.join(logdir, "tracd.pid"))
        self._add_computed_prop("tracd_stdout", os.path.join(logdir, "tracd.stdout"))

        # for 64-bit linux the standard fcgi apache module isn't available
        self._add_computed_prop("use_mod_fcgid",
                                self.os_type=="linux")

        # plugins
        self._add_computed_prop("gitpluginconf", self.input_ports.gitpluginconf.ini)
        self._add_computed_prop("acctmgrconf", self.input_ports.acctmgrconf.ini)
        self._add_computed_prop("iniadminconf", self.input_ports.iniadminconf.ini)
        self._add_computed_prop("themeengineconf", self.input_ports.themeengineconf.ini)
        self._add_computed_prop("permredirectconf", self.input_ports.permredirectconf.ini)
        self._add_computed_prop("gfdownloadconf", self.input_ports.gfdownloadconf.ini)
        self._add_computed_prop("gfappconf", self.input_ports.gfappconf.ini)

    def _build_fcgi_env_vars(self, fcgi_env_vars):
        if len(fcgi_env_vars) == 0:
            return ""
        if not self.use_mod_fcgid: # normal case, just using fcgi
            return "FastCGIConfig " + \
                   " ".join("-initial-env %s=%s" % (var, val) for (var, val) in fcgi_env_vars)
        else:
            return "\n".join("DefaultInitEnv %s %s" % (var, val) for (var, val) in fcgi_env_vars)

    def get_httpd_config_string(self, fcgi_env_vars):
        """Return the instantiated apache configuration string for use with the
        fcgi/fcgid module, This goes in the trac-project-specific apache
        configuration file (e.g. GF.conf). fcgi_env_vars is a list of key,value
        pairs.
        """
        if not self.use_mod_fcgid: # normal case, just using fcgi
            return _httpd_config_string_fcgi % {"projecthome":self.projecthome,
                                                "projectname":self.projectname,
                                                "cgidir":self.cgi_dir,
                                                "module_lib":self.module_lib,
                                                "env_vars":self._build_fcgi_env_vars(fcgi_env_vars)}
        else:
            return _httpd_config_string_fcgid % \
                {"projecthome":self.projecthome,
                 "projectname":self.projectname,
                 "cgidir":self.cgi_dir,
                 "module_lib":self.module_lib,
                 "env_vars":self._build_fcgi_env_vars(fcgi_env_vars)}

    def get_https_config_string(self):
        return _https_config_string % \
            {"projectname":self.projectname,
             "projecthome":self.projecthome,
             "pwfile":self.password_file}

    def get_base_url(self):
        if (self.port==80 and self.protocol=="http") or \
           (self.port==443 and self.protocol=="https"):
            url = "%s://%s/%s" % (self.protocol, self.host, self.projectname)
        else:
            url = "%s://%s:%d/%s" % (self.protocol, self.host, self.port,
                                     self.projectname)
        return url

    def get_smtp_notification_string(self):
        # See http://trac.edgewall.org/wiki/TracNotification
        url = self.get_base_url()
        return _smtp_notification_string % \
                {"url":url,
                 "smtp_server":self.smtp_server,
                 "smtp_server_port":self.smtp_server_port,
                 "email":self.smtp_user,
                 "user":self.smtp_user,
                 "password":self.smtp_password}

    def get_menu_string(self):
	return _menu_string


class BaseResourceMgr(resource_manager.Manager):
    """Shared code for resource managers.
    """
    def __init__(self, metadata, config_type, config_class):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.config = metadata.get_config(config_type, config_class, self.id, package_name) 

    def validate_pre_install(self):
        # Should eventually write code to check that projecthome is valid, etc.
        pass

    def is_installed(self):
	if os.path.exists(self.config.projecthome) == True:
            return True
	else:
            return False

    def validate_post_install(self):
	pass

    def _update_and_copy_fcgi_file(self, sudo_password):
        # Run during install.
        # We need to update the fcgi file to refer to the virtualenv copy
        # of python
        fcgi_src_file = os.path.abspath(os.path.join(self.config.projecthome,
                                                     "www/cgi-bin/trac.fcgi"))
        rc = iufile.subst_in_file(fcgi_src_file,
                                  [('\\#\\!\\/usr\\/bin\\/python', '#!' + self.config.input_ports.trachome.python_exe)])
        if (rc != 1) and (rc != 0):
            raise UserError(errors[ERR_TRAC_FCGI_SETUP],
                            developer_msg="Unable to substitute python executable %s in fcgi script %s" %
                            (self.config.input_ports.trachome.python_exe, fcgi_src_file))

        # cp fcgi file to cgi-executables directory
        iuprocess.sudo_copy([fcgi_src_file,
                             os.path.join(self.config.cgi_dir,
                                          self.config.projectname + ".fcgi")],
                            sudo_password, logger)
        iuprocess.sudo_chmod("+x",
                             [os.path.join(self.config.cgi_dir, self.config.projectname + ".fcgi")],
                             sudo_password, logger)


"""Resource manager for apache-tomcat 6.0

"""

# Common stdlib imports
import sys
import os
import os.path
import re
## import commands

# fix path if necessary (if running from source or running as test)
try:
    import engage.utils
except:
    sys.exc_clear()
    dir_to_add_to_python_path = os.path.abspath((os.path.join(os.path.dirname(__file__), "../../../..")))
    sys.path.append(dir_to_add_to_python_path)

import engage.drivers.service_manager as service_manager
import engage.drivers.utils
from engage.drivers.password_repo_mixin import PasswordRepoMixin
# Drivers compose *actions* to implement their methods.
from engage.drivers.action import *
from engage.drivers.action import _check_file_exists
import engage.utils.process as procutils
import engage.utils.file as fileutils
import engage.utils.http as httputils
import engage.drivers.genforma.tomcat_utils as tomcat_utils

# setup errors
from engage.utils.user_error import UserError, EngageErrInf
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_PORT_TAKEN     = 1
ERR_STARTUP_FAILED = 2
ERR_PORT_SUBST     = 3

define_error(ERR_PORT_TAKEN,
             _("%(id)s (Apache Tomcat) unable to start - port %(port)d is already in use"))
define_error(ERR_STARTUP_FAILED,
             _("Startup of %(id)s failed, see logfile %(log)s for details"))
define_error(ERR_PORT_SUBST,
             _("Unable to substitute port number in apache tomcat configuration file %(file)s. Attempted to replace port 8080 with %(port)d."))


# setup logging
from engage.utils.log_setup import setup_engage_logger
logger = setup_engage_logger(__name__)


# this is used by the package manager to locate the packages.json
# file associated with the driver
def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)

def make_context(resource_json, sudo_password_fn, dry_run=False):
    """Create a Context object (defined in engage.utils.action). This contains
    the resource's metadata in ctx.props, references to the logger and sudo
    password function, and various helper functions. The context object is used
    by individual actions.

    If your resource does not need the sudo password, you can just pass in
    None for sudo_password_fn.
    """
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=sudo_password_fn,
                  dry_run=dry_run)
    ctx.check_port('config_port',
                  home=unicode,
                  gui_admin_user=unicode,
                  gui_admin_password=unicode,
                  admin_user=unicode,
                  admin_password=unicode,
                  manager_port=int,
                  pid_file=unicode)
    ctx.check_port('input_ports.host',
                  genforma_home=unicode,
                  cpu_arch=unicode,
                  os_type=unicode,
                  hostname=unicode,
                  os_user_name=unicode)
    ctx.check_port('input_ports.jvm',
                  home=unicode,
                  type=unicode)
    ctx.check_port('output_ports.tomcat',
                  admin_user=unicode,
                  environment_vars=list,
                  genforma_home=unicode,
                  os_user_name=unicode,
                  hostname=unicode,
                  admin_password=unicode,
                  home=unicode,
                  manager_port=int,
                  pid_file=unicode)

    # add any extra computed properties here using the ctx.add() method.
    p = ctx.props
    ctx.add("tomcat_users_file", os.path.join(p.config_port.home,
                                              "conf/tomcat-users.xml"))
    ctx.add("tomcat_server_file", os.path.join(p.config_port.home,
                                               "conf/server.xml"))
    bin_dir = os.path.join(p.config_port.home, "bin")
    ctx.add("startup_script", os.path.join(bin_dir, "startup.sh"))
    ctx.add("shutdown_script", os.path.join(bin_dir, "shutdown.sh"))
    ctx.add("catalina_out_log", os.path.join(p.config_port.home,
                                             "logs/catalina.out"))
    env_mapping = {"CATALINA_HOME":p.config_port.home}
    if p.input_ports.jvm.type=="jdk":
        env_mapping["JAVA_HOME"] = p.input_ports.jvm.home
    else:
        env_mapping["JRE_HOME"] = p.input_ports.jvm.home
    env_mapping["CATALINA_PID"] = p.config_port.pid_file
    for env_var_def in p.output_ports.tomcat.environment_vars:
        env_mapping[env_var_def.name] = env_var_def.value
    ctx.add("env_mapping", env_mapping)
    ctx.add("setclasspath_file",
            os.path.join(p.config_port.home, "bin/setclasspath.sh"))
    return ctx


tomcat_users_xml = """
<tomcat-users>
 <role rolename="manager-gui"/>
 <role rolename="manager-script"/>
 <user username="${config_port.gui_admin_user}" password="${gui_pw_value}" roles="manager-gui"/>
 <user username="${config_port.admin_user}" password="${admin_pw_value}" roles="manager-script"/>
</tomcat-users>
"""

STATUS_RUNNING    = "running"
STATUS_NORESPONSE = "noresponse"
STATUS_STOPPED    = "stoppped"

DEFAULT_MANAGER_PORT = 8080


    
@make_action
def set_tomcat_user_file_perms(self, user_file_path):
    """Set the user file permissions to be unreadable to other
    users (the file contains passwords!).
    """
    os.chmod(user_file_path, 0600)

@make_action
def add_environment_vars_to_classpath(self, classpath_file, env_mapping):
    _check_file_exists(classpath_file, self)
    backup_file = classpath_file + ".orig"
    if not os.path.exists(backup_file):
        shutil.copyfile(classpath_file, backup_file)
    assignments = ""
    for (var, value) in env_mapping.items():
        assignments += '%s="%s"\n' % (var, value)
    with open(classpath_file, "a") as f:
        f.write(assignments)

        
# Now, define the main resource manager class for the driver. If this driver is
# a service, inherit from service_manager.Manager instead of
# resource_manager.Manager. If you need the sudo password, add
# PasswordRepoMixin to the inheritance list.
#
class Manager(service_manager.Manager, PasswordRepoMixin):
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(),
                                None, # self._get_sudo_password,
                                dry_run=dry_run)

    def validate_pre_install(self):
        p = self.ctx.props
        self.ctx.r(check_installable_to_dir, p.config_port.home)

    def is_installed(self):
        os.path.exists(self.ctx.props.config_port.home)

    def install(self, package):
        p = self.ctx.props
        r = self.ctx.r
        rv = self.ctx.rv
        # We have to lookup the password values now vs. in make_context()
        # because the install_context member isn't set up until after
        # the constructor has run.
        self.ctx.add("admin_pw_value",
                     self._get_password(self.ctx.props.config_port.admin_password))
        self.ctx.add("gui_pw_value",
                     self._get_password(self.ctx.props.config_port.gui_admin_password))
        r(extract_package_as_dir, package, p.config_port.home)
        r(move_old_file_version, p.tomcat_users_file,
          leave_old_backup_file=True)
        r(instantiate_template_str, tomcat_users_xml,
          p.tomcat_users_file)
        r(set_tomcat_user_file_perms, p.tomcat_users_file)
        if p.config_port.manager_port != DEFAULT_MANAGER_PORT:
            cnt = rv(subst_in_file, p.tomcat_server_file,
                     [(re.escape('<Connector port="8080" protocol="HTTP/1.1"'),
                       '<Connector port="%d" protocol="HTTP/1.1"' %
                       p.config_port.manager_port)])
            if cnt != 1:
                raise UserError(ERR_PORT_SUBST,
                                msg_args={"file":p.tomcat_server_file,
                                          "port":p.config_port.manager_port})
        r(add_environment_vars_to_classpath, p.setclasspath_file,
          p.env_mapping)                               

    def validate_post_install(self):
        p = self.ctx.props
        self.ctx.r(check_dir_exists,  p.config_port.home)

    def start(self):
        tomcat_utils.ensure_tomcat_running(self.ctx,
                                           self.ctx.props.output_ports.tomcat)

    def stop(self):
        tomcat_utils.ensure_tomcat_stopped(self.ctx,
                                           self.ctx.props.output_ports.tomcat)

    def is_running(self):
        p = self.ctx.props
        return self.ctx.rv(get_server_status, p.config_port.pid_file)!=None

    def get_pid_file_path(self):
        return self.ctx.props.config_port.pid_file

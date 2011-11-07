
"""Resource manager for jasper-reports-server 4.2 
"""

# Common stdlib imports
import sys
import os
import os.path
import shutil
import re

# fix path if necessary (if running from source or running as test)
try:
    import engage.utils
except:
    sys.exc_clear()
    dir_to_add_to_python_path = os.path.abspath((os.path.join(os.path.dirname(__file__), "../../../..")))
    sys.path.append(dir_to_add_to_python_path)

import engage.drivers.service_manager as service_manager
from engage.drivers.password_repo_mixin import PasswordRepoMixin
import engage.drivers.utils
# Drivers compose *actions* to implement their methods.
from engage.drivers.action import *
from engage.drivers.action import _check_file_exists
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
# FILL IN
ERR_TBD = 0

define_error(ERR_TBD,
             _("Replace this with your error codes"))


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
                  home=unicode)
    ctx.check_port('input_ports.jdbc_driver_file',
                  jar_file_path=unicode)
    ctx.check_port('input_ports.mysql_admin',
                  admin_password=unicode)
    ctx.check_port('input_ports.tomcat',
                  admin_user=unicode,
                  genforma_home=unicode,
                  hostname=unicode,
                  admin_password=unicode,
                  home=unicode,
                  manager_port=int,
                  pid_file=unicode)
    ctx.check_port('input_ports.mysql',
                  host=unicode,
                  port=int)
    ctx.check_port('output_ports.jasper_server',
                  url=unicode,
                  app_path=unicode)

    # add any extra computed properties here using the ctx.add() method.
    p = ctx.props
    ctx.add("jdbc_target_path",
            os.path.join(os.path.join(p.config_port.home,
                                     "buildomatic/conf_source/db/mysql/jdbc"),
                        os.path.basename(p.input_ports.jdbc_driver_file.jar_file_path)))
    ctx.add("template_properties_file",
            os.path.join(p.config_port.home,
                         "buildomatic/sample_conf/mysql_master.properties"))
    ctx.add("properties_file",
            os.path.join(p.config_port.home,
                         "buildomatic/default_master.properties"))
    ctx.add("install_shell_script",
            os.path.join(p.config_port.home,
                         "buildomatic/js-install-ce.sh"))
    return ctx


class copy_file(Action):
    NAME = "copy_file"
    def __init__(self, ctx):
        super(copy_file, self).__init__(ctx)

    def run(self, src, dest):
        _check_file_exists(src, self)
        shutil.copyfile(src, dest)

    def dry_run(self, src, dest):
        pass

class Manager(service_manager.Manager, PasswordRepoMixin):
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(),
                                None, #self._get_sudo_password,
                                dry_run=dry_run)

    def validate_pre_install(self):
        p = self.ctx.props
        self.ctx.r(check_installable_to_dir, p.config_port.home)

    def is_installed(self):
        return os.path.exists(self.ctx.props.config_port.home)

    def install(self, package):
        p = self.ctx.props
        r = self.ctx.r
        rv = self.ctx.rv
        # Unfortunately, Python's built-in unzip does not seem
        # to preserve executable permissions. We need those permissions
        # for the shell scripts we're going to run. As a workaround,
        # we'll call out to the os's unzip call.
        ## r(extract_package_as_dir, package, p.config_port.home)
        parent_dir = os.path.dirname(p.config_port.home)
        r(run_program, ["/usr/bin/unzip", package.get_file()],
          cwd=parent_dir)
        JASPER_EXTRACTED_DIR="jasperreports-server-cp-4.2.1-bin"
        if JASPER_EXTRACTED_DIR!=os.path.basename(p.config_port.home) and \
           not self.ctx.dry_run:
            os.rename(os.path.join(parent_dir, JASPER_EXTRACTED_DIR),
                      p.config_port.home)

        r(copy_file, p.input_ports.jdbc_driver_file.jar_file_path,
          p.jdbc_target_path)
        r(copy_file, p.template_properties_file,
          p.properties_file)
        esc = re.escape
        replacements = [
            (esc(r"appServerDir = C:\\Program Files\\Apache Software Foundation\\Tomcat 6.0"),
             "appServerDir = %s" % p.input_ports.tomcat.home),
            (esc("dbPassword=password"),
             "dbPassword=%s" % self._get_password(p.input_ports.mysql_admin.admin_password))
        ]
        cnt = rv(subst_in_file, p.properties_file, replacements)
        assert cnt == len(replacements) or self.ctx.dry_run, "Properties file %s might be wrong - expecting %d replacements, got %d" % (p.properties_file, len(replacements), cnt)
        tomcat_utils.ensure_tomcat_stopped(self.ctx, p.input_ports.tomcat)
        # TODO: should check that the jasper reports database doesn't
        # already exist in mysql. Otherwise, will get an infinite loop in
        # script as it tries to ask you whether to delete the existing db
        # TODO: should use run_and_scan_results and check for
        # BUILD SUCCESSFUL or BUILD FAILED
        r(run_program, [p.install_shell_script],
          cwd=os.path.dirname(p.install_shell_script))
        tomcat_utils.ensure_tomcat_running(self.ctx, p.input_ports.tomcat)
        
    def validate_post_install(self):
        p = self.ctx.props
        self.ctx.r(check_dir_exists,  p.config_port.home)

    def start(self):
        r = self.ctx.r
        p = self.ctx.props
        r(tomcat_utils.start_app, p.input_ports.tomcat,
          p.output_ports.jasper_server.app_path,
          self._get_password(p.input_ports.tomcat.admin_password))

    def stop(self):
        r = self.ctx.r
        p = self.ctx.props
        r(tomcat_utils.stop_app, p.input_ports.tomcat,
          p.output_ports.jasper_server.app_path,
          self._get_password(p.input_ports.tomcat.admin_password))

    def is_running(self):
        p = self.ctx.props
        return self.ctx.rv(tomcat_utils.status_request,
                           p.input_ports.tomcat,
                           p.output_ports.jasper_server.app_path,
                           self._get_password(p.input_ports.tomcat.admin_password))

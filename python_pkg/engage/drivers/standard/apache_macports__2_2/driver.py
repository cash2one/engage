"""Service manager for apache, macports version.
See https://trac.macports.org/wiki/howto/MAMP for a good explanation of the
Apache install process. To support easily extensible configuration, we modify
the httpd.conf file, adding the following lines:
Include conf/engage_modules/*.conf
Include conf/engage_extra/*.conf

We then create the engage_modules and engage_extra directories. Downstream
components can put module configureation in engage_modules and any other
configuration (e.g. virtual site or alias definitions) in engage_extra.
"""

import os
import os.path
import sys
import re
import time

# fix path if necessary (if running from source or running as test)
try:
    import engage.utils
except:
    sys.exc_clear()
    dir_to_add_to_python_path = os.path.abspath((os.path.join(os.path.dirname(__file__), "../../../..")))
    sys.path.append(dir_to_add_to_python_path)

from engage.drivers.action import *
from engage.drivers.genforma.apache_utils import start_apache, stop_apache, restart_apache, apache_is_running
import engage.drivers.genforma.macports_pkg as macports_pkg
import engage.drivers.service_manager as service_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.utils.process as processutils
import engage.utils.log_setup
import engage.drivers.utils
from engage.drivers.password_repo_mixin import PasswordRepoMixin
from engage.utils.cfg_file import is_config_line_present, add_config_file_line

logger = engage.utils.log_setup.setup_engage_logger(__name__)

from engage.utils.user_error import EngageErrInf, UserError, convert_exc_to_user_error

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_HTTPD_ALREADY_RUNNING    = 1
ERR_INSTALL_PKG_QUERY        = 2
ERR_APACHE_STOP              = 3
ERR_APACHE_START             = 4
ERR_APACHE_PIDFILE_START     = 5

define_error(ERR_HTTPD_ALREADY_RUNNING,
             _("Found an existing httpd process. Do you have your Mac's built-in webserver running? Check the 'personal web sharing' preference in your System Preferences."))
define_error(ERR_INSTALL_PKG_QUERY,
             _("After installing MacPorts package %(pkg)s, query did not find that package was installed"))
define_error(ERR_APACHE_STOP,
             _("Apache still running %(time)s seconds after executing stop command in resource %(id)s"))
define_error(ERR_APACHE_START,
             _("Apache not running %(time)s seconds after executing start command in resource %(id)s"))
define_error(ERR_APACHE_PIDFILE_START,
             _("%(time)s seconds after starting apache, pid file %(pidfile)s has not been created in resource %(id)s"))


CFG_LINE1 = "Include conf/engage_modules/*.conf"
CFG_LINE2 = "Include conf/engage_extra/*.conf"

# this is used by the package manager to locate the packages.json
# file associated with the driver
def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)


PORTS_PACKAGE_NAME = "apache2"


def make_context(resource_json, sudo_password_fn, dry_run=False):
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=sudo_password_fn,
                  dry_run=dry_run)
    ctx.check_port("output_ports.apache",
                   config_file=str,
                   htpasswd_exe=str,
                   apache_user=str,
                   apache_group=str,
                   controller_exe=str,
                   module_config_dir=str,
                   additional_config_dir=str)
    ctx.checkp("input_ports.macports.macports_exe")
    ctx.checkp("input_ports.host.sudo_password")
    ctx.add("output_ports.apache.pid_file", "/opt/local/apache2/logs/httpd.pid")
    return ctx

class check_for_existing_server(Action):
    NAME="check_for_existing_server"
    def __init__(self, ctx):
        super(check_for_existing_server, self).__init__(ctx)

    def run(self):
        if not self.ctx.rv(macports_pkg.is_installed, PORTS_PACKAGE_NAME):
            htprocs = processutils.find_matching_processes(["httpd"])
            if len(htprocs) > 0:
                raise UserError(errors[ERR_HTTPD_ALREADY_RUNNING],
                                developer_msg="\n".join(["%d %s" for (pid, cmd)
                                                         in htprocs]))
    def dry_run(self):
        if not self.ctx.rv(macports_pkg.is_installed, PORTS_PACKAGE_NAME):
            htprocs = processutils.find_matching_processes(["httpd"])
            if len(htprocs) > 0:
                logger.warning("Found an existing httpd process. Do you have your Mac's built-in webserver running? Check the 'personal web sharing' preference in your System Preferences.")


@make_value_action
def is_pidfile_present(self, apache_config):
        return os.path.exists(apache_config.pid_file)


class Manager(service_manager.Manager, PasswordRepoMixin):
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(),
                                sudo_password_fn=self._get_sudo_password,
                                dry_run=dry_run)
        
    def validate_pre_install(self):
        """If we haven't installed the apache package and apache is running,
        the most likely the user left their apple built-in server running.
        """
        self.ctx.r(check_for_existing_server)

    def is_installed(self):
        """We consider it installed if the macport package is installed and the
        config file changes are made.
        """
        config_file = self.ctx.props.output_ports.apache.config_file
        if (not os.path.exists(config_file)) or \
           (not self.ctx.rv(macports_pkg.is_installed, PORTS_PACKAGE_NAME)):
            return False
        elif not is_config_line_present(config_file, CFG_LINE1):
            return False
        elif not is_config_line_present(config_file, CFG_LINE2):
            return False
        else:
            return True
        
    def install(self, package):
        r = self.ctx.r
        p = self.ctx.props
        config_file = p.output_ports.apache.config_file
        module_config_dir = p.output_ports.apache.module_config_dir
        additional_config_dir = p.output_ports.apache.additional_config_dir
        
        r(macports_pkg.port_install, [PORTS_PACKAGE_NAME])
        r(check_file_exists, config_file)
        if not self.ctx.dry_run:
            (uid, gid, cfg_file_mode) = fileutils.get_file_permissions(config_file)
        else:
            (uid, gid, cfg_file_mode) = (0, 0, 0755)

        if not os.path.exists(module_config_dir):
            r(sudo_mkdir, module_config_dir)
            r(sudo_set_file_permissions,
                       module_config_dir, uid, gid, 0755)
        if not os.path.exists(additional_config_dir):
            r(sudo_mkdir, additional_config_dir)
            r(sudo_set_file_permissions,
                       additional_config_dir, uid, gid, 0755)
                       
        r(sudo_add_config_file_line, config_file, CFG_LINE1)
        r(sudo_add_config_file_line, config_file, CFG_LINE2)
        # Don't need to restart, since someone will have to add a config file first and
        # then restart anyway.
        r(macports_pkg.port_load, PORTS_PACKAGE_NAME)
        self.validate_post_install()

    def validate_post_install(self):
        if not self.is_installed() and not self.ctx.dry_run:
            raise UserError(errors[ERR_INSTALL_PKG_QUERY],
                            msg_args={"pkg":PORTS_PACKAGE_NAME})

    def start(self):
        r = self.ctx.r
        p = self.ctx.props
        r(start_apache, p.output_ports.apache)
        if not self.ctx.poll_rv(5, 2.0, lambda r: r, apache_is_running, p.output_ports.apache) \
           and not self.ctx.dry_run:
            raise UserError(errors[ERR_APACHE_START],
                            msg_args={"id":p.id, "time":10})
        # wait until after the pidfile has been created before declaring things started. Otherwise, if you try
        # stopping, then apachectl will ignore the stop request.
        if not self.ctx.poll_rv(5, 2.0, lambda res: res, is_pidfile_present, p.output_ports.apache) \
           and not self.ctx.dry_run:
            raise UserError(errors[ERR_APACHE_PIDFILE_START],
                            msg_args={"id":p.id, "time":10, "pidfile":p.output_ports.apache.pid_file})

    def stop(self):
        p = self.ctx.props
        self.ctx.r(stop_apache, p.output_ports.apache)
        if not self.ctx.poll_rv(5, 2.0, lambda res: not res, apache_is_running, p.output_ports.apache) \
           and not self.ctx.dry_run:
            raise UserError(errors[ERR_APACHE_STOP],
                            msg_args={"id":p.id, "time":10})
        

    def is_running(self):
        return self.ctx.rv(apache_is_running, self.ctx.props.output_ports.apache)
        

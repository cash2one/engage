
"""Resource manager for mysql_macports 5.1

Steps to install mysql manually using macports
  (see https://trac.macports.org/wiki/howto/MAMP):
sudo port install mysql5
sudo port install mysql5-server
sudo -u _mysql mysql_install_db5
sudo chown -R _mysql:_mysql /opt/local/var/db/mysql5
sudo chown -R _mysql:_mysql /opt/local/var/run/mysql5
sudo chown -R _mysql:_mysql /opt/local/var/log/mysql5
cd /opt/local
sudo -u _mysql /opt/local/bin/mysqld_safe5 --init-file=/Users/jfischer/tmp/mysql_security.sql
mysqladmin -u root -p shutdown
"""

# Common stdlib imports
import sys
import os
import os.path

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
from engage.drivers.shared_resource_mixin import SharedResourceWithPwDbMixin
import engage.drivers.genforma.mysql_utils as mysql_utils
import engage.drivers.genforma.macports_pkg as macports_pkg
from engage.drivers.action import *
from socket import gethostname

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
ERR_NOT_INSTALLED = 1
ERR_ADMIN_PW_KEY  = 2

define_error(ERR_NOT_INSTALLED,
             _("MySQL resource file %(file)s found, but associated port %(port)s not installed"))
define_error(ERR_ADMIN_PW_KEY,
             _("Password key property %(prop)s has invalid value %(value)s"))


# setup logging
from engage.utils.log_setup import setup_engage_logger
logger = setup_engage_logger(__name__)


# this is used by the package manager to locate the packages.json
# file associated with the driver
def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)

MYSQL_PORT_PKG = "mysql5-server"

def make_context(resource_json, sudo_password_fn,
                 dry_run=False):
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=sudo_password_fn,
                  dry_run=dry_run)
    ctx.check_port("config_port",
                   mysql_admin_password=str,
                   startup_on_boot=str)
    ctx.check_port("input_ports.host",
                   sudo_password=str,
                   log_directory=str)
    ctx.check_port("input_ports.macports",
                   macports_exe=str)
    ctx.check_port("output_ports.mysql_admin",
                   mysql_user=str)
    ctx.add("startup_on_boot",
            ctx.props.config_port.startup_on_boot.lower()=='yes')
    ctx.add("mysql_install_db_script",
            "/opt/local/lib/mysql5/bin/mysql_install_db")
    ctx.add("mysql_secure_installation_script",
            "/opt/local/lib/mysql5/bin/mysql_secure_installation")
    return ctx

@make_action
def set_mysql_file_ownership(self):
    user = self.ctx.props.output_ports.mysql_admin.mysql_user
    procutils.sudo_chown(user + ":" + user,
                         ["/opt/local/var/db/mysql5",
                          "/opt/local/var/run/mysql5",
                          "/opt/local/var/log/mysql5"],
                         self.ctx._get_sudo_password(self),
                         self.ctx.logger,
                         recursive=True)
    
class Manager(service_manager.Manager, PasswordRepoMixin, SharedResourceWithPwDbMixin):
    REQUIRES_ROOT_ACCESS = True
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(),
                                self._get_sudo_password,
                                dry_run=dry_run)

    def _get_metadata_filedir(self):
        return "/opt/local/etc/mysql5"

    def _get_password_properties(self):
        return [self.ctx.props.config_port.mysql_admin_password]

    def validate_pre_install(self):
        pass

    def is_installed(self):
        return os.path.exists(self._get_metadata_filename())

    def _get_admin_password(self):
        key = self.ctx.props.config_port.mysql_admin_password
        if key==None or key=="<UNDEFINED>":
            raise UserError(errors[ERR_ADMIN_PW_KEY],
                            msg_args={"prop":"%s.config_port.mysql_admin_password" % \
                                      self.ctx.props.id,
                                      "value": key})
        return self.install_context.password_repository.get_value(key)
        
    def install(self, package):
        p = self.ctx.props
        r = self.ctx.r
        rv = self.ctx.rv
        # the package should be available, unless we are running
        # in dry run mode and are on linux
        assert self.ctx.dry_run or (package.location == MYSQL_PORT_PKG)
        if not rv(macports_pkg.is_installed, MYSQL_PORT_PKG):
            r(macports_pkg.port_install, [MYSQL_PORT_PKG])
        if p.startup_on_boot:
            r(macports_pkg.port_load, MYSQL_PORT_PKG)
        r(mysql_utils.mysql_install_db)
        r(set_mysql_file_ownership)
        mysql_utils.run_secure_installation_script(self.ctx,
                                                   self._get_admin_password())
        self._save_shared_resource_metadata()

    def validate_post_install(self):
        rv = self.ctx.rv
        if os.path.exists(self._get_metadata_filename()) and \
           (not rv(macports_pkg.is_installed, MYSQL_PORT_PKG)) and \
           (not self.ctx.dry_run):
            raise UserError(errors[ERR_NOT_INSTALLED],
                            msg_args={"file":self._get_metadata_filename(),
                                      "port":MYSQL_PORT_PKG})
        self._load_shared_resource_password_entries()

    def get_pid_file_path(self):
        return self.ctx.props.output_ports.mysql_admin.pid_file_template % \
               {"hostname":gethostname()}

    def start(self):
        p = self.ctx.props
        if self.is_running() and not self.ctx.dry_run:
            logger.debug("%s: MySQL already running" % p.id)
            return
        self.ctx.r(mysql_utils.start_mysql_server, p.output_ports.mysql_admin)
        self.ctx.check_poll(5, 2.0, lambda x: x, mysql_utils.get_mysql_status,
                            p.output_ports.mysql_admin)

    def stop(self):
        p = self.ctx.props
        if not self.is_running() and not self.ctx.dry_run:
            logger.debug("%s: MySQL already stopped" % p.id)
            return
        self.ctx.r(mysql_utils.run_mysqladmin, p.output_ports.mysql_admin,
                   self._get_admin_password(),
                   ["shutdown"])
        self.ctx.check_poll(5, 2.0, lambda x: not x, mysql_utils.get_mysql_status,
                            p.output_ports.mysql_admin)

    def is_running(self):
        return self.ctx.rv(mysql_utils.get_mysql_status,
                           self.ctx.props.output_ports.mysql_admin)

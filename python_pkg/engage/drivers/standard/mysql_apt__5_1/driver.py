
"""Resource manager for mysql_apt 5.1

Steps to install mysql manually using apt on linux:
#export DEBIAN_FRONTEND=noninteractive
echo >tmpfile <<!
> mysql-server-5.1 mysql-server/root_password password test1
> mysql-server-5.1 mysql-server/root_password_again password test1
!
sudo debconf-set-selections tmpfile
sudo apt-get install -y mysql-client-5.1 mysql-server-5.1
sudo -u mysql /usr/bin/mysql_install_db
/usr/bin/mysql -u root --password=test1 mysql_security.sql

For the mysql_config executable, need to install libmysqlclient-dev
"""

# Common stdlib imports
import sys
import os
import os.path
from socket import gethostname

# fix path if necessary (if running from source or running as test)
try:
    import engage.utils
except:
    sys.exc_clear()
    dir_to_add_to_python_path = os.path.abspath((os.path.join(os.path.dirname(__file__), "../../../..")))
    sys.path.append(dir_to_add_to_python_path)

import engage.drivers.service_manager as service_manager
import engage.drivers.utils
from engage.drivers.genforma.sysv_service_mixin import SysVServiceMixin
from engage.drivers.password_repo_mixin import PasswordRepoMixin
from engage.drivers.shared_resource_mixin import SharedResourceWithPwDbMixin
import engage.drivers.genforma.mysql_utils as mysql_utils
import engage.drivers.genforma.aptget as aptget
from engage.drivers.action import *
from engage.utils.pw_repository import gen_password
from engage.utils.file import NamedTempFile

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

define_error(ERR_NOT_INSTALLED,
             _("MySQL resource file %(file)s found, but associated port %(port)s not installed"))


# setup logging
from engage.utils.log_setup import setup_engage_logger
logger = setup_engage_logger(__name__)


# this is used by the package manager to locate the packages.json
# file associated with the driver
def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)


def make_context(resource_json, sudo_password_fn,
                 dry_run=False):
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=sudo_password_fn,
                  dry_run=dry_run)
    ctx.check_port("config_port",
                   mysql_admin_password=str)
    ctx.check_port("input_ports.host",
                   sudo_password=str,
                   log_directory=str)
    ctx.check_port("output_ports.mysql_admin",
                   mysql_user=str)
    ctx.add("mysql_install_db_script",
            "/usr/bin/mysql_install_db")
    return ctx

_debconf_selections = """
mysql-server-5.1 mysql-server/root_password password %(pw)s
mysql-server-5.1 mysql-server/root_password_again password %(pw)s
"""
    
class Manager(SysVServiceMixin, PasswordRepoMixin,
              SharedResourceWithPwDbMixin, service_manager.Manager):
    REQUIRES_ROOT_ACCESS = True
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(),
                                self._get_sudo_password,
                                dry_run=dry_run)

    def _get_metadata_filedir(self):
        return "/etc/mysql"

    def _get_password_properties(self):
        return [self.ctx.props.config_port.mysql_admin_password]

    def validate_pre_install(self):
        pass

    def is_installed(self):
        return os.path.exists(self._get_metadata_filename())

    def _get_admin_password(self):
        return self.install_context.password_repository.get_value(
                   self.ctx.props.config_port.mysql_admin_password)

    def _get_service_name(self):
        return "mysql"
    
    def install(self, package):
        p = self.ctx.props
        r = self.ctx.r
        rv = self.ctx.rv
        # we ignore the package, as we call apt-get directly for the server and
        # client packages
        pw = gen_password(12)
        debconf_selections = _debconf_selections % {"pw":pw}
        r(aptget.debconf_set_selections, debconf_selections)
        r(aptget.ensure_installed, "mysql-client-5.1")
        r(aptget.ensure_installed, "mysql-server-5.1")
        r(aptget.ensure_installed, "libmysqlclient-dev")
        r(mysql_utils.mysql_install_db)
        self.ctx.add("mysql_admin_password_value", self._get_admin_password())
        # run the secure install script
        with NamedTempFile(rv(get_template_subst, "mysql_security.sql.tmpl",
                              src_dir=os.path.join(
                                        os.path.dirname(mysql_utils.__file__), "data"))) as f:
            r(mysql_utils.run_mysql_client, "root", pw, "source %s" % f.name)
        if self.is_running():
            self.stop() # leave the db in a stopped state
        self._save_shared_resource_metadata()

    def validate_post_install(self):
        rv = self.ctx.rv
        if os.path.exists(self._get_metadata_filename()) and \
           (not rv(apt_get.is_pkg_installed, "mysql-server-5.1")) and \
           (not self.ctx.dry_run):
            raise UserError(errors[ERR_NOT_INSTALLED],
                            msg_args={"file":self._get_metadata_filename(),
                                      "port":"mysql-server-5.1"})
        self._load_shared_resource_password_entries()

    def get_pid_file_path(self):
        return self.ctx.props.output_ports.mysql_admin.pid_file_template % \
               {"hostname":gethostname()}


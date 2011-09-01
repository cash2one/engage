
"""Resource manager for mysql-connector-for-django 5.1 
"""

# Common stdlib imports
import sys
import os
import os.path
import re

# fix path if necessary (if running from source or running as test)
try:
    import engage.utils
except:
    sys.exc_clear()
    dir_to_add_to_python_path = os.path.abspath((os.path.join(os.path.dirname(__file__), "../../../..")))
    sys.path.append(dir_to_add_to_python_path)

import engage.drivers.resource_manager as resource_manager
import engage.drivers.utils
from engage.drivers.password_repo_mixin import PasswordRepoMixin
import engage.drivers.genforma.mysql_utils as mysql_utils
import engage.utils.file as fileutils

# Drivers compose *actions* to implement their methods.
from engage.drivers.action import *

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
    ctx.check_port("config_port",
                   NAME=str,
                   USER=str,
                   PASSWORD=str)
    ctx.check_port("input_ports.mysql_admin",
                   admin_password=str,
                   mysqladmin_exe=str,
                   mysql_client_exe=str,
                   mysqldump_exe=str)
    ctx.check_port("input_ports.mysql",
                   host=str,
                   port=int)
    return ctx


# Now, define the main resource manager class for the driver. If this driver is
# a service, inherit from service_manager.Manager instead of
# resource_manager.Manager. If you need the sudo password, add
# PasswordRepoMixin to the inheritance list.
#
class Manager(resource_manager.Manager, PasswordRepoMixin):
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(),
                                self._get_sudo_password,
                                dry_run=dry_run)

    def _get_admin_password(self):
        p = self.ctx.props
        return self._get_password(p.input_ports.mysql_admin.admin_password)
    
    def validate_pre_install(self):
        self.ctx.r(check_file_exists,
                   self.ctx.props.input_ports.mysql_admin.mysql_client_exe)

    def is_installed(self):
        p = self.ctx.props
        rv = self.ctx.rv
        results = rv(mysql_utils.run_mysql_client_and_scan_results,
                     "root", self._get_admin_password(),
                     "use mysql\nselect count(*) from db where db='%s';\nquit\n" % p.config_port.NAME,
                     {"db_not_found":"^0$",
                      "db_found": "^1$"},
                     log_output=True)
        if self.ctx.dry_run:
            return None
        elif results['db_found']:
            return True
        elif results['db_not_found']:
            return False
        else:
            assert 0, "Unexpected output from mysql use database"

    def install(self, package):
        p = self.ctx.props
        r = self.ctx.r
        r(mysql_utils.run_mysql_client,
          "root", self._get_admin_password(),
          "CREATE DATABASE %s CHARACTER SET utf8;" % p.config_port.NAME)
        r(mysql_utils.run_mysql_client,
          "root", self._get_admin_password(),
          "create user '%s'@'localhost' identified by '%s';\nquit\n" %
           (p.config_port.USER, self._get_password(p.config_port.PASSWORD)),
          command_text_for_logging="create user '%s'@'localhost' identified by '****';\nquit\n" % p.config_port.USER)
        r(mysql_utils.run_mysql_client,
          "root", self._get_admin_password(),
          "use %s;\ngrant all on %s.* to '%s'@'localhost';\nflush privileges;\nquit\n" %
          (p.config_port.NAME, p.config_port.NAME, p.config_port.USER))

    def validate_post_install(self):
        p = self.ctx.props
        r = self.ctx.r
        logger.debug("Testing that we can login to mysql using django account")
        r(mysql_utils.run_mysql_client,
          p.config_port.USER, self._get_password(p.config_port.PASSWORD),
          "use %s;\nquit\n" % p.config_port.NAME)

    def backup(self, backup_to_directory, compress=True):
        p = self.ctx.props
        r = self.ctx.r
        mysql_backup_dir = \
            os.path.join(backup_to_directory,
                         fileutils.mangle_resource_key(self.metadata.key))
        r(ensure_dir_exists, mysql_backup_dir)
        r(mysql_utils.dump_database, p.config_port.NAME,
          os.path.join(mysql_backup_dir,
                       "mysql_dump_%s.sql" % p.config_port.NAME),
          self._get_admin_password())
    
    def uninstall(self, backup_to_directory, incomplete_install=False,
                  compress=True):
        p = self.ctx.props
        r = self.ctx.r
        try:
            self.backup(backup_to_directory, compress)
        except Exception, e:
            if incomplete_install:
                logger.debug("Backup failed for resource %s, exception was %s ignoring." %
                             (p.id, str(e)))
            else:
                raise
        try:
            r(mysql_utils.run_mysql_client, "root", self._get_admin_password(),
              "drop database %s;\nquit\n" % p.config_port.NAME)
        except Exception, e:
            if incomplete_install:
                logger.debug("Drop database failed for resource %s, exception was %s, ignoring." %
                             (p.id, str(e)))
            else:
                raise
        try:
            r(mysql_utils.run_mysql_client, "root", self._get_admin_password(),
              "drop user '%s'@'localhost';\nquit\n" % p.config_port.USER)
        except Exception, e:
            if incomplete_install:
                logger.debug("Drop user failed for resource %s, exception was %s, ignoring." %
                             (p.id, str(e)))
            else:
                raise

    def restore(self, backup_to_directory, package):
        p = self.ctx.props
        r = self.ctx.r
        script = os.path.join(
                     os.path.join(backup_to_directory,
                         fileutils.mangle_resource_key(self.metadata.key)),
                     "mysql_dump_%s.sql" % p.config_port.NAME)
        r(check_file_exists, script)
        self.install(package)
        r(mysql_utils.run_mysql_script, "root", self._get_admin_password(),
          script, database=p.config_port.NAME)
        logger.debug("Successfully restored database %s" % p.config_port.NAME)
        

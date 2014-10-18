
"""Resource manager for postgres-database 9.x 
"""

# Common stdlib imports
import sys
import os
import os.path
## import commands

# fix path if necessary (if running from source or running as test)
try:
    import engage.utils
except:
    sys.exc_clear()
    dir_to_add_to_python_path = os.path.abspath((os.path.join(os.path.dirname(__file__), "../../../..")))
    sys.path.append(dir_to_add_to_python_path)

import engage_utils.process as procutils

import engage.drivers.resource_manager as resource_manager
import engage.drivers.utils
# Drivers compose *actions* to implement their methods.
from engage.drivers.action import *
from engage.drivers.action import _check_file_exists

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
ERR_BAD_USER = 1

define_error(ERR_BAD_USER,
             _("Install must be running as database user %(db_user)s, was running as %(user)s"))

# setup logging
from engage.utils.log_setup import setup_engage_logger
logger = setup_engage_logger(__name__)


# this is used by the package manager to locate the packages.json
# file associated with the driver
def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)

@make_value_action
def is_database_installed(self, psql_exe, database_name, database_user):
    _check_file_exists(psql_exe, self)
    rc = procutils.run_and_log_program([psql_exe, '-d', database_name,
                                        '-U', database_user, '-c', r'\d'], None,
                                       self.ctx.logger, os.path.dirname(psql_exe))
    return rc==0

    
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
                  database_name=unicode,
                  create_schema_script=unicode)
    ctx.check_port('input_ports.postgres',
                  psql_exe=unicode,
                  pg_ctl_exe=unicode,
                  createdb_exe=unicode,
                  createuser_exe=unicode,
                  initdb_exe=unicode)
    ctx.check_port('input_ports.postgres_inst',
                  database_dir=unicode,
                  user=unicode)

    # add any extra computed properties here using the ctx.add() method.
    return ctx

#
# Now, define the main resource manager class for the driver.
# If this driver is a service, inherit from service_manager.Manager.
# If the driver is just a resource, it should inherit from
# resource_manager.Manager. If you need the sudo password, add
# PasswordRepoMixin to the inheritance list.
#
class Manager(resource_manager.Manager):
    # Uncomment the line below if this driver needs root access
    ## REQUIRES_ROOT_ACCESS = True 
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(),
                                None, # self._get_sudo_password,
                                dry_run=dry_run)

    def validate_pre_install(self):
        p = self.ctx.props
        user = getpass.getuser()
        if user != p.input_ports.postgres_inst.user:
            raise UserError(errors[ERR_BAD_USER],
                            msg_args={'user':user,
                                      'db_user':p.input_ports.postgres_inst.user})
        if p.config_port.create_schema_script!='':
            self.ctx.r(check_file_exists, p.config_port.create_schema_script)

    def is_installed(self):
        p = self.ctx.props
        return self.ctx.rv(is_database_installed, p.input_ports.postgres.psql_exe,
                           p.config_port.database_name,
                           p.input_ports.postgres_inst.user)
                           

    def install(self, package):
        p = self.ctx.props
        r = self.ctx.r
        r(run_program, [p.input_ports.postgres.createdb_exe,
                        p.config_port.database_name],
          cwd=p.input_ports.postgres_inst.database_dir)
        if p.config_port.create_schema_script!='':
            logger.info('Will run %s to create schema for %s' %
                        (p.config_port.create_schema_script,
                         p.config_port.database_name))
            r(run_program,
              [p.input_ports.postgres.psql_exe,
               '-d', p.config_port.database_name,
               '-f', p.config_port.create_schema_script],
              cwd=p.input_ports.postgres_inst.database_dir)
        else:
            logger.info("No create schema script specified for %s" %
                        p.config_port.database_name)


    def validate_post_install(self):
        assert self.is_installed()



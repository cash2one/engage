
"""Resource manager for postgres-instance 9.2.

Note that this driver runs the database instance under a specified user (not
necessarily postgres). On Linux, installing the apt package creates
a database instance at /var/lib/postgresql/9.2/main and adds the database
instance to system startup/shutdown. Unfortunately, this causes problems
for us, as we cannot run two instances on the same machine with the default
port. As a workaround, we disable the automatic startup of postgresql on
linux as a part of this driver's install() method.
"""

# Common stdlib imports
import sys
import os
import os.path
import getpass
import re

# fix path if necessary (if running from source or running as test)
try:
    import engage.utils
except:
    sys.exc_clear()
    dir_to_add_to_python_path = os.path.abspath((os.path.join(os.path.dirname(__file__), "../../../..")))
    sys.path.append(dir_to_add_to_python_path)

import engage.drivers.service_manager as service_manager
import engage.drivers.utils
# Drivers compose *actions* to implement their methods.
from engage.drivers.action import *
from engage.drivers.action import _check_poll

from engage_utils.system_info import get_platform

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
                  database_dir=unicode)
    ctx.check_port('input_ports.host',
                  genforma_home=unicode,
                  os_user_name=unicode,
                  sudo_password=unicode,
                  log_directory=unicode)
    ctx.check_port('input_ports.postgres',
                  psql_exe=unicode,
                  pg_ctl_exe=unicode,
                  createdb_exe=unicode,
                  createuser_exe=unicode,
                  initdb_exe=unicode)
    ctx.check_port('output_ports.postgres_inst',
                  database_dir=unicode,
                  user=unicode,
                  pid_file=unicode)

    # add any extra computed properties here using the ctx.add() method.
    return ctx

#
# Now, define the main resource manager class for the driver.
# If this driver is a service, inherit from service_manager.Manager.
# If the driver is just a resource, it should inherit from
# resource_manager.Manager. If you need the sudo password, add
# PasswordRepoMixin to the inheritance list.
#
class Manager(service_manager.Manager):
    # Uncomment the line below if this driver needs root access
    ## REQUIRES_ROOT_ACCESS = True 
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(),
                                None, # self._get_sudo_password,
                                dry_run=dry_run)

    def validate_pre_install(self):
        p = self.ctx.props
        user = getpass.getuser()
        if user != p.input_ports.host.os_user_name:
            raise UserError(errors[ERR_BAD_USER],
                            msg_args={'user':user,
                                      'db_user':p.input_ports.host.os_user_name})
        self.ctx.r(check_installable_to_dir, p.config_port.database_dir)

    def is_installed(self):
        return os.path.exists(self.ctx.props.config_port.database_dir)

    def install(self, package):
        # the installation must be running as the db user (checked in validate_pre_install())
        p = self.ctx.props
        r = self.ctx.r
        if get_platform().startswith('linux'):
            self.ctx.logger.info("Disabling startup of default postgres instance")
            r(sudo_run_program, ['/usr/sbin/update-rc.d', 'postgresql', 'disable'],
              cwd='/etc/init.d')
            r(sudo_run_program, ['/etc/init.d/postgresql', 'stop'],
              cwd='/etc/init.d')
            # we need to make sure the lock directory exists and is
            # writable by our postgres user
            if not os.path.exists('/var/run/postgresql'):
                self.ctx.r_su(mkdir, '/var/run/postgresql')
            r(sudo_run_program, ['/bin/chown', p.output_ports.postgres_inst.user,
                                 '/var/run/postgresql'],
              cwd='/')
        r(mkdir, p.config_port.database_dir)
        r(run_program,
          [p.input_ports.postgres.initdb_exe, '-D', p.config_port.database_dir],
          cwd=p.config_port.database_dir)
        config_file = os.path.join(p.config_port.database_dir, 'postgresql.conf')
        r(check_file_exists, config_file)
        r(subst_in_file_and_check_count,
          config_file,
          [('^' + re.escape("#external_pid_file = ''"),
            "external_pid_file = '%s'" % p.output_ports.postgres_inst.pid_file)], 1)

    def validate_post_install(self):
        p = self.ctx.props
        self.ctx.r(check_dir_exists,  p.config_port.database_dir)

    def start(self):
        p = self.ctx.props
        r = self.ctx.r
        if get_platform().startswith('linux'):
            # we need to make sure the lock directory exists and is
            # writable by our postgres user
            if not os.path.exists('/var/run/postgresql'):
                self.ctx.r_su(mkdir, '/var/run/postgresql')
            r(sudo_run_program, ['/bin/chown', p.output_ports.postgres_inst.user,
                                 '/var/run/postgresql'],
              cwd='/')
        self.ctx.r(start_server_as_user,
                   p.output_ports.postgres_inst.user,
                   [p.input_ports.postgres.pg_ctl_exe,
                    '-D', p.config_port.database_dir, 'start'],
                   os.path.join(p.input_ports.host.log_directory,
                                'postgres.log'),
                   cwd=p.config_port.database_dir)
        self.ctx.check_poll(12, 5.0, lambda v:v,
                            get_server_status, p.output_ports.postgres_inst.pid_file)
        

    def is_running(self):
        p = self.ctx.props
        return self.ctx.rv(get_server_status,
                           p.output_ports.postgres_inst.pid_file) != None

    def stop(self):
        p = self.ctx.props
        ## self.ctx.r(stop_server, p.output_ports.postgres_inst.pid_file)
        logger.info("Doing a fast-stop of postgres...")
        db_dir = p.output_ports.postgres_inst.database_dir
        self.ctx.r(run_program, ['/usr/bin/sudo', '-u', p.output_ports.postgres_inst.user, p.input_ports.postgres.pg_ctl_exe, '-D',
                                 db_dir, 'stop', '-m', 'fast'],
                   cwd=db_dir)

    def force_stop(self):
        p = self.ctx.props
        logger.info("Doing a force-stop of postgres via SIGKILL...")
        self.ctx.r(stop_server, p.output_ports.postgres_inst.pid_file, force_stop=True)
        ## r = self.ctx.r
        ## logger.info("Doing a force-stop of postgres...")
        ## db_dir = p.output_ports.postgres_inst.database_dir
        ## r(run_program, [p.input_ports.postgres.pg_ctl_exe, '-D',
        ##                 db_dir, 'stop', '-m', 'fast'],
        ##   cwd=db_dir)
        return True

    def get_pid_file_path(self):
        # Method to return the path to the pid file for an installed service.
        # If there is no pid file for this service, just return None. This is
        # used by management tools (e.g. monit) to monitor the service.xs
        return self.ctx.props.output_ports.postgres_inst.pid_file


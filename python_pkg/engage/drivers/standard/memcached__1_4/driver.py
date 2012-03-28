"""Service manager for memcached
"""
import os
import os.path
import shutil
import sys
import time

# fix path if necessary (if running from source or running as test)
try:
    import engage.utils
except:
    sys.exc_clear()
    dir_to_add_to_python_path = os.path.abspath((os.path.join(os.path.dirname(__file__), "../../../..")))
    sys.path.append(dir_to_add_to_python_path)

import engage.drivers.service_manager as service_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.utils.path as iupath
import engage.utils.process as iuprocess
import engage.utils.http as iuhttp
import engage.utils.log_setup
import engage.utils.file as iufile
import engage.utils.timeout as iutimeout
import engage.drivers.utils
from engage.drivers.password_repo_mixin import PasswordRepoMixin
from engage.drivers.action import *
import engage.drivers.genforma.macports_pkg as macports_pkg
import engage.drivers.genforma.aptget as aptget

logger = engage.utils.log_setup.setup_script_logger(__name__)

from engage.utils.user_error import ScriptErrInf, UserError

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_MEMCACHED_BUILD_FAILED    = 1
ERR_MEMCACHED_NO_INSTALL_DIR  = 2
ERR_MEMCACHED_NO_EXEC_FOUND   = 3
ERR_MEMCACHED_START_FAILED    = 4
ERR_MEMCACHED_STOP_FAILED     = 5
ERR_MEMCACHED_EXITED          = 6
ERR_MEMCACHED_UNKNOWN_OSTYPE  = 7


define_error(ERR_MEMCACHED_BUILD_FAILED,
             _("Memcached build failed"))
define_error(ERR_MEMCACHED_NO_INSTALL_DIR,
             _("Post install check failed: missing installation directory '%(dir)s'"))
define_error(ERR_MEMCACHED_NO_EXEC_FOUND,
             _("Post install check failed: missing executable in directory '%(dir)s'"))
define_error(ERR_MEMCACHED_START_FAILED,
             _("Memcached daemon execution failed in resource %(id)s"))
define_error(ERR_MEMCACHED_STOP_FAILED,
             _("Memcached daemon stop failed"))
define_error(ERR_MEMCACHED_EXITED,
             _("Memcached daemon appears to have exited after startup"))
define_error(ERR_MEMCACHED_UNKNOWN_OSTYPE,
             _("Installation on unknown os type %(ostype)s"))

def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)

def make_context(resource_json, sudo_password_fn, dry_run=False):
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=sudo_password_fn,
                  dry_run=dry_run)
    ctx.check_port("input_ports.host",
                   os_type=str,
                   log_directory=str,
                   sudo_password=str)
    ctx.check_port("output_ports.cache",
                   host=str,
                   port=int,
                   provider=str,
                   home=str)
    if ctx.props.input_ports.host.os_type == 'linux':
        ctx.add("memcached_exe", "/usr/bin/memcached")
        # we stick the linux pid file where it would go if memcached
        # is started by the os. This handles the case where the
        # server is rebooted and we want to see if memcached is running.
        ctx.add("pidfile", os.path.join("/var/run/memcached.pid"))
    elif ctx.props.input_ports.host.os_type == 'mac-osx':
        ctx.add("memcached_exe", "/opt/local/bin/memcached")
        # this is hack: we should really have separate drivers for macports
        # and aptget
        ctx.add("input_ports.macports.macports_exe", "/opt/local/bin/port")
        ctx.add("pidfile", os.path.join(ctx.props.output_ports.cache.home, "memcached.pid"))
    else:
        raise UserError(ERR_MEMCACHED_UNKNOWN_OS_TYPE, {'ostype':ctx.props.input_ports.host.os_type})
    ctx.add("logfile", os.path.join(ctx.props.input_ports.host.log_directory, "memcached.log"))
    ctx.add("memsize", 64)
    return ctx


@make_action
def start_memcached(self):
    """We start memcached as a daemon process. The pidfile is created
    by memcached.
    """
    p = self.ctx.props
    memcached_args = [p.memcached_exe, "-d", "-P", p.pidfile,
                      "-m", str(p.memsize)]
    if os.geteuid()==0:
        memcached_args.extend(["-u", "root"])
    rc = procutils.run_and_log_program(memcached_args,
                                       None, self.ctx.logger)
    if rc != 0:
        raise UserError(errors[ERR_MEMCACHED_START_FAILED],
                        msg_args={"id":p.id},
                        developer_msg="rc was %d" % rc)
    self.ctx.logger.debug("memcached daemon started successfully")

class Manager(service_manager.Manager, PasswordRepoMixin):
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(),
                                sudo_password_fn=self._get_sudo_password,
                                dry_run=dry_run)

    def validate_pre_install(self):
        pass

    def get_pid_file_path(self):
        return self.ctx.props.pidfile
    
    def install(self, package):
        r = self.ctx.r
        p = self.ctx.props
        home_path = p.output_ports.cache.home
        # on linux, use apt-get
        if p.input_ports.host.os_type == 'linux':
            # use apt-get
            r(aptget.install, ['memcached'])
        elif p.input_ports.host.os_type == 'mac-osx':
            # otherwise install using macports
            r(macports_pkg.port_install, ['memcached'])
        else:
            raise UserError(ERR_MEMCACHED_UNKNOWN_OS_TYPE, {'ostype':p.input_ports.host.os_type})
        # home_path used for pidfile
        r(ensure_dir_exists, home_path)
        self.validate_post_install()

    def is_installed(self):
        p = self.ctx.props
        rv = self.ctx.rv
        if not os.path.exists(p.output_ports.cache.home):
            return False
        if p.input_ports.host.os_type == 'linux':
            return rv(aptget.is_pkg_installed, 'memcached')
        elif p.input_ports.host.os_type == 'mac-osx':
            return rv(macports_pkg.is_installed, "memcached")
        else:
            raise UserError(ERR_MEMCACHED_UNKNOWN_OS_TYPE, {'ostype':p.input_ports.host.os_type})

    def validate_post_install(self):
        r = self.ctx.r
        p = self.ctx.props
        home_path = p.output_ports.cache.home
        r(check_dir_exists, home_path)
        if p.input_ports.host.os_type == 'linux':
            r(aptget.check_installed, "memcached")
        elif p.input_ports.host.os_type == 'mac-osx':
            r(macports_pkg.check_installed, "memcached")
        else:
            raise UserError(ERR_MEMCACHED_UNKNOWN_OS_TYPE, {'ostype':p.input_ports.host.os_type})

    def start(self):
        p = self.ctx.props
        self.ctx.r(start_memcached)
        # make sure that it is up
        self.ctx.poll_rv(10, 1.0, lambda x: x, get_server_status,
                         p.pidfile)

    def is_running(self):
        return self.ctx.rv(get_server_status, self.ctx.props.pidfile)!=None

    def stop(self):
        r = self.ctx.r
        p = self.ctx.props
        r(stop_server, p.pidfile, force_stop=True, timeout_tries=20)

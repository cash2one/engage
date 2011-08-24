"""Service manager for rabbitmq

This driver works on both macosx (using ports) and ubuntu (using aptget).
On mac, we don't setup rabbitmq to automatically start on boot. To do this, run:
    sudo port load rabbitmq-server

Unfortunately, rabbitmq doesn't generate a pidfile. We play some tricks to
create one ourselves and keep it in sync.
Pid pattern for linux: [{'rabbit@demo-yDedvp9NbJiq',3313}]. (version 1.7.2)
"""
import os
import os.path
import shutil
import sys
import time
import re
import copy

# fix path if necessary (if running from source or running as test)
try:
    import engage.utils
except:
    sys.exc_clear()
    dir_to_add_to_python_path = os.path.abspath((os.path.join(os.path.dirname(__file__), "../../../..")))
    sys.path.append(dir_to_add_to_python_path)

from engage.drivers.action import *
import engage.drivers.service_manager as service_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.utils.path as iupath
import engage.utils.process as procutils
import engage.utils.http as iuhttp
import engage.utils.log_setup
import engage.utils.file as fileutils
import engage.utils.timeout as iutimeout
import engage.drivers.utils
import engage.drivers.genforma.aptget as aptget
import engage.drivers.genforma.macports_pkg as macports_pkg
from engage.drivers.password_repo_mixin import PasswordRepoMixin

logger = engage.utils.log_setup.setup_script_logger(__name__)

from engage.utils.user_error import ScriptErrInf, UserError
from engage.drivers.password_repo_mixin import PasswordRepoMixin

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_RABBITMQ_SETUP_FAILED = 1
ERR_RABBITMQ_EXITED       = 2

define_error(ERR_RABBITMQ_SETUP_FAILED,
             _("Install of Rabbitmq failed in resource %(id)s."))
define_error(ERR_RABBITMQ_EXITED,
             _("Rabbitmq broker appears to have exited after startup in resource %(id)s"))


# timeouts for checking server liveness after startup
def get_rabbitmq_executable(host):
    """Called by other drivers to get the controller executable
    """
    if host.os_type == "linux":
        return "/usr/sbin/rabbitmqctl"
    else:
        return "/opt/local/sbin/rabbitmqctl"


def make_context(resource_json, sudo_password_fn, dry_run=False):
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=sudo_password_fn,
                  dry_run=dry_run)
    ctx.check_port("input_ports.host",
                   os_type=str,
                   log_directory=str,
                   sudo_password=str)
    ctx.add("rabbitmqctl", get_rabbitmq_executable(ctx.props.input_ports.host))
    if ctx.props.input_ports.host.os_type == 'linux':
        ctx.add("rabbitmqserver", '/usr/sbin/rabbitmq-server')
        ctx.add("rabbitmqmulti", "/usr/sbin/rabbitmq-multi")
        ctx.add("rabbitmq_old_pid_file", "/var/lib/rabbitmq/pids")
        ctx.add("package_name", "rabbitmq-server")
        ctx.add("logdir", "/var/log/rabbitmq")
    elif ctx.props.input_ports.host.os_type == 'mac-osx':
        ctx.add("rabbitmqserver", '/opt/local/sbin/rabbitmq-server')
        ctx.add("rabbitmqmulti", "/opt/local/sbin/rabbitmq-multi")
        ctx.add("rabbitmq_old_pid_file", "opt/local/var/lib/rabbitmq/pids")
        ctx.add("package_name", "rabbitmq-server")
        ctx.add("logdir", "/opt/local/var/log/rabbitmq")
        # this is hack: we should really have separate drivers for macports
        # and aptget
        ctx.add("input_ports.macports.macports_exe", "/opt/local/bin/port")
    # we stick the pidfile in the log directory. We have to generate it ourselves.
    ctx.add("pidfile", os.path.join(ctx.props.input_ports.host.log_directory,
                                    "rabbitmq.pid"))
    return ctx



class get_rabbitmq_pid(ValueAction):
    NAME = "get_rabbitmq_pid"
    def __init__(self, ctx):
        super(get_rabbitmq_pid, self).__init__(ctx)
        
    def _run_rabbitmqctl(self, re_map):
        rc, remap = procutils.run_sudo_program_and_scan_results(
                        [get_rabbitmq_executable(self.ctx.props.input_ports.host),
                         'status'],
                        re_map,
                        self.ctx.logger,
                        self.ctx._get_sudo_password(self),
                        return_mos=True,
                        log_output=True)
        return rc, remap
        
    def run(self):
        p = self.ctx.props
        if os.path.exists(p.rabbitmqmulti):
            # we're running the old-style rabbitmq. This means that
            # the pid is written to disk, but in a weird format.
            # We run rabbitmqctl to get the status, and, if rabbitmq is
            # running, parse the pidfile.
            (rc, remap) = self._run_rabbitmqctl({ 'err_msg' : r'^Error:'})
            if (rc != 0) or (remap['err_msg'] != None):
                return None
            elif not os.path.exists(p.rabbitmq_old_pid_file):
                self.ctx.logger.warning("Rabbit mq running, but pid file '%s' not found" %
                                        p.rabbitmq_old_pid_file)
                return None
            with open(p.rabbitmq_old_pid_file, "r") as pf:
                pid_data = pf.read()
            mo = re.search("\\[\\{\\'[^\\']+\\'\\,(\d+)\\}\\]",
                           pid_data)
            assert mo!=None, \
                   "Pid file '%s' contents does not contain pid in expected format. Data was: %s" % \
                   (p.rabbitmq_old_pid_file, pid_data)
            return int(mo.group(1))
        else:
            # we're running the new-style rabbitmq. This means that
            # the pid is included in the output of the status message.
            rc, remap = self._run_rabbitmqctl({ 'err_msg' : r'^Error:', 'pid': "\\{pid\\,(\d+)\\}" })
            if (rc != 0) or (remap['err_msg'] != None):
                return None
            elif remap['pid'] != None:
                assert len(remap['pid'])==1, \
                       "More than one math for pid regular expression in rabbitmqctl status output"
                return int(remap['pid'][0].group(1))
            else:
                assert 0, "Rabbitmq apparently up, but pid not found in output"

    def dry_run(self):
        pass
    

def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)

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

    def install(self, package):
        p = self.ctx.props
        r = self.ctx.r
        if p.input_ports.host.os_type == 'linux':
            # We have to make a debian config change to prevent apt-get
            # from putting up a dialog box when installing rabbitmq.
            # See http://askubuntu.com/questions/27982/bypass-rabbitmq-ok-dialog-on-install
            data="rabbitmq-server rabbitmq-server/upgrade_previous note"
            with fileutils.NamedTempFile(data=data) as tf:
                r(sudo_run_program, ["/usr/bin/debconf-set-selections", tf.name])
            r(aptget.install, [p.package_name])
        elif p.input_ports.host.os_type == 'mac-osx':
	    r(macports_pkg.port_install, [p.package_name])
        else:
            assert False, 'Unknown OS type %s' % p.input_ports.host.os_type
        # check that everything is now in place
        self.validate_post_install()

    def is_installed(self):
        p = self.ctx.props
        rv = self.ctx.rv
        if p.input_ports.host.os_type == 'linux':
            return rv(aptget.is_pkg_installed, p.package_name)
        elif p.input_ports.host.os_type == 'mac-osx':
            return rv(macports_pkg.is_installed, p.package_name)
        else:
            assert False, 'Unknown OS type %s' % p.input_ports.host.os_type

    def validate_post_install(self):
        if not self.is_installed() and not self.ctx.dry_run:
            raise UserError(errors[ERR_RABBITMQ_SETUP_FAILED], msg_args={"id":self.ctx.props.id })

    def start(self):
        p = self.ctx.props
        r = self.ctx.r
        running_pid = self.ctx.rv(get_rabbitmq_pid)
        if running_pid!=None:
            # an external utility or the OS may have already started rabbit mq.
            # In this case, we just make sure that the pidfile reflects reality.
            logger.debug("Resource %s is already running, will update pidfile and return" % p.id)
            self.update_pidfile(running_pid)
            return
        
        startup_log_file = os.path.join(p.input_ports.host.log_directory,
                                        'rabbitmq_startup.log')
        env = copy.deepcopy(os.environ)
        # force rabbitmq to only listen locally
        env['RABBITMQ_NODE_IP_ADDRESS'] = '127.0.0.1'
        r(sudo_start_server, [p.rabbitmqserver, '-detached'], startup_log_file,
          environment=env)
        # check for up to 10 seconds to see if running
        running_pid = self.ctx.check_poll(5, 2.0, lambda pid: pid!=None, get_rabbitmq_pid)
        self._update_pidfile(running_pid)
        logger.debug("Started resource %s" % p.id)

    def _update_pidfile(self, running_pid):
        """Make sure that the pidfile on the disk matches the current
        running process. If the process is running, but there is no
        pidfile or a pidfile with the wrong pid, write out the current pid.
        If the process is not running, and there is a pidfile, delete it.
        """
        p = self.ctx.props
        pidfile_pid = procutils.get_pid_from_file(p.pidfile)
        if running_pid==None:
            if pidfile_pid:
                os.remove(p.pidfile)
        else:
            if pidfile_pid != running_pid:
                with open(p.pidfile, "w") as pf:
                    pf.write(str(running_pid))

    def is_running(self):
        if self.ctx.dry_run: return None
        running_pid = self.ctx.rv(get_rabbitmq_pid)
        self._update_pidfile(running_pid)
        return running_pid!=None
                

    def stop(self):
        p = self.ctx.props
        r = self.ctx.r
        poll_rv = self.ctx.poll_rv
        r(sudo_run_program, [p.rabbitmqctl, 'stop'])
        if not self.ctx.dry_run:
            # wait up to 10 seconds to verify that it stopped
            # then, update pidfie
            self.ctx.check_poll(5, 2.0, lambda pid: pid==None,
                                get_rabbitmq_pid)
            self._update_pidfile(None)

    def get_pid_file_path(self):
        return self.ctx.props.pidfile

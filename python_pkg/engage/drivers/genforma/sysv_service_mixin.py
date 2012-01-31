import re
from engage.drivers.action import *
from engage.utils.decorators import require_methods
import engage.utils.process as procutils

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
ERR_BAD_STATUS = 1

define_error(ERR_BAD_STATUS,
             _("Problem in determining status of service %(svc)s"))

SERVICE_EXE="/usr/sbin/service"

@make_value_action
def is_running(self, svcname):
    ## rc = procutils.run_and_log_program([SERVICE_EXE, svcname, "status"], None,
    ##                                    self.ctx.logger)
    re_map = {"running":re.escape("%s start/running" % svcname),
              "stopped":re.escape("%s stop/waiting" % svcname)}
    (rc, m) = procutils.run_sudo_program_and_scan_results([SERVICE_EXE, svcname, "status"],
                                                          re_map, self.ctx.logger,
                                                          self.ctx._get_sudo_password(self),
                                                          log_output=True)
    if rc==1:
        return False
    elif rc!=0:
        raise UserError(errors[ERR_BAD_STATUS],
                        msg_args={"svc":svcname},
                        developer_msg="Return code was %d" % rc)
    elif m['running']:
        return True
    elif m['stopped']:
        return False
    else:
        raise UserError(errors[ERR_BAD_STATUS],
                        msg_args={"svc":svcname},
                        developer_msg="Did not find status patterns")


sudo_get_server_status = adapt_sudo_value_action(get_server_status)

class SysVServiceMixin(object):
    """This is a mixin to be used with service managers on systems that have
    "Unix system V style" service management. This includes ubuntu linux.
    """
    @require_methods("_get_service_name", "get_pid_file_path")
    def __init__(self):
        pass

    def start(self):
        self.ctx.r(sudo_run_program, [SERVICE_EXE, self._get_service_name(), "start"])
        # wait up to 10 seconds for process to start
        self.ctx.check_poll(5, 2.0, lambda x: x, is_running, self._get_service_name())
        # if we have a pid file, we also wait until the pid file reflects that the
        # server is up
        pid_file = self.get_pid_file_path()
        if pid_file:
            self.ctx.check_poll(5, 2.0, lambda x: x, sudo_get_server_status,
                                pid_file)

    def stop(self):
        self.ctx.r(sudo_run_program, [SERVICE_EXE, self._get_service_name(), "stop"])
        # wait up to 10 seconds for process to stop
        self.ctx.check_poll(5, 2.0, lambda x: not x, is_running, self._get_service_name())

    def is_running(self):
        return self.ctx.rv(is_running, self._get_service_name())

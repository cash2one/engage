"""Resource manager for easy_install packages. 
"""

import commands
import os
import re

import fixup_python_path
import engage.drivers.service_manager as service_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.utils.path
import engage.utils.process as iuprocess
import engage.utils.log_setup
from engage.drivers.password_repo_mixin import PasswordRepoMixin
from engage.drivers.genforma.python import is_module_installed

from engage.drivers.standard.rabbitmq__2_4.driver import get_rabbitmq_executable
from engage.drivers.action import *
import engage.drivers.genforma.easy_install as easy_install

from engage.utils.user_error import UserError, ScriptErrInf
import gettext
_ = gettext.gettext

logger = engage.utils.log_setup.setup_script_logger(__name__)

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_ADD_USER = 2
ERR_ADD_VHOST = 3

define_error(ERR_ADD_USER,
             _("error adding rabbitmq user %(user)s in celery install for resource %(id)s"))
define_error(ERR_ADD_VHOST,
             _("error adding rabbitmq vhost %(vhost)s in celery install for resource %(id)s"))


def make_context(resource_json, sudo_password_fn, dry_run=False):
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=sudo_password_fn,
                  dry_run=dry_run)
    ctx.check_port("config_port",
                   username=str,
                   password=str)
    ctx.check_port("input_ports.host",
                   sudo_password=str,
                   os_type=str)
    ctx.check_port("input_ports.broker",
                   broker=str,
                   BROKER_HOST=str,
                   BROKER_PORT=str) # port should be int, but need to change in rabbitmq first
    return ctx


class Manager(service_manager.Manager, PasswordRepoMixin):
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(),
                                self._get_sudo_password,
                                dry_run=dry_run)
        self.started = False

    
    def validate_pre_install(self):
	pass

    def is_installed(self):
        return self.ctx.rv(is_module_installed, "celery")


    def install(self, package):
        r = self.ctx.r
        r(easy_install.install_package, package)

    def validate_post_install(self):
	assert self.ctx.rv(is_module_installed, "celery") or self.ctx.dry_run, \
               "Unable to import celery_package"

    def start(self):
        r = self.ctx.r
        rv = self.ctx.rv
        p = self.ctx.props
        # set up rabbitmq connection
        rabbitmqctl = get_rabbitmq_executable(p.input_ports.host)
        # the following commands run as root
        pat = re.escape('Error: {user_already_exists,<<"' + p.config_port.username + '">>}')
        (rc, re_map) = rv(sudo_run_program_and_scan_results,
                          [rabbitmqctl, 'add_user', p.config_port.username,
                           p.config_port.password],
                          {"pw_already_exists": pat},
                          log_output=True)
        if (not self.ctx.dry_run) and rc!=0 and re_map['pw_already_exists']==False:
            raise UserError(errors[ERR_ADD_USER],
                            msg_args={"user":p.config_port.username,
                                      "id":p.id},
                            developer_msg="rc was %d" % rc)
        pat = re.escape('Error: {vhost_already_exists,<<"' +
                        p.config_port.vhost + '">>}')
        (rc, re_map) = rv(sudo_run_program_and_scan_results,
                          [rabbitmqctl, 'add_vhost', p.config_port.vhost],
                          {"vhost_already_exists":pat},
                          log_output=True)
        if (not self.ctx.dry_run) and rc!=0 and \
               re_map["vhost_already_exists"]==False:
            raise UserError(errors[ERR_ADD_VHOST],
                            msg_args={"vhost":p.config_port.vhost,
                                      "id":p.id},
                            developer_msg="rc was %d" % rc)
        r(sudo_run_program,
          [rabbitmqctl, 'set_permissions', '-p',
           p.config_port.vhost, p.config_port.username,
           '.*', '.*', '.*'])
        self.started = True
        # no more root
        # make config file
        _format_str = \
"""BROKER_HOST = "%(hostname)s"
BROKER_PORT = %(portname)s
BROKER_USER = "%(username)s"
BROKER_PASSWORD = "%(password)s"
BROKER_VHOST = "%(vhost)s"
CELERY_RESULT_BACKEND = "amqp"
             """
        substitutions = {
            "hostname" : p.input_ports.broker.BROKER_HOST,  
            "portname" : p.input_ports.broker.BROKER_PORT,  
            "username" : p.config_port.username,  
            "password" : p.config_port.password,  
            "vhost" : p.config_port.vhost,  
        }
        # Do nothing: celeryd will be started from django's management system
        # JF: Rupak, do we need to write out config file file?

    def is_running(self):
        return self.started

    def stop(self):
        r = self.ctx.r
        rv = self.ctx.rv
        p = self.ctx.props
        # get rid of rabbitmq bindings
        rabbitmqctl = get_rabbitmq_executable(p.input_ports.host)
        # the following commands run as root
        r(sudo_run_program,
          [rabbitmqctl, 'delete_user', p.config_port.username])
        r(sudo_run_program,
          [rabbitmqctl, 'delete_vhost', p.config_port.vhost])
        self.started = False

"""Service manager for apache, linux version"""

import os
import os.path
import sys
import re
import time

import fixup_python_path
import engage.drivers.service_manager as service_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.utils.process as iuprocess
import engage.utils.log_setup
import aptget
from engage.drivers.password_repo_mixin import PasswordRepoMixin
from engage.drivers.genforma.apache_utils import start_apache, stop_apache, restart_apache, \
                                                 apache_is_running
from engage.drivers.action import *

logger = engage.utils.log_setup.setup_script_logger(__name__)

from engage.utils.user_error import ScriptErrInf, UserError, convert_exc_to_user_error

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_INSTALL_PKG_QUERY       = 1

define_error(ERR_INSTALL_PKG_QUERY,
             _("dpkg-query for installed package %(pkg)s failed."))

APT_PACKAGE_NAME = "apache2-mpm-prefork"


def make_context(resource_json, sudo_password_fn, dry_run=False):
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=sudo_password_fn,
                  dry_run=dry_run)
    ctx.check_port("input_ports.host",
                   hostname=str,
                   os_user_name=str,
                   sudo_password=str)
    ctx.check_port("output_ports.apache",
                   config_file=str,
                   additional_config_dir=str,
                   htpasswd_exe=str,
                   apache_user=str,
                   apache_group=str,
                   controller_exe=str)
    return ctx
    


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
    
    def is_installed(self):
        return self.ctx.rv(aptget.is_pkg_installed, APT_PACKAGE_NAME)

    def install(self, package):
        self.ctx.r(aptget.install, [APT_PACKAGE_NAME])
        self.validate_post_install()

    def validate_post_install(self):
        if not self.is_installed() and not self.ctx.dry_run:
            raise UserError(errors[ERR_INSTALL_PKG_QUERY],
                            msg_args={"pkg":APT_PACKAGE_NAME})

    def start(self):
        self.ctx.r(start_apache, self.ctx.props.output_ports.apache)

    def stop(self):
        self.ctx.r(stop_apache, self.ctx.props.output_ports.apache)

    def is_running(self):
        return self.ctx.rv(apache_is_running, self.ctx.props.output_ports.apache)
        

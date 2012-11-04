"""Resource manager for monit
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

from engage.drivers.action import *
import engage.drivers.service_manager as service_manager
import engage.drivers.resource_metadata as resource_metadata
import engage.utils.path as iupath
import engage_utils.process as procutils
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
ERR_MONIT_SETUP_FAILED = 1

define_error(ERR_MONIT_SETUP_FAILED,
             _("Install of Monit failed in resource %(id)s."))


def make_context(resource_json, dry_run=False):
    ctx = Context(resource_json, logger, __file__, dry_run=dry_run)
    ctx.check_port("input_ports.host",
                   os_type=str,
                   log_directory=str,
                   sudo_password=str)
    return ctx


class Manager(resource_manager.Manager):
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
        extracted_dir = package.extract(p.input_ports.host.genforma_home, desired_common_dirname=self.config.home_dir)
        monit_dir = os.path.join(p.input_ports.host.genforma_home, 'monit')
        monit_exe = os.path.join(monit_dir, 'monit')
        make = '/usr/bin/make'
        configure = os.path.join(monit_dir, 'configure') 
        if not (os.path.exists(monit_exe) and os.access(monit_exe, os.X_OK)):
            #run configure and make
            iuprocess.run_and_log_program([configure], { }, logger, cwd=monit_dir)
            iuprocess.run_and_log_program([make], { }, logger, cwd=monit_dir)
            # check that everything is now in place
            self.validate_post_install()

    def is_installed(self):
        p = self.ctx.props
        rv = self.ctx.rv
        # monit exists
        monit_dir = os.path.join(p.input_ports.host.genforma_home, 'monit')
        monit_exe = os.path.join(monit_dir, 'monit')
        if (os.path.exists(monit_exe) and os.access(monit_exe, os.X_OK)):
            return True
        else:
            return False

    def validate_post_install(self):
        if not self.is_installed() and not self.ctx.dry_run:
            raise UserError(errors[ERR_MONIT_SETUP_FAILED], msg_args={"id":self.ctx.props.id })


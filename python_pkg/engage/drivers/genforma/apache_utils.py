"""These are some common utilities for managing the apache webserver.
They should work across the different variants of apache (Linux, Mac pre-installed,
Mac ports) as long as you get the controller executable path from the apache
resource definition's output port.
"""

import sys
import time
import os.path
import re

import fixup_python_path
import engage.utils.process as iuprocess
import engage.utils.file as fileutils
import engage.drivers.action as action

import engage.utils.log_setup
logger = engage.utils.log_setup.setup_engage_logger(__name__)

from engage.utils.user_error import EngageErrInf, UserError, convert_exc_to_user_error

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_APACHE_STATUS           = 3
ERR_APACHE_RESTART          = 4
ERR_APACHE_HTPASSWD         = 5

define_error(ERR_APACHE_STATUS,
             _("An error occurred when attempting to obtain the status of the Apache webserver in resource %(id)s"))
define_error(ERR_APACHE_HTPASSWD,
             _("An error occurred when running htpasswd in resource %(id)s. htpasswd executable was '%(exe)s', password file was '%(file)s'"))


class start_apache(action.Action):
    NAME="apache_utils.start_apache"
    def __init__(self, ctx):
        super(start_apache, self).__init__(ctx)
    
    def run(self, apache_config):
        """Start the apache server. apache_config is the port
        containing the apache config variables.
        """
        controller_exe = apache_config.controller_exe
        action._check_file_exists(controller_exe, self)
        iuprocess.run_sudo_program([controller_exe, "start"],
                                   self.ctx._get_sudo_password(self),
                                   self.ctx.logger)

    def dry_run(self, apache_config):
        controller_exe = apache_config.controller_exe
        action._check_file_exists(controller_exe, self)
        self.ctx.logger.debug("%s start" % controller_exe)


class stop_apache(action.Action):
    NAME="apache_utils.stop_apache"
    def __init__(self, ctx):
        super(stop_apache, self).__init__(ctx)
    
    def run(self, apache_config):
        """Stop the apache server. apache_config is the port
        containing the apache config variables.
        """
        controller_exe = apache_config.controller_exe
        action._check_file_exists(controller_exe, self)
        iuprocess.run_sudo_program([controller_exe, "stop"],
                                   self.ctx._get_sudo_password(self),
                                   self.ctx.logger)

    def dry_run(self, apache_config):
        controller_exe = apache_config.controller_exe
        action._check_file_exists(controller_exe, self)
        self.ctx.logger.debug("%s stop" % controller_exe)


class restart_apache(action.Action):
    NAME="apache_utils.restart_apache"
    def __init__(self, ctx):
        super(restart_apache, self).__init__(ctx)
    
    def run(self, apache_config):
        """Restart the apache server. apache_config is the port
        containing the apache config variables.
        """
        controller_exe = apache_config.controller_exe
        action._check_file_exists(controller_exe, self)
        ## iuprocess.run_sudo_program([controller_exe, "restart"],
        ##                            self.ctx._get_sudo_password(self),
        ##                            self.ctx.logger)
        # The restart command doesn't seem to work in some
        # situations (see ticket #203). We do a real stop and start
        # instead.
        iuprocess.run_sudo_program([controller_exe, "stop"],
                                   self.ctx._get_sudo_password(self),
                                   self.ctx.logger)
        iuprocess.run_sudo_program([controller_exe, "start"],
                                   self.ctx._get_sudo_password(self),
                                   self.ctx.logger)

    def dry_run(self, apache_config):
        controller_exe = apache_config.controller_exe
        action._check_file_exists(controller_exe, self)
        self.ctx.logger.debug("%s stop" % controller_exe)
        self.ctx.logger.debug("%s start" % controller_exe)


def _macports_apache_is_running(controller_exe, sudo_password):
    matches = iuprocess.find_matching_processes(['/opt/local/apache2/bin/httpd',])
    if len(matches)>0:
        logger.debug("Apache status is up (found %d httpd processes)" % len(matches))
        return True
    else:
        logger.debug("Apache status is down")
        return False


class apache_is_running(action.ValueAction):
    NAME="apache_utils.apache_is_running"
    def __init__(self, ctx):
        super(apache_is_running, self).__init__(ctx)
        
    def run(self, apache_config, timeout_tries=5, time_between_tries=2.0):
        """If you check whether apache is running just after it was (re)started, it may report that it
        isn't running when it is infact running. This is because apache takes a few seconds before it writes
        its pid file out. Thus, we need to use a timeout to see if apache could really be up when the status
        command reports that it is down. If you haven't just started apache, you can probably reduce the
        timeout duration. Note that time_between_tries is in seconds, so the default timeout is 10 seconds.
        """
        controller_exe = apache_config.controller_exe
        action._check_file_exists(controller_exe, self)
        if controller_exe=='/opt/local/apache2/bin/apachectl':
            """The apachectl for macports is broken. We determine whether apache is
            running by looking for the process
            """
            return _macports_apache_is_running(controller_exe, self.ctx._get_sudo_password(self))

        for i in range(timeout_tries):
            try:
                iuprocess.run_sudo_program([controller_exe, "status"],
                                           self.ctx._get_sudo_password(self), self.ctx.logger)
                self.ctx.logger.debug("Apache status is up")
                return True
            except iuprocess.SudoExcept, e:
                if e.rc == 1: # this means the server is down
                    self.ctx.logger.debug("Apache status is down")
                    if i != (timeout_tries-1): time.sleep(time_between_tries)
                else:
                    exc_info = sys.exc_info()
                    self.ctx.logger.exception("Unexpected exception when checking for apache status occurred in resource %s" %
                                              self.ctx.props.id)
                    raise convert_exc_to_user_error(exc_info, errors[ERR_APACHE_STATUS], nested_exc_info=e.get_nested_exc_info(),
                                                    msg_args={"id":self.ctx.props.id})
        # if we exit the loop, we can conclude that apache is really not running
        return False

    def dry_run(self, apache_config, timeout_tries=5, time_between_tries=2.0):
        controller_exe = apache_config.controller_exe
        action._check_file_exists(controller_exe, self)
        return False


class add_apache_config_file(action.Action):
    """Copy an apache config file (src_config_file) to the apache_config_directory
    and set the permissions to match that of the master config file.
    If new_name is specified, use that as the name. Otherwise,
    use the name of src_config_file.
    """
    NAME="apache_utils.add_apache_config_file"
    def __init__(self, ctx):
        super(add_apache_config_file, self).__init__(ctx)
        
    def run(self, src_config_file, apache_config, new_name=None):
        (uid, gid, mode) = fileutils.get_file_permissions(apache_config.config_file)
        if new_name:
            target_path = os.path.join(apache_config.additional_config_dir,
                                       new_name)
        else:
            target_path = os.path.join(apache_config.additional_config_dir,
                                       os.path.basename(src_config_file))
        iuprocess.sudo_copy([src_config_file, target_path], self.ctx._get_sudo_password(self), self.ctx.logger)
        iuprocess.sudo_set_file_permissions(target_path, uid, gid, mode, self.ctx.logger, self.ctx._get_sudo_password(self))

    def dry_run(self, src_config_file, apache_config, new_name=None):
        pass


class run_htpasswd(action.Action):
    """Run the htpasswd command. If sudo_password is provided, we run this under sudo.
    Otherwise, just use the current user. Specifies the -c option if the file does
    not exist.
    """
    NAME="apache_utils.run_htpasswd"
    def __init__(self, ctx):
        super(run_htpasswd, self).__init__(ctx)
        
    def run(self, password_file, username, password, apache_config):
        class LogProxy:
            """We need to wrap the logger and capture any action events, as those may
            contain the password.
            """
            def __init__(self, logger):
                #Set attribute.
                self._logger = logger
            def __getattr__(self, attrib):
                if attrib == "action":
                    return self.action
                else:
                    return getattr(self._logger, attrib)
            def action(self, msg):
                pass

        htpasswd_exe = apache_config.htpasswd_exe
        action._check_file_exists(htpasswd_exe, self)
        if os.path.exists(password_file):
            cmd = [htpasswd_exe, "-b", password_file, username, password]
        else:
            cmd = [htpasswd_exe, "-b", "-c", password_file, username, password]
        if self.ctx._get_sudo_password(self)==None or iuprocess.is_running_as_root():
            self.ctx.logger.action("%s <password>" % " ".join(cmd[0:-1]))
            rc = iuprocess.run_and_log_program(cmd, {}, LogProxy(self.ctx.logger))
            if rc != 0:
                raise UserError(errors[ERR_APACHE_HTPASSWD],
                                msg_args={"exe": htpasswd_exe,
                                          "file": password_file,
                                          "id":self.ctx.props.id},
                                developer_msg="return code was %d" % rc)
        else:
            try:
                logger.action("sudo %s <password>" % " ".join(cmd[0:-1]))
                iuprocess.run_sudo_program(cmd, self.ctx._get_sudo_password(self),
                                           LogProxy(self.ctx.logger))
            except Exception, e:
                exc_info = sys.exc_info()
                logger.exception("exception in htpasswd: %s, resource %s" % (e.__repr__(),
                                                                             ctx.props.id))
                raise convert_exc_to_user_error(exc_info, errors[ERR_APACHE_HTPASSWD],
                                                msg_args={"exe": htpasswd_exe,
                                                          "file": password_file,
                                                          "id":self.ctx.props.id},
                                                developer_msg="exception" % e.__repr__())
            
        def dry_run(self, password_file, username, password, apache_config):
            htpasswd_exe = apache_config.htpasswd_exe
            action._check_file_exists(htpasswd_exe, self)
            if os.path.exists(password_file):
                cmd = [htpasswd_exe, "-b", password_file, username, password]
            else:
                cmd = [htpasswd_exe, "-b", "-c", password_file, username, password]
            self.ctx.logger.debug(" ".join(cmd))

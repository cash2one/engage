
"""Resource manager for MoinMoin 1.9

This lets you install the wiki either using its own local webserver or using apache
via mod_wsgi. If running with apache, you have the option to use apache authentication.
Currently, we don't do the setup of the password file for you, beyond creating the file
and putting in the user root with password change_me. Be sure to change this!
"""

import sys
import os
import os.path
import re
import string
import grp
import unittest

# fix path if necessary (if running from source or running as test)
try:
    import engage.utils
except:
    sys.exc_clear()
    dir_to_add_to_python_path = os.path.abspath((os.path.join(os.path.dirname(__file__), "../../../..")))
    sys.path.append(dir_to_add_to_python_path)

import engage.drivers.service_manager as service_manager
import engage.drivers.utils
from engage.drivers.action import *
from engage.utils.path import check_installable_to_target_dir
import engage.utils.process as processutils
import engage.utils.file as fileutils
import engage.drivers.genforma.apache_utils as apache_utils
from engage.drivers.password_repo_mixin import PasswordRepoMixin

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
ERR_DIR_NOT_FOUND        = 1
ERR_WIKISERVER_NOT_FOUND = 2
ERR_MOIN_ADD_SETTINGS    = 3
ERR_CFG_FILE_MISSING     = 4
ERR_MUST_SELECT_APACHE   = 5
ERR_MOIN_EXITED          = 6
ERR_NO_PIDFILE           = 7

define_error(ERR_DIR_NOT_FOUND,
             _("MoinMoin home directory %(dir)s not found"))
define_error(ERR_WIKISERVER_NOT_FOUND,
             _("MoinMoin wiki server script %(file)s not found"))
define_error(ERR_MOIN_ADD_SETTINGS,
             _("Error adding settings to MoinMoin configuration file %(file)s in resource %(id)s"))
define_error(ERR_CFG_FILE_MISSING,
             _("Unable to find MoinMoin configuration file at %(file)s"))
define_error(ERR_MUST_SELECT_APACHE,
             _("To use Apache Authentication, you must select Apache as the webserver"))
define_error(ERR_MOIN_EXITED,
             _("MoinMoin server exited after startup in resource %(id)s"))
define_error(ERR_NO_PIDFILE,
             _("Apache started, but pidfile %(pidfile)s was not created in resource %(id)s"))


# setup logging
from engage.utils.log_setup import setup_engage_logger
logger = setup_engage_logger(__name__)


# this is used by the package manager to locate the packages.json
# file associated with the driver
def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)


# timeouts for checking server liveness after startup
TIMEOUT_TRIES = 5
TIME_BETWEEN_TRIES = 2.0


def make_context(resource_json, sudo_password_fn, dry_run=False):
    """This function sets up the context, validates the properties,
    and adds computed properties.
    """
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=sudo_password_fn, dry_run=dry_run)
    # Check for required props. We don't have to do this,
    # but it makes for better error checking.
    ctx.checkp("input_ports.python.home")
    ctx.check_port("config_port",
                   home=str,
                   superuser_name=str,
                   front_page=str,
                   use_apache_authentication=str)
    ctx.check_port("input_ports.webserver_adapter",
                   type=str,
                   config_file=str,
                   additional_config_dir=str,
                   group=str,
                   controller_exe=str,
                   htpasswd_exe=str)
    ctx.checkp("output_ports.moinmoin.log_directory")
    # add a shortcut for the home dir since we use it a lot. We'll also make it
    # an absolute path, although when run from the installer, we should get it that
    # way anyway.
    ctx.add("home",
            os.path.abspath(os.path.expanduser(ctx.props.config_port.home)))
    #  add computed props
    ctx.add("server_script", os.path.join(ctx.props.home, "wikiserver.py"))
    ctx.add("log_file", os.path.join(ctx.props.output_ports.moinmoin.log_directory,
                                     "moinmoin.log"))
    ctx.add("log_config_file", os.path.join(ctx.props.home,
                                            "wiki/config/logging/engage_logging.cfg"))
    ctx.add("pid_file", os.path.join(ctx.props.home, "moinmoin.pid"))
    ctx.add("config_file", os.path.join(ctx.props.home, "wikiconfig.py"))
    ctx.add("use_apache_authentication", ctx.props.config_port.use_apache_authentication=="yes")
    ctx.add("password_file", os.path.join(ctx.props.home, "passwords"))
    ctx.add("wsgi_file", os.path.join(ctx.props.home, "wiki/server/engage_moin.wsgi"))
    return ctx


def run_validate_preinstall(ctx):
    ctx.r(check_installable_to_dir, ctx.props.home)
    if ctx.props.use_apache_authentication and \
       ctx.props.input_ports.webserver_adapter.type!="apache":
        raise UserError(errors[ERR_MUST_SELECT_APACHE])


def _setup_apache_config_files(ctx):
    # setup some shorthands
    r = ctx.r
    rv = ctx.rv
    p = ctx.props
    # instantiate templates
    r(template, "engage_logging.cfg", p.log_config_file)
    r(template, "engage_moin.wsgi", p.wsgi_file)
    if p.use_apache_authentication:
        apache_cfg_data = rv(get_template_subst, "moinmoin_apache_auth.conf")
    else:
        apache_cfg_data = rv(get_template_subst, "moinmoin_apache.conf")
    with fileutils.NamedTempFile(data=apache_cfg_data) as f:
        r(apache_utils.add_apache_config_file, f.name,
              p.input_ports.webserver_adapter,
              new_name="moinmoin_apache.conf")

    # set group perms to let webserver user to access files
    ws_group = p.input_ports.webserver_adapter.group
    r(sudo_ensure_user_in_group, ws_group)
    r(ensure_shared_perms, os.path.join(p.home, "wiki"),
          ws_group, writable_to_group=True)
    r(ensure_shared_perms, p.output_ports.moinmoin.log_directory,
          ws_group, writable_to_group=True)

    # create password file
    if p.use_apache_authentication:
        r(apache_utils.run_htpasswd,p.password_file, "root", "change_me",
          p.input_ports.webserver_adapter)
        # after running htpasswd, the file is owned by root. Set
        # perms so current user owns it, with access rights to web
        # server group.
        if not ctx.dry_run:
            r(sudo_set_file_permissions, p.password_file, os.geteuid(),
              grp.getgrnam(ws_group).gr_gid, 0640)
          

@make_action
def add_moin_config_settings(self, config_file, settings, imports=None):
    # add the specified settings to the moinmoin config
    # file. The settings parameter should be a list of (name, value)
    # pairs.
    start_str = "# Add your configuration items here.\n"
    replacement = start_str + "\n".join(["    %s = %s" % (name, value) for
                                           (name, value) in settings]) + "\n"
    pattern_list = [(re.escape(start_str), replacement)]
    if imports:
        import_start_str = "from MoinMoin.config import multiconfig, url_prefix_static"
        additional_imports = import_start_str + "\n" + "\n".join(imports) + "\n"
        pattern_list += [(re.escape(import_start_str), additional_imports),]
        expected_substitutions = 2
    else:
        expected_substitutions = 1
    cnt = fileutils.subst_in_file(config_file, pattern_list)
    if cnt != expected_substitutions:
        raise UserError(errors[ERR_MOIN_ADD_SETTINGS], msg_args={"file":config_file,
                                                                 "id":self.ctx.props.id},
                        developer_msg="Expected %d substitution(s), got %d instead" %
                            (expected_substitutions, cnt))
    

class Manager(service_manager.Manager, PasswordRepoMixin):
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(), sudo_password_fn=self._get_sudo_password,
                                dry_run=dry_run)

    def validate_pre_install(self):
        run_validate_preinstall(self.ctx)

    def is_installed(self):
        return os.path.exists(self.ctx.props.home)
        
    def install(self, package):
        # some shorthands to reduce typing
        r = self.ctx.r
        p = self.ctx.props
        # do the work!
        r(extract_package_as_dir, package, p.home)
        r(check_file_exists, p.config_file)
        config_settings = [("superuser", "[u'%s',]" % p.config_port.superuser_name),
                           ("page_front_page", "u'%s'" % p.config_port.front_page)]
        if p.use_apache_authentication:
            config_settings.extend([("user_autocreate", "True"),
                                    ("auth", "[HTTPAuth(autocreate=True),]")])
            imports=["from MoinMoin.auth.http import HTTPAuth",]
        else:
            imports=None
        r(add_moin_config_settings, p.config_file, config_settings, imports)
        r(ensure_dir_exists, p.output_ports.moinmoin.log_directory)
        if p.input_ports.webserver_adapter.type == "apache":
            _setup_apache_config_files(self.ctx)
            r(apache_utils.restart_apache, p.input_ports.webserver_adapter)
        self.validate_post_install()

    def validate_post_install(self):
        self.ctx.r(check_dir_exists, self.ctx.props.home)
        self.ctx.r(check_file_exists, self.ctx.props.server_script)

    def start(self):
        """This is kind of hacky. Moin can either have a local server (which runs as a
        service) or can connected into apache via mod_wsgi. In the first case, we are running
        as a service. In the second case, we really aren't but have to pretend we are. To handle
        that, we just mimic apache's status and start/stop it in our start/stop commands.
        """
        r = self.ctx.r
        poll_rv = self.ctx.poll_rv
        p = self.ctx.props

        if p.input_ports.webserver_adapter.type == "apache":
            r(apache_utils.start_apache, p.input_ports.webserver_adapter)
            if os.uname()[0]=="Darwin":
                # On the mac, the apachectl program is not so reliable. We need
                # to wait until apache has created a pidfile before returning.
                # Otherwise, we might have trouble stopping it, if we try to stop
                # right away.
                if not poll_rv(TIMEOUT_TRIES, TIME_BETWEEN_TRIES, lambda r: r,
                               get_path_exists, "/opt/local/apache2/logs/httpd.pid") \
                   and not self.ctx.dry_run:
                    raise UserError(errors[ERR_NO_PIDFILE],
                                    msg_args={"id":p.id, "pidfile":"/opt/local/apache2/logs/httpd.pid"})
        else:
            r(start_server, [p.input_ports.python.home, p.server_script], p.log_file, p.pid_file)
            started = poll_rv(TIMEOUT_TRIES, TIME_BETWEEN_TRIES, lambda r: r,
                              get_server_status, p.pid_file)
            if not started:
                raise UserError(errors[ERR_MOIN_EXITED],
                                msg_args={"id":p.id})

    def stop(self):
        r = self.ctx.r
        poll_rv = self.ctx.poll_rv
        p = self.ctx.props

        if p.input_ports.webserver_adapter.type == "apache":
            r(apache_utils.stop_apache, p.input_ports.webserver_adapter)
        else:
            pid = processutils.stop_server_process(self.pid_file, logger,
                                                self.metadata.id,
                                                timeout_tries=5, force_stop=False)
            if pid:
                logger.info("MoinMoin stop: server %s was not running" %
                            self.metadata.id)
            else:
                logger.info("MoinMoin server %s stopped successfully" %
                            self.metadata.id)

    def is_running(self):
        rv = self.ctx.rv
        p = self.ctx.props
        if p.input_ports.webserver_adapter.type == "apache":
            return rv(apache_utils.apache_is_running, p.input_ports.webserver_adapter)
        else:
            return rv(get_server_status, p.pid_file)



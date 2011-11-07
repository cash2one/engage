"""Actions defined for Java Web Applications that are installed into
Tomcat.
"""
import os
import os.path
import urllib

import fixup_python_path
from engage.drivers.action import *
from engage.drivers.action import _check_file_exists
import engage.utils.http as httputils

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
ERR_TOMCAT_STATREQ     = 1
ERR_TOMCAT_BADSTAT     = 2
ERR_TOMCAT_NOSTAT      = 3
ERR_TOMCAT_START       = 4
ERR_TOMCAT_STOP        = 5
ERR_TOMCAT_DEPLOY      = 6
ERR_TOMCAT_UNDEPLOY    = 7

define_error(ERR_TOMCAT_STATREQ,
             _("An error occurred when attempting to obtain the status of the Apache Tomcat applications in resource %(id)s: %(status)s"))
define_error(ERR_TOMCAT_BADSTAT,
             _("Tomcat server returned unexpected status '%(stat)s' for application '%(path)s' in resource %(id)s"))
define_error(ERR_TOMCAT_NOSTAT,
             _("Tomcat server did not return a status entry for application '%(path)s' in resource %(id)s. Perhaps that application was not deployed successfully."))
define_error(ERR_TOMCAT_START,
             _("Tomcat server was unable to start application '%(path)s' for resource %(id)s: %(response)s."))
define_error(ERR_TOMCAT_STOP,
             _("Tomcat server was unable to stop application '%(path)s' for resource %(id)s: %(response)s."))
define_error(ERR_TOMCAT_DEPLOY,
             _("Tomcat server was unable to deploy application '%(path)s' for resource %(id)s: %(response)s."))
define_error(ERR_TOMCAT_UNDEPLOY,
             _("Tomcat server was unable to undeploy application '%(path)s' for resource %(id)s: %(response)s."))


MANAGER_REALM = "Tomcat Manager Application"

def _make_request(uri, user, password):
    return httputils.make_request_with_basic_authentication(uri, MANAGER_REALM,
                                                            user, password,
                                                            logger=logger)

_args_format_string = \
'%(name)s {"hostname":"%(hostname)s", "manager_port":%(port)d, "admin_user":"%(user)s", "admin_password":"****"}, %(app_path)s'

def status_request_fn(resource_id, server_host, server_port, app_path,
                      user, password, install_check=False):
    """Return true if app running, false if stopped. Throw an error
    otherwise. If install_check is True, then we are checking whether
    the app is installed at all. If not, return None instead of throwing
    an error.
    """
    result = _make_request("http://%s:%d/manager/list" % (server_host, server_port),
                          user, password)
    if result[0:2]!="OK":
        status = result.split("\n")[0]
        logger.error("Tomcat status request failed: %s" % status)
        raise UserError(errors[ERR_TOMCAT_STATREQ],
                        msg_args={"id":resource_id,
                                  "status": status})
    content = result.split("\n")[1:]
    for line in content:
        fields = line.split(":")
        if fields[0]!=app_path:
            continue
        status = fields[1]
        if status=="running":
            return True
        elif status=="stopped":
            return False
        else:
            raise UserError(errors[ERR_TOMCAT_BADSTAT],
                            msg_args={"id":resource_id,
                                      "status":status,
                                      "path":app_path})
    # if we get here, didn't find the app
    if install_check:
        return None
    else:
        raise UserError(errors[ERR_TOMCAT_NOSTAT],
                        msg_args={"id":resource_id,
                                  "path":app_path})
        
class status_request(ValueAction):
    """ValueAction: Request the status of the specified Tomcat web application.
    Takes the 'tomcat' output port from the apache-tomcat resource
    and the application path (url).
    """
    NAME = "tomcat_utils.status_request"
    def __init__(self, ctx):
        ValueAction.__init__(self, ctx)

    def run(self, tomcat_port, app_path, admin_password):
        return status_request_fn(self.ctx.props.id,
                                 tomcat_port.hostname,
                                 tomcat_port.manager_port,
                                 app_path,
                                 tomcat_port.admin_user,
                                 admin_password)

    def dry_run(self, tomcat_port, app_path, admin_password):
        return None
        
    def format_action_args(action_name, tomcat_port, app_path, admin_password):
        return _args_format_string % {
            "name":action_name,
            "hostname": tomcat_port.hostname,
            "port":tomcat_port.manager_port,
            "user":tomcat_port.admin_user,
            "app_path":app_path
            }

class is_app_installed(ValueAction):
    """ValueAction: Return True if app is installed (either stopped or
    running) and False otherwise.
    Takes the 'tomcat' output port from the apache-tomcat resource
    and the application path (url).
    """
    NAME = "tomcat_utils.is_app_installed"
    def __init__(self, ctx):
        ValueAction.__init__(self, ctx)

    def run(self, tomcat_port, app_path, admin_password):
        result = status_request_fn(self.ctx.props.id,
                                   tomcat_port.hostname,
                                   tomcat_port.manager_port,
                                   app_path,
                                   tomcat_port.admin_user,
                                   admin_password,
                                   install_check=True)
        return result!=None

    def dry_run(self, tomcat_port, app_path, admin_password):
        return None
        
    def format_action_args(action_name, tomcat_port, app_path, admin_password):
        return _args_format_string % {
            "name":action_name,
            "hostname": tomcat_port.hostname,
            "port":tomcat_port.manager_port,
            "user":tomcat_port.admin_user,
            "app_path":app_path
            }


class WarAction(Action):
    """Base class for WAR file actions.
    """
    def __init__(self, ctx):
        Action.__init__(self, ctx)

    def dry_run(self, tomcat_port, app_path, admin_password):
        return None
        
    def format_action_args(action_name, tomcat_port, app_path, admin_password):
        return _args_format_string % {
            "name":action_name,
            "hostname": tomcat_port.hostname,
            "port":tomcat_port.manager_port,
            "user":tomcat_port.admin_user,
            "app_path":app_path
            }

    
def start_app_fn(resource_id, server_host, server_port, app_path,
                 user, password):
    result = _make_request("http://%s:%d/manager/start?%s" %
                           (server_host, server_port,
                            urllib.urlencode({"path":app_path})),
                          user, password)
    if result[0:2]!="OK":
        raise UserError(errors[ERR_TOMCAT_START],
                        msg_args={"id":resource_id,
                                  "path":app_path,
                                  "response": result})

class start_app(WarAction):
    """Action: Start a java web appliction via the tomcat manager http api.
    """
    NAME = "tomcat_utils.start_app"
    def __init__(self, ctx):
        WarAction.__init__(self, ctx)

    def run(self, tomcat_port, app_path, admin_pasword):
        start_app_fn(self.ctx.props.id,
                     tomcat_port.hostname,
                     tomcat_port.manager_port,
                     app_path,
                     tomcat_port.admin_user,
                     admin_password)

        
def stop_app_fn(resource_id, server_host, server_port, app_path,
                user, password):
    result = _make_request("http://%s:%d/manager/stop?%s" %
                           (server_host, server_port,
                            urllib.urlencode({"path":app_path})),
                          user, password)
    if result[0:2]!="OK":
        raise UserError(errors[ERR_TOMCAT_STOP],
                        msg_args={"id":resource_id,
                                  "path":app_path,
                                  "response": result})

class stop_app(WarAction):
    """Action: Stop a java web appliction via the tomcat manager http api.
    """
    NAME = "tomcat_utils.stop_app"
    def __init__(self, ctx):
        WarAction.__init__(self, ctx)

    def run(self, tomcat_port, app_path, admin_password):
        stop_app_fn(self.ctx.props.id,
                    tomcat_port.hostname,
                    tomcat_port.manager_port,
                    app_path,
                    tomcat_port.admin_user,
                    admin_password)


def deploy_app_fn(resource_id, server_host, server_port, app_path,
                  app_war_file, user, password, update=False, tag=None):
    params = {"path":app_path}
    params["war"] = "file:" + \
                    os.path.abspath(os.path.expanduser(app_war_file))
    if update:
        params["update"] = "true"
    if tag:
        params["tag"] = tag
              
    uri = "http://%s:%d/manager/deploy?%s" % \
              (server_host, server_port,
               urllib.urlencode(params))
    with open(app_war_file, "rb") as f:
        result = \
            httputils.make_request_with_basic_authentication(
                uri, MANAGER_REALM, user, password,
                logger=logger)
            # This version tried to send the file directly using PUT.
            # Unfortunately, the python code seems to be expecting unicode
            # data and errors out. Not sure what kind of encoding the
            # tomcat side is expecting.
            ## httputils.make_request_with_basic_authentication(
            ##     uri, MANAGER_REALM, user, password,
            ##     data=f.read(),
            ##     content_type="application/java-archive",
            ##     request_method="PUT",
            ##     logger=logger)
    if result[0:2]!="OK":
        raise UserError(errors[ERR_TOMCAT_DEPLOY],
                        msg_args={"id":resource_id,
                                  "path":app_path,
                                  "response": result},
                        developer_msg="uri=%s" % uri)


_deploy_args_format_string = \
'%(name)s {"hostname":"%(hostname)s", "manager_port":%(port)d, "admin_user":"%(user)s", "admin_password":"****"}, %(app_path)s, %(warfile)s, update=%(update)s, tag=%(tag)s'


class deploy_app(Action):
    """Action: Deploy a java web appliction via the tomcat manager http api.
    """
    NAME = "tomcat_utils.deploy_app"
    def __init__(self, ctx):
        Action.__init__(self, ctx)

    def run(self, tomcat_port, app_path, warfile_path, admin_password,
            update=False, tag=None):
        _check_file_exists(warfile_path, self)
        deploy_app_fn(self.ctx.props.id,
                      tomcat_port.hostname,
                      tomcat_port.manager_port,
                      app_path,
                      warfile_path,
                      tomcat_port.admin_user,
                      admin_password,
                      update=update, tag=tag)

    def dry_run(self, tomcat_port, app_path, warfile_path,
                admin_password, update=False,
            tag=None):
        _check_file_exists(warfile_path, self)

    def format_action_args(action_name, tomcat_port, app_path, warfile_path,
                           admin_password,
                           update=False, tag=None):
        return _deploy_args_format_string % {
            "name":action_name,
            "hostname": tomcat_port.hostname,
            "port":tomcat_port.manager_port,
            "user":tomcat_port.admin_user,
            "app_path":app_path,
            "warfile":warfile_path,
            "update":str(update),
            "tag":str(tag)
            }


def undeploy_app_fn(resource_id, server_host, server_port, app_path,
                    user, password):
    result = _make_request("http://%s:%d/manager/undeploy?%s" %
                           (server_host, server_port,
                            urllib.urlencode({"path":app_path})),
                          user, password)
    if result[0:2]!="OK":
        raise UserError(errors[ERR_TOMCAT_UNDEPLOY],
                        msg_args={"id":resource_id,
                                  "path":app_path,
                                  "response": result})

class updeploy_app(WarAction):
    """Action: Updeploy a java web appliction via the tomcat manager http api.
    """
    NAME = "tomcat_utils.undeploy_app"
    def __init__(self, ctx):
        WarAction.__init__(self, ctx)

    def run(self, tomcat_port, app_path, admin_password):
        undeploy_app_fn(self.ctx.props.id,
                        tomcat_port.hostname,
                        tomcat_port.manager_port,
                        app_path,
                        tomcat_port.admin_user,
                        admin_password)

@make_value_action
def _check_tomcat_url(self, tomcat_port):
    if httputils.check_url(tomcat_port.hostname,
                           tomcat_port.manager_port, "/",
                           self.ctx.logger):
        return True
    else:
        return False


def ensure_tomcat_running(ctx, tomcat_port):
    """This is a sequence of actions that verifies that tomcat
    is up, starting it if necessary.
    """
    pid = ctx.rv(get_server_status, tomcat_port.pid_file)
    if pid == None:
        startup_script = os.path.join(tomcat_port.home, "bin/startup.sh")
        ctx.r(run_program, [startup_script],
              cwd=os.path.dirname(startup_script))
        # wait for pid file
        ctx.check_poll(10, 1.5, lambda pid: pid!=None,
                       get_server_status, tomcat_port.pid_file)
        ctx.logger.debug("Tomcat started successfully")
    else:
        ctx.logger.debug("Tomcat already running")
    # wait for a response on the tomcat url
    ctx.check_poll(10, 1.5, lambda rsp: rsp,
                   _check_tomcat_url, tomcat_port)
        

def ensure_tomcat_stopped(ctx, tomcat_port):
    """This is a sequence of actions that verifies tomcat is stopped,
    stopping it if necessary.
    """
    pid = ctx.rv(get_server_status, tomcat_port.pid_file)
    if pid != None:
        shutdown_script = os.path.join(tomcat_port.home, "bin/shutdown.sh")
        ctx.r(run_program, [shutdown_script],
              cwd=os.path.dirname(shutdown_script))
        # wait for pid file
        ctx.check_poll(10, 1.5, lambda pid: pid==None,
                       get_server_status, tomcat_port.pid_file)
        ctx.logger.debug("Tomcat stopped successfully")
    else:
        ctx.logger.debug("Tomcat already stopped")



def tst_lifecycle(server_host, server_port, app_path, warfile_path,
                  user, password):
    """Given a warfile and the server info, test the full lifecycle.
    """
    rid = os.path.basename(warfile_path)
    print "deploying app"
    deploy_app_fn(rid, server_host, server_port, app_path,
                  warfile_path, user, password)
    status = status_request_fn(rid, server_host, server_port, app_path,
                               user, password)
    assert status==True, "App was not started in deployment"
    print "stopping app"
    stop_app_fn(rid, server_host, server_port, app_path, user, password)
    status = status_request_fn(rid, server_host, server_port, app_path,
                               user, password)
    assert status==False, "App was not stopped"
    print "restarting app"
    start_app_fn(rid, server_host, server_port, app_path, user, password)
    status = status_request_fn(rid, server_host, server_port, app_path,
                               user, password)
    assert status==True, "App was not restarted"
    print "undeploying app"
    undeploy_app_fn(rid, server_host, server_port, app_path, user, password)
    print "lifecycle test complete"


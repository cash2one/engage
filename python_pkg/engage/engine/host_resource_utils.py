"""Utiltities for dealing with resource instances cooresponding to hosts.
"""

import os
import os.path
import shutil
import copy

# fix path if necessary (if running from source or running as test)
import fixup_python_path

import engage.utils.system_info as system_info
import engage.utils.process as procutils
from engage.utils.user_error import UserError, EngageErrInf
from engage.utils.find_exe import find_python_executable
from engage.utils.log_setup import setup_engine_logger
logger = setup_engine_logger(__name__)

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info


ERR_SLAVE_BOOTSTRAP = 1
ERR_BAD_OS          = 2

define_error(ERR_SLAVE_BOOTSTRAP,
             _("Bootstrap of slave node %(host)s failed"))
define_error(ERR_BAD_OS,
             _("Sorry, you are running on an unsupported Operating System. Valid choices are %(choices)s."))

os_choices = [system_info.LINUX_UBUNTU_11, system_info.LINUX_UBUNTU_11_64BIT,
              system_info.LINUX_UBUNTU_10_64BIT,
              system_info.MACOSX_10_5, system_info.MACOSX_10_6]


def get_target_machine_resource(deployment_home, log_directory):
    machine_info = system_info.get_machine_info(os_choices)
    if not machine_info.has_key("os"):
        raise UserError(errors[ERR_BAD_OS],
                        msg_args={"choices":os_choices})
    tr = system_info.get_target_machine_resource("master-host",
                                                 machine_info["hostname"],
                                                 machine_info["username"],
                                                 "GenForma/%s/sudo_password" % machine_info["username"],
                                                 machine_info["os"], machine_info["private_ip"])
    tr['config_port']['genforma_home'] = deployment_home
    tr['config_port']['log_directory'] = log_directory
    return tr


def setup_slave_host(resource, master_deployment_home,
                     password_file, password_salt_file):
    bootstrap_script = os.path.abspath(os.path.join(master_deployment_home,
                                                    "engage/bootstrap.py"))
    assert os.path.exists(bootstrap_script), "Can't find bootstrap script %s" % \
                                             bootstrap_script
    python_exe = find_python_executable(logger)
    
    dh = resource["config_port"]["genforma_home"]
    logger.info("Bootstrapping slave node %s" % resource["id"])
    deployed_nodes_root = os.path.dirname(dh)
    if not os.path.exists(deployed_nodes_root):
        os.makedirs(deployed_nodes_root)
    try:
        rc = procutils.run_and_log_program([python_exe, bootstrap_script, "-p",
                                            python_exe, dh], None, logger,
                                            cwd=os.path.dirname(bootstrap_script))
    except Exception, e:
        logger.exception("Error in slave bootstrap for %s: %s" % (e, resource["id"]))
        raise UserError(errors[ERR_SLAVE_BOOTSTRAP],
                        msg_args={"host":resource["id"]},
                        developer_msg="deployment home was %s" % dh)
    if rc!=0:
        raise UserError(errors[ERR_SLAVE_BOOTSTRAP],
                        msg_args={"host":resource["id"]},
                        developer_msg="deployment home was %s" % dh)
    if password_file:
        assert password_salt_file
        slave_pw_file = os.path.join(os.path.join(dh, "config"),
                                     os.path.basename(password_file))
        shutil.copy(password_file, slave_pw_file)
        slave_pw_salt_file = os.path.join(os.path.join(dh, "config"),
                                          os.path.basename(password_salt_file))
        shutil.copy(password_salt_file, slave_pw_salt_file)
    logger.debug("Slave %s bootstrap successful" % resource["id"])

import os.path
import shutil
import sys

import cmdline_script_utils
from engage.drivers.resource_metadata import parse_install_soln
from install_sequencer import get_install_target_mgr
from engage.utils.log_setup import setup_engage_logger
logger = setup_engage_logger(__name__)

from engage.utils.user_error import UserError, EngageErrInf, convert_exc_to_user_error

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

ERR_UPGRADE_ROLLBACK = 1
ERR_ROLLBACK_FAILED  = 2

define_error(ERR_UPGRADE_ROLLBACK,
             _("Upgrade of resource '%(id)s' failed, successfully uninstalled."))
define_error(ERR_ROLLBACK_FAILED,
             _("Upgrade of resource '%(orig_id)s' failed with exception '%(orig_exc)s', subsequent attempt to rollback then failed."))



def get_old_resources(backup_dir):
    res_file = os.path.join(backup_dir, "installed_resources.json")
    if not os.path.exists(res_file):
        raise Exception("Unable to find installed resources file for previous version at %s" % res_file)
    res_list = parse_install_soln(res_file)
    res_map = {}
    for res in res_list:
        res_map[res.id] = res
    return res_map

def _undo_bad_install(failed_resource_mgr, undo_list, deployment_home, orig_exc):
    m = failed_resource_mgr
    try:
        failed_upgrade_dir = os.path.join(deployment_home, "failed_upgrade")
        if os.path.exists(failed_upgrade_dir):
            logger.debug("Removing old upgrade directory %s" % failed_upgrade_dir)
            shutil.rmtree(failed_upgrade_dir)
        logger.debug("Force stop and uninstall of resource %s" % failed_resource_mgr.id)
        if m.is_service():
            m.force_stop()
        os.makedirs(failed_upgrade_dir)
        m.uninstall(failed_upgrade_dir, incomplete_install=True, compress=False)
        logger.debug("Uninstalling remaining resources")
        undo_list.reverse()
        for m in undo_list:
            if m.is_service():
                m.force_stop()
            m.uninstall(failed_upgrade_dir, incomplete_install=False, compress=False)
        logger.info("Uninstall of failed version successful")
    except:
        exc_info = sys.exc_info()
        logger.exception("Exception thrown during undo")
        raise convert_exc_to_user_error(exc_info, errors[ERR_ROLLBACK_FAILED],
                                        msg_args={'failed_id':m.id, 'orig_id':failed_resource_mgr.id,
                                                  'orig_exc':orig_exc})
                                        
class UpgradeRollbackInProgress(UserError):
    """We subclass from UserError so the caller can catch the exception in the
    case that an upgrade fails, and we then uninstall.
    """
    def __init__(self, error_info, msg_args=None, developer_msg=None,
                 context=None):
        UserError.__init__(self, error_info, msg_args, developer_msg, context)
        self.resource_id = None


def upgrade(backup_dir, file_layout, deployment_home, options, password_db=None, atomic_upgrade=True):
    old_resources = get_old_resources(backup_dir)
    mgrs_and_pkgs = cmdline_script_utils.get_mgrs_and_pkgs(file_layout, deployment_home, options,
                                                           file_layout.get_install_script_file(), password_db)
    undo_list = []
    for (m, p) in mgrs_and_pkgs:
        id = m.metadata.id
        try:
            if old_resources.has_key(id) and old_resources[id].key['name']==m.metadata.key['name'] and \
               m.metadata.key['version']>=old_resources[id].key['version']:
                logger.info("Calling upgrade for resource %s" % id)
                m.upgrade(p, old_resources[id], backup_dir)
            else:
                if not m.is_installed():
                    logger.info("Installing resource %s" % id)
                    m.install(p)
                else:
                    logger.info("Resource %s already installed" % id)
            m.metadata.set_installed()
            if m.is_service() and not m.is_running():
                m.start()
            undo_list.append(m)
        except:
            if not atomic_upgrade:
                raise
            exc_info = (exc_class, exc_val, exc_tb) = sys.exc_info()
            logger.exception("Upgrade of %s failed, will attempt undo" % m.id)
            _undo_bad_install(m, undo_list, deployment_home, "%s(%s)" % (exc_class.__name__, exc_val))
            user_error = convert_exc_to_user_error(exc_info, errors[ERR_UPGRADE_ROLLBACK],
                                                   msg_args={'id':m.id},
                                                   user_error_class=UpgradeRollbackInProgress)
            user_error.resource_id = m
            raise user_error
        
    install_target_mgr = get_install_target_mgr(mgrs_and_pkgs)
    managers = [mgr for (mgr, pkg) in mgrs_and_pkgs]
    install_target_mgr.write_resources_to_file(managers)
    if options.mgt_backends:
        import mgt_registration
        import install_context
        mgt_registration.register_with_mgt_backends(options.mgt_backends,
                                                    managers,
                                                    deployment_home,
                                                    sudo_password=install_context.get_sudo_password(),
                                                    upgrade=True)
    return 0
    

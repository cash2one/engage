
import sys
from optparse import OptionParser
import json
import os.path
import copy
from itertools import ifilter

# fix path if necessary (if running from source or running as test)
try:
    import engage.utils
except:
    dir_to_add_to_python_path = os.path.abspath(os.path.expanduser(os.path.join(os.path.dirname(__file__), "../..")))
    if not (dir_to_add_to_python_path in sys.path):
        sys.path.append(dir_to_add_to_python_path)


from engage.drivers.resource_metadata import parse_resource_from_json
from engage.utils.log_setup import add_log_option, parse_log_options, setup_engage_logger
import install_plan
from engage_file_layout import get_engine_layout_mgr
from cmdline_script_utils import add_standard_cmdline_options, process_standard_options, \
                                 get_mgrs_and_pkgs

class CommandError(Exception):
    pass


STATUS_RUNNING = "Running"
STATUS_STOPPED = "Stopped"
STATUS_NOT_INSTALLED = "Not installed"
STATUS_INSTALLED = "Installed" # used only when not a service
STATUS_UNAVAILABLE = "Unavailable"

def get_service_status(rm, resource_map, status_cache_map):
    """Get the status of the service associated with
    the resource manager. If the containing service is
    not up, the status request could fail. To address this,
    we check the containing service first and, if it is not up,
    report the status as the inner service as unavalable. The
    status_cache_map parameter is a map from resource ids to statuses.
    It is updated by get_service_status() with any status values it
    obtains (including recursive calls).
    """
    if rm.metadata.inside!=None:
        inside_id = rm.metadata.inside.id
        if not status_cache_map.has_key(inside_id):
            # obtain the status of the containing resource
            get_service_status(resource_map[inside_id], resource_map,
                               status_cache_map)
        if not (status_cache_map[inside_id]==STATUS_RUNNING or
                status_cache_map[inside_id]==STATUS_INSTALLED):
            status_cache_map[rm.metadata.id] = STATUS_UNAVAILABLE
            return STATUS_UNAVAILABLE
    
    if rm.is_installed()==False:
        status_cache_map[rm.metadata.id] = STATUS_NOT_INSTALLED
    elif not rm.is_service():
        status_cache_map[rm.metadata.id] = STATUS_INSTALLED
    elif rm.is_running()==False:
        status_cache_map[rm.metadata.id] = STATUS_STOPPED
    else:
        status_cache_map[rm.metadata.id] = STATUS_RUNNING
    return status_cache_map[rm.metadata.id]


def dummy(command, command_args, mgr_pkg_list, resource_map, logger):
    print "running dummy version of command %s" % command


def _format_key(key):
    return "%s %s" % (key['name'], key['version'])

def list_resources(command, command_args, mgr_pkg_list, resource_map, logger, dry_run):
    for (mgr, pkg) in mgr_pkg_list:
        if mgr.is_service():
            print "%s (%s) [service]" % (mgr.id, _format_key(mgr.metadata.key))
        else:
            print "%s (%s)" % (mgr.id, _format_key(mgr.metadata.key))
    return 0


def status(command, command_args, mgr_pkg_list, resource_map, logger, dry_run):
    status_cache = {}
    def print_status(rm):
        if not dry_run:
            status = get_service_status(rm, resource_map, status_cache)
            print "%s (%s) Status: %s" % \
                  (rm.id, rm.package_name, status)
        else:
            print "%s (%s) [dry_run]" % (rm.id, rm.package_name)

    if len(command_args)==0 or command_args==["all"]:
        for (mgr, pkg) in mgr_pkg_list:
            if mgr.is_service():
                print_status(mgr)
    else:
        for resource_id in command_args:
            rm = resource_map[resource_id]
            print_status(rm)
    return 0

def _filter_mgr_pkg_list(mgr_pkg_list, filter_fn, target_res_id_list):
    """The filter function takes two resource lists: the set of all resources
    (obtained from mgr_pkg_list) and the set of target resources. It should
    return a set of resource ids. This set is unioned with the target set and
    used to filter the manager-package list.
    """
    resource_list = [mgr.metadata for (mgr, pkg) in mgr_pkg_list]
    targ_set = filter_fn(resource_list, target_res_id_list)
    targ_set = targ_set.union(set(target_res_id_list))
    return [i for i in ifilter(lambda (mgr, pkg): mgr.metadata.id in targ_set,
                               mgr_pkg_list)]


def _stop_mgr(mgr, dry_run, force):
    if not mgr.is_service(): return True
    if not dry_run:
        if mgr.is_running():
            if force:
                print "Attempting to force stop %s" % mgr.id
                result = mgr.force_stop()
                if result:
                    print "%s stopped successfully." % mgr.id
                else:
                    print "Unable to force stop %s" % mgr.id
                    return False
            else:
                mgr.stop()
                print "%s stopped." % mgr.id
        else:
            print "%s already stopped." % mgr.id
            
    else:
        print "%s: stop if not already stopped [dry-run]" % mgr.id
    return True


def stop(command, command_args, mgr_pkg_list, resource_map, logger, dry_run, force=False):
    had_errors = False
    if len(command_args)==0:
        target_resource_ids = ["all"]
    else:
        target_resource_ids = command_args[0:]

    reversed_mgr_pkg_list = copy.copy(mgr_pkg_list)
    reversed_mgr_pkg_list.reverse()
    if target_resource_ids == ["all"]:
        for (mgr, pkg) in reversed_mgr_pkg_list:
            ok = _stop_mgr(mgr, dry_run, force)
            if not ok: had_errors = True
    else:
        filtered_list = _filter_mgr_pkg_list(reversed_mgr_pkg_list,
                                             install_plan.get_transitive_resources_depending_on_resource,
                                             target_resource_ids)
        for (mgr, pkg) in filtered_list:
            if not mgr.is_service() and mgr.id in target_resource_ids:
                print "%s is not a service" % mgr.id
                continue
            ok = _stop_mgr(mgr, dry_run, force)
            if not ok: had_errors = True
    return 1 if had_errors else 0


def _start_mgr(mgr, dry_run):
    if not mgr.is_service(): return
    if not dry_run:
        if not mgr.is_running():
            mgr.start()
            print "Started %s." % mgr.id
        else:
            print "%s already started." % mgr.id
    else:
        print "%s: check if running and start if not already running [dry-run]" % mgr.id
    
def start(command, command_args, mgr_pkg_list, resource_map, logger, dry_run):
    if len(command_args)==0:
        target_resource_ids = ["all"]
    else:
        target_resource_ids = command_args[0:]

    if target_resource_ids == ["all"]:
        for (mgr, pkg) in mgr_pkg_list:
            _start_mgr(mgr, dry_run)
    else:
        filtered_list = _filter_mgr_pkg_list(mgr_pkg_list,
                                             install_plan.get_transitive_dependencies_for_resource,
                                             target_resource_ids)
        for (mgr, pkg) in filtered_list:
            if not mgr.is_service() and mgr.id in target_resource_ids:
                print "%s is not a service." % mgr.id
                continue
            _start_mgr(mgr, dry_run)
    return 0


def restart(command, command_args, mgr_pkg_list, resource_map, logger, dry_run, force=False):
    if len(command_args)>0:
        raise Exception("Restart does not take any extra command arguments")
    reversed_mgr_pkg_list = copy.copy(mgr_pkg_list)
    reversed_mgr_pkg_list.reverse()
    for (mgr, pkg) in reversed_mgr_pkg_list:
        _stop_mgr(mgr, dry_run, force)

    for (mgr, pkg) in mgr_pkg_list:
        _start_mgr(mgr, dry_run)
    return 0


commands = {
 "start":start,
 "stop":stop,
 "status":status,
 "list":list_resources,
 "restart":restart
}

valid_commands = commands.keys()

usage_msg = """usage: %prog [options] command command_args
Valid commands:
  start  <resource id>
  stop   <resource id>
  status <resource id>
  list"""

def main():
    parser = OptionParser(usage=usage_msg)
    add_standard_cmdline_options(parser, running_deployment=False,
                                 default_log_level="WARNING")
    parser.add_option("-r", "--resource-file", dest="resource_file", default=None,
                      help="Name of resource file (defaults to <deployment_home>/config/installed_resources.json)")
    parser.add_option("--force", dest='force', default=False,
                      action="store_true",
                      help="If stop or restart, try to force everything to stop")
    parser.add_option("--dry-run", dest="dry_run", default=False,
                      action="store_true",
                      help="If specified, just print what would be done")
    (options, args) = parser.parse_args()

    if len(args)==0:
        parser.print_help()
        sys.exit(0)

    if len(args)<1:
        parser.error("Missing command name. Must be one of %s" % valid_commands)

    (file_layout, deployment_home) = process_standard_options(options, parser, allow_overrides_of_dh=True,
                                                              rotate_logfiles=False)

    if options.resource_file:
        installed_resources_file = os.path.abspath(os.path.expanduser(options.resource_file))
    else:
        installed_resources_file = file_layout.get_installed_resources_file(deployment_home)
    if not os.path.exists(installed_resources_file):
        sys.stderr.write("Error: Installed resources file '%s does not exist\n" %
                         installed_resources_file)
        sys.exit(1)

    logger = setup_engage_logger(__name__)
    
    mgr_pkg_list = get_mgrs_and_pkgs(file_layout, deployment_home, options, installed_resources_file)
    resource_map = {}
    for (mgr, pkg) in mgr_pkg_list:
        resource_map[mgr.id] = mgr

    command = args[0]
    if command not in commands.keys():
        sys.stderr.write("Error: invalid command %s\n" % command)
        parser.print_help()
        sys.exit(1)

    if options.force and command not in ['stop', 'restart']:
        sys.stderr.write("Error: --force option not valid for command %s\n" % command)
        parser.print_help()
        sys.exit(1)

    command_args = args[1:]
    cmd_fn = commands[command]
    try:
        if command in ['stop', 'restart']:
            rc = cmd_fn(command, command_args, mgr_pkg_list, resource_map, logger,
                   options.dry_run, force=options.force)
        else:
            rc = cmd_fn(command, command_args, mgr_pkg_list, resource_map, logger,
                        options.dry_run)
    except CommandError, msg:
        sys.stderr.write("Error: %s\n" % msg)
        sys.exit(1)

    sys.exit(rc)
    
if __name__ == "__main__": main()

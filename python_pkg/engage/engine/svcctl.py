
import sys
from optparse import OptionParser
import json
import os.path
import copy

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



def get_service_status(rm):
    if rm.is_installed()==False:
        return "Not installed"
    elif rm.is_running()==False:
        return "Stopped"
    else:
        return "Running"


def dummy(command, command_args, mgr_pkg_list, resource_map, logger):
    print "running dummy version of command %s" % command


def _format_key(key):
    return "%s %s" % (key['name'], key['version'])

def list(command, command_args, mgr_pkg_list, resource_map, logger):
    for (mgr, pkg) in mgr_pkg_list:
        if mgr.is_service():
            print "%s (%s) [service]" % (mgr.id, _format_key(mgr.metadata.key))
        else:
            print "%s (%s)" % (mgr.id, _format_key(mgr.metadata.key))


def status(command, command_args, mgr_pkg_list, resource_map, logger):
    def print_status(rm):
        print "%s (%s) Status: %s" % \
            (rm.id, rm.package_name, get_service_status(rm))

    if len(command_args)==0 or command_args==["all"]:
        for (mgr, pkg) in mgr_pkg_list:
            if mgr.is_service():
                print_status(mgr)
    else:
        for resource_id in command_args:
            rm = resource_map[resource_id]
            print_status(rm)


def stop(command, command_args, mgr_pkg_list, resource_map, logger):
    if len(command_args)>1:
        raise CommandError, \
            "unexpected arguments to stop commmand"
    elif len(command_args)==0:
        target_resource_ids = ["all"]
    else:
        target_resource_ids = command_args[0:]
        
    if target_resource_ids == ["all"]:
        lst_cpy = copy.copy(mgr_pkg_list)
        lst_cpy.reverse()
        plan = [mgr for (mgr, pkg) in lst_cpy]
        for rm in plan:
            if not rm.is_service(): continue
            if rm.is_running():
                rm.stop()
                print "%s stopped." % rm.id
            else:
                print "%s already stopped." % rm.id
    else:
        for id in target_resource_ids:
            rm = resource_map[id]
            if not rm.is_service():
                print "%s is not a service." % rm.id
            elif rm.is_running():
                rm.stop()
                print "Stopped %s." % rm.id
            else:
                print "%s already stopped." % rm.id


def start(command, command_args, mgr_pkg_list, resource_map, logger):
    if len(command_args)>1:
        raise CommandError, \
            "unexpected arguments to start command"
    elif len(command_args)==0:
        target_resource_ids = ["all"]
    else:
        target_resource_ids = command_args[0:]

    if target_resource_ids == ["all"]:
        plan = [mgr for (mgr, pkg) in mgr_pkg_list]
        for rm in plan:
            if not rm.is_service(): continue
            if not rm.is_running():
                rm.start()
                print "%s started." % rm.id
            else:
                print "%s already running." % rm.id
    else:
        for id in target_resource_ids:
            rm = resource_map[id]
            if not rm.is_service():
                print "%s is not a service." % rm.id
            elif not rm.is_running():
                rm.start()
                print "Started %s." % rm.id
            else:
                print "%s already started." % rm.id
                

commands = {
 "start":start,
 "stop":stop,
 "status":status,
 "list":list
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
    add_standard_cmdline_options(parser, default_log_level="WARNING")
    parser.add_option("-r", "--resource-file", dest="resource_file", default=None,
                      help="Name of resource file (defaults to <deployment_home>/config/installed_resources.json)")
    (options, args) = parser.parse_args()

    if len(args)==0:
        parser.print_help()
        sys.exit(0)

    if len(args)<1:
        parser.error("Missing command name. Must be one of %s" % valid_commands)

    (file_layout, deployment_home) = process_standard_options(options, parser, allow_overrides_of_dh=True)

    if options.resource_file:
        installed_resources_file = os.path.abspath(os.path.expanduser(options.resource_file))
    else:
        installed_resources_file = file_layout.get_installed_resources_file(deployment_home)
    if not os.path.exists(installed_resources_file):
        sys.stderr.write("Error: Installed resources file '%s does not exist\n" %
                         installed_resources_file)
        sys.exit(1)

    logger = setup_engage_logger(__name__)
    
    # this is a hack to avoid specifying the -n option if there is no password repository
    pw_dir = file_layout.get_password_file_directory()
    from engage.utils.pw_repository import REPOSITORY_FILE_NAME
    pw_file = os.path.join(pw_dir, REPOSITORY_FILE_NAME)
    if not os.path.exists(pw_file) and not options.no_password_file:
        logger.info("-n option not specified, but password file does exist. Assuming that no password file is needed.\n")
        options.no_password_file = True
        

    mgr_pkg_list = get_mgrs_and_pkgs(file_layout, deployment_home, options, installed_resources_file)
    resource_map = {}
    for (mgr, pkg) in mgr_pkg_list:
        resource_map[mgr.id] = mgr

    command = args[0]
    if command not in commands.keys():
        sys.stderr.write("Error: invalid command %s\n" % command)
        parser.print_help()
        sys.exit(1)


    command_args = args[1:]
    cmd_fn = commands[command]
    try:
        cmd_fn(command, command_args, mgr_pkg_list, resource_map, logger)
    except CommandError, msg:
        sys.stderr.write("Error: %s\n" % msg)
        sys.exit(1)

    sys.exit(0)
    
if __name__ == "__main__": main()

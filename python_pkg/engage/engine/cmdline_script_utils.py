"""Common functionality for the various command line scripts that need to instantiate resources.
"""
import json
import os.path

import engage.utils.log_setup as log_setup
from library import parse_library_files
import install_plan
from engage.engine.engage_file_layout import get_engine_layout_mgr
from engage.drivers.resource_metadata import parse_resource_from_json

def add_standard_cmdline_options(parser, uses_pw_file=True,
                                 default_log_level="INFO"):
    if uses_pw_file:
        parser.add_option("-n", "--no-password-file", action="store_true", dest="no_password_file",
                          default=False, help="If specified, there is no password file to parse")
        parser.add_option("--force-password-file", action="store_true", dest="force_password_file",
                          default=False, help="If specified, always use password file")
        parser.add_option("-s", "--subproc", action="store_true", dest="subproc",
                          default=False, help="Run in subprocess mode, getting master password from standard input")
    log_setup.add_log_option(parser, default=default_log_level)
    parser.add_option("--deployment-home", "-d", dest="deployment_home",
                      default=None,
                      help="Location of deployed application - can figure this out automatically unless installing from source")
    

def get_deployment_home(options, parser, file_layout, allow_overrides=False):
    if options.deployment_home:
        if file_layout.get_deployment_home() and file_layout.get_deployment_home()!=options.deployment_home and (not allow_overrides):
            parser.error("Cannot specify deployment home option when running from a deployment home")
        dh = options.deployment_home
    else:
        dh = file_layout.get_deployment_home()
        if not dh:
            parser.error("When running from source tree, need to specify deployment home")
    if not os.path.isdir(dh):
        parser.error("Deployment home %s does not exist" % dh)
    return dh

def process_standard_options(options, parser, precreated_file_layout=None, installer_name=None, allow_overrides_of_dh=False):
    if hasattr(options, "no_password_file") and options.no_password_file and \
       hasattr(options, "force_password_file") and options.force_password_file:
        parser.error("Cannot specify both --no-password-file and --force-password-file")
    if precreated_file_layout:
        file_layout = precreated_file_layout
    else:
        file_layout = get_engine_layout_mgr(installer_name)
    dh = get_deployment_home(options, parser, file_layout, allow_overrides=allow_overrides_of_dh)
    log_setup.parse_log_options(options, file_layout.get_log_directory())
    return (file_layout, dh)

    
def get_mgrs_and_pkgs(file_layout, deployment_home, options, resource_file=None, pw_database=None):
    """Perform common initialization operations, returning
    a list of (mgr, pkg) pairs sorted in dependency order.
    """
    library = parse_library_files(file_layout)
    if options.no_password_file:
        assert pw_database==None
        import engage.utils.pw_repository as pw_repository
        pw_database = pw_repository.PasswordRepository("")
    import install_context
    install_context.setup_context(file_layout.get_password_file_directory(), options.subproc, library, pw_database)

    if not resource_file:
        resource_file = file_layout.get_installed_resources_file(deployment_home)

    def get_manager_and_pkg(resource):
        entry = library.get_entry(resource)
        assert entry, "Unable to find entry for resource %s in library file %s" % (resource.id, file_layout.get_software_library_file())
        resource_manager_class = entry.get_manager_class()
        mgr = resource_manager_class(resource)
        import install_context
        mgr.install_context = install_context
        return (mgr, entry.get_package())
        
    with open(resource_file, "rb") as f:
        resource_list_json = json.load(f)
    rlist =  [parse_resource_from_json(resource_json) for
              resource_json in resource_list_json]
    return [get_manager_and_pkg(r) for r in install_plan.create_install_plan(rlist)]
    

"""Common functionality for the various command line scripts that need to instantiate resources.
"""
import json
import os.path

import fixup_python_path
import engage.utils.log_setup as log_setup
from engage.engine.engage_file_layout import get_engine_layout_mgr
from engage.drivers.resource_metadata import parse_resource_from_json


def add_standard_cmdline_options(parser, uses_pw_file=True,
                                 running_deployment=True,
                                 default_log_level="INFO"):
    """These are the command line options used by 
    """
    log_setup.add_log_option(parser, default=default_log_level)
    parser.add_option("--deployment-home", "-d", dest="deployment_home",
                      default=None,
                      help="Location of deployed application - can figure this out automatically unless installing from source")
    if uses_pw_file:
        if running_deployment:
            parser.add_option("-p", "--master-password-file", default=None,
                              help="File containing master password (if not specified, will prompt from console if needed). If --suppress-master-password-file is not set, and the master password file is not already at <deployment_home>/config/master.pw, a master password file will be generated at that location. Permissions will be set to 0600.")
            parser.add_option("--generate-random-passwords", "-g",
                              default=False, action="store_true",
                              help="If passwords are needed for individual components to be installed, generate random passwords rather than prompting for them")
            parser.add_option("--suppress-master-password-file", default=False,
                              action="store_true",
                              help="If specified, do not create a file containing the master password at <deployment_home>/config/master.pw.")
        else:
            parser.add_option("-p", "--master-password-file", default=None,
                              help="File containing master password. If not specified, will look for file at <deployment_home>/config/master.pw. If that file is not present, prompt from console if needed)")
        ## parser.add_option("--generate-password-file", "-g",
        ##                   dest="generate_password_file",
        ##                   default=False, action="store_true",
        ##                   help="If specified, generate a password file and exit")
        parser.add_option("-s", "--subproc", action="store_true", dest="subproc",
                          default=False, help="Run in subprocess mode, getting master password from standard input")
    if running_deployment:
        parser.add_option("--mgt-backends", dest="mgt_backends", default=None,
                          help="If specified, a list of management backend plugin(s)")
        parser.add_option("--force-stop-on-error", dest="force_stop_on_error",
                          default=False, action="store_true",
                          help="If specified, force stop any running daemons if the install fails. Default is to leave things running (helpful for debugging).")
        parser.add_option("-n", "--dry-run", action="store_true",
                          default=False,
                          help="If specified, just do a dry run and exit")


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

def process_standard_options(options, parser, precreated_file_layout=None, installer_name=None, allow_overrides_of_dh=False, rotate_logfiles=True):
    if precreated_file_layout:
        file_layout = precreated_file_layout
    else:
        file_layout = get_engine_layout_mgr(installer_name)
    dh = get_deployment_home(options, parser, file_layout, allow_overrides=allow_overrides_of_dh)
    log_setup.parse_log_options(options, file_layout.get_log_directory(),
                                rotate_logfiles=rotate_logfiles)
    if hasattr(options, "master_password_file") and \
       options.master_password_file and \
       (not os.path.exists(options.master_password_file)):
        parser.error("Master password file %s does not exist" %
                     options.master_password_file)
    return (file_layout, dh)


def extract_standard_options(options):
    """We're going to call another component that accepts the standard options
    and need to extract them from an options map back to an array of
    arguments.
    """
    args = []
    if options.deployment_home:
        args.extend(["--deployment-home", options.deployment_home])
    if hasattr(options, "master_password_file") and options.master_password_file:
        args.extend(["--master-password-file", options.master_password_file])
    if options.subproc:
        args.append("--subproc")
    if options.mgt_backends:
        args.extend(["--mgt-backends", options.mgt_backends])
    if options.force_stop_on_error:
        args.append("--force-stop-on-error")
    if hasattr(options, "generate_random_passwords") and \
       options.generate_random_passwords:
        args.append("--generate-random-passwords")
    if hasattr(options, "suppress_master_password_file") and \
       options.suppress_master_password_file:
        args.append("--suppress-master-password-file")
    if options.dry_run:
        args.append("--dry-run")
    ## if options.generate_password_file:
    ##     args.append("--generate-password-file")
    args.extend(log_setup.extract_log_options_from_options_obj(options))
    return args
    
def get_mgrs_and_pkgs(file_layout, deployment_home, options,
                      resource_file=None):
    """Perform common initialization operations, returning
    a list of (mgr, pkg) pairs sorted in dependency order.
    """
    import library
    import install_plan
    l = library.parse_library_files(file_layout)
    import engage.engine.password
    pw_database = engage.engine.password.get_password_db(file_layout, options)
    import install_context
    install_context.setup_context(file_layout, options.subproc, l, pw_database)

    if not resource_file:
        resource_file = file_layout.get_installed_resources_file(deployment_home)

    def get_manager_and_pkg(resource):
        if resource.package!=None:
            # new style packags are on the resource
            package = resource.package
            resource_manager_class = resource.get_resource_manager_class()
        else:
            entry = l.get_entry(resource)
            assert entry, "Unable to find entry for resource %s in library file %s" % (resource.id, file_layout.get_software_library_file())
            resource_manager_class = entry.get_manager_class()
            package = entry.get_package()
        mgr = resource_manager_class(resource)
        import install_context
        mgr.install_context = install_context
        return (mgr, package)
        
    with open(resource_file, "rb") as f:
        resource_list_json = json.load(f)
    rlist =  [parse_resource_from_json(resource_json) for
              resource_json in resource_list_json]
    return [get_manager_and_pkg(r) for r in install_plan.create_install_plan(rlist)]
    

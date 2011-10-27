
import sys
import os
import os.path
from optparse import OptionParser
import json
from subprocess import Popen
import getpass
import copy

# fix path if necessary (if running from source or running as test)
import fixup_python_path

from engage.utils.user_error import UserError, EngageErrInf, convert_exc_to_user_error, UserErrorParseExc, parse_user_error, AREA_CONFIG

from engage.engine.installer_config import parse_installer_config, \
     ValidationResults, LocalFileType, ConfigProperty, PasswordType
import engage.utils.log_setup as log_setup
import engage.engine.install_engine as install_engine
from engage.engine.engage_file_layout import get_engine_layout_mgr
from engage.utils.file import subst_utf8_template_file
import cmdline_script_utils
import upgrade_engine
from preprocess_resources import create_install_spec
from host_resource_utils import get_target_machine_resource, setup_slave_host
from config_engine import preprocess_and_run_config_engine, get_config_error_file


import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info


ERR_UNEXPECTED_EXC  = 1
ERR_NEED_PW_FILE    = 3
ERR_MISSING_PW_KEY  = 4

define_error(ERR_UNEXPECTED_EXC,
             _("Aborting install due to unexpected error."))
define_error(ERR_NEED_PW_FILE,
             _("No password file provided, but password file needed for property %(name)s (password key %(key)s)"))
define_error(ERR_MISSING_PW_KEY,
             _("Password file does not include key %(key)s, which is needed for input property %(name)s"))

############################################################
# constants
############################################################

# Name of property in config choices used to indicate app archive file
APPLICATION_ARCHIVE_PROP = "Application Archive File"
# Name of property in config choices to keep track of management tools in the case of upgrades
MGT_BACKENDS_PROP = "_management backends"


class InputValidator(object):
    def __init__(self):
        self.error_message = None

    def validate(data, choice_history):
        pass


class LovValidator(InputValidator):
    """Validate that the input is one of a specified
    list of values.
    """
    def __init__(self, values):
        InputValidator.__init__(self)
        self.values = values

    def validate(self, data, choice_history):
        if data in self.values:
            return ValidationResults(True)
        else:
            return ValidationResults(False, "Please specify one of %s" % self.values)


class DeploymentHomeValidator(InputValidator):
    """Validate that deployment home does not already contain an app
    """
    def __init__(self):
        InputValidator.__init__(self)

    def validate(self, data, choice_history):
        cfg_dir = os.path.join(data, "config")
        installed_resources_file = os.path.join(cfg_dir, "installed_resources.json")
        if os.path.exists(installed_resources_file):
            return ValidationResults(False,
                                     "File %s already exists, are you installing on top of an old install?\nPlease remove before installing." % \
                                     installed_resources_file)
        else:
            return ValidationResults(True)


def get_password_input(prompt, read_from_stdin=False):
    if read_from_stdin:
        return sys.stdin.read().rstrip()
    else:
        while True:
            input1 = getpass.getpass(prompt)
            input2 = getpass.getpass("Retype password:")
            if input1 == input2:
                return input1
            else:
                print "Passwords do not match!"


class ConfigChoices(object):
    """Class to manage configuration choices. We may read them from
    a file or get them interactively from the user.
    We record all the choices, in case we want to save them to a history
    file for future replay.
    """
    def __init__(self, filename=None, use_defaults=False):
        self.filename = filename
        if self.filename:
            with open(filename, "rb") as f:
                self.choices_from_file = json.load(f)
        else:
            self.choices_from_file = None
        # password repository will be set later if we are running from an input
        # file.
        self.password_repository = None
        self.choice_history = {}
        self.app_archive_value = None # used if we override on command line
        self.use_defaults = use_defaults # if true and getting input from user, pick default without asking user

    def has_input_file(self):
        return self.filename != None

    def _get_input_from_file(self, name):
        assert self.choices_from_file != None
        if not self.choices_from_file.has_key(name):
            raise Exception("Configuration choices file %sis missing key for input '%s'" % (self.filename, name))
        return self.choices_from_file[name]

    def get_user_input(self, name, default=None, validator=None, optional=False, description=None):
        assert not (default!=None and optional), \
               "Bad get input choice request: %s - cannot have an input which has a default value and is optional" % name
        if self.has_input_file():
            data = self._get_input_from_file(name)
            if data=='' and default!=None:
                data = default
            if validator and (not (data=='' and optional)):
                result = validator.validate(data, self.choice_history)
                if not result.successful():
                    raise Exception("Validation for input %s, value '%s' from config choices file %s failed: %s" %
                                    (name, data, self.filename, result.get_error_message()))
            print "Configuration choice '%s': using value '%s' from file" % (name, data)
            self.choice_history[name] = data
            return data
        else: # we are getting input from user interactively
            if name==APPLICATION_ARCHIVE_PROP and self.app_archive_value:
                # first, a special case if we've overridden the application archive
                # property on the command line
                result = validator.validate(self.app_archive_value, self.choice_history)
                if not result.successful():
                    raise Exception("Validation for input %s, value '%s' failed: %s" %
                                    (name, data, result.get_error_message()))
                else:
                    self.choice_history[name] = self.app_archive_value
                    return self.app_archive_value
            elif self.use_defaults and default:
                # If interactive, we always use defaults, and there is a default,
                # we don't need to bother the user.
                self.choice_history[name] = default
                print "%s: using default value '%s'" % (name, default)
                return default
            elif self.use_defaults and optional:
                print "%s: Using value chosen by configuration engine" % name
                self.choice_history[name] = ''
                return ''
            while True:
                if description:
                    long_name = "%s (%s)" % (name, description)
                else:
                    long_name = name
                if default:
                    prompt = "%s [%s] ? " % (long_name, default)
                elif optional:
                    prompt = "%s [If not specified, will use value chosen by configuration engine] ? " % long_name
                else:
                    prompt = "%s ? " % long_name
                data = raw_input(prompt)
                if data != "":
                    if validator:
                        result = validator.validate(data, self.choice_history)
                        if result.successful():
                            self.choice_history[name] = data
                            return data
                        else:
                            print result.get_error_message()
                    else:
                        self.choice_history[name] = data
                        return data
                elif default != None:
                    self.choice_history[name] = default
                    return default
                elif optional:
                    self.choice_history[name] = ''
                    return ''
                else:
                    print "Please provide a value for %s" % name

    def get_password(self, name, password_key, description=None):
        if self.has_input_file():
            if not self.password_repository:
                raise UserError(errors[ERR_NEED_PW_FILE],
                                msg_args={"name":name, "key":password_key})
            if not self.password_repository.has_key(password_key):
                raise UserError(errors[ERR_MISSING_PW_KEY],
                                msg_args={"name":name, "key":password_key})
            self.choice_history[name] = password_key
            return self.password_repository.get_value(password_key)
        else:
            if description:
                long_name = name + " (" + description + ")"
            else:
                long_name = name
            value = get_password_input(long_name + "? ", False)
            self.choice_history[name] = password_key
            return value
                           
    def select_numbered_option(self, name, option_list, default=None,
                               description=None):
        if description:
            print "Please select a %s (%s):" % (name, description)
        else:
            print "Please select a %s:" % name
        option_number = 1
        option_values = []
        for option in option_list:
            print "%d  %s" % (option_number, option)
            option_values.append("%d" % option_number)
            option_number = option_number + 1
        if default != None:
            default_as_string = "%d" % default
        else:
            default_as_string = None
        data = self.get_user_input(name, default=default_as_string,
                                   validator=LovValidator(option_values),
                                   description=description)
        return int(data) - 1

    def save_history_file(self, save_filename):
        with open(save_filename, "wb") as f:
            json.dump(self.choice_history, f)

    def get_installer_name(self):
        assert self.choices_from_file.has_key("Installer"), \
               "config choices does not contain installer name key 'Installer'"
        return self.choices_from_file["Installer"]

    def set_installer_name(self, installer_name):
        self.choice_history["Installer"] = installer_name



def select_configuration(installer_file_layout, config_choices):
    install_spec_options = installer_file_layout.get_installer_config().install_spec_options
    if len(install_spec_options)==1:
        # special case if there is only one option
        return 0
    else:
        return config_choices.select_numbered_option("configuration option",
                                                     [c["choice_name"] for c in install_spec_options])



def set_install_spec_properties(installer_file_layout, install_spec_option_no,
                                config_choices, target_machine, logger):
    """This function gets the config properties associated with the install spec choice
    and asks the user to provide values for those properties. We then write out a new
    install spec file with these properties set.

    Returns a list of password (key, value) pairs (may be empty if no passwords read).
    """
    def find_resource(resource_id, install_spec):
        for r in install_spec: # install spec is a list of resources
            if r[u"id"] == resource_id:
                return r
        return None
    def add_config_prop(resource, prop_name, prop_value):
        if not resource.has_key("config_port"):
            resource['config_port'] = {}
        resource['config_port'][prop_name] = prop_value
        
    gc = installer_file_layout.get_installer_config()
    config_props = gc.get_config_properties_for_install_spec(install_spec_option_no)
    if len(config_props)==0 and (not gc.has_application_archive()):
        return
    install_spec_file = installer_file_layout.get_install_spec_file(install_spec_option_no)
    with open(install_spec_file, "rb") as f:
        install_spec = json.load(f)

    # if there is an application archive, we ask for it now and validate.
    # The app may give us additional resources to add to the spec.
    if gc.has_application_archive():
        archive_path = config_choices.get_user_input(APPLICATION_ARCHIVE_PROP,
                                                     default=None, validator=LocalFileType(),
                                                     optional=False)
        archive_path = os.path.abspath(os.path.expanduser(archive_path))
        av = gc.get_application_archive_validator(archive_path)
        if config_choices.has_input_file() and config_choices.choices_from_file.has_key("_application_components"):
            prev_app_comps = config_choices.choices_from_file["_application_components"]
        else:
            prev_app_comps = None
        result = av.validate(prev_app_comps=prev_app_comps)
        if not result.successful():
            raise Exception("Validation error in application achive '%s': %s" %
                            (archive_path, result.get_error_message()))
        included_resources = set([inst["id"] for inst in install_spec])
        dependencies = av.get_app_dependency_resources(target_machine["id"],
                                                       target_machine["key"])
        for dep in dependencies:
            if not (dep["id"] in included_resources):
                install_spec.append(dep)
                included_resources.add(dep["id"])
        # set the associated property in the install spec
        r = find_resource(av.resource, install_spec)
        assert r, "Unable to find resource %s in install spec" % av.resource
        if not r.has_key(u"config_port"):
            r[u"config_port"] = {}
        r[u"config_port"][av.property_name] = LocalFileType().convert_to_json_type(archive_path, config_choices.choice_history)
        # if there are any additional config properties, add them
        config_props.extend([ConfigProperty(p['resource'], p['name'], p['type'], p['description'],
                                            p['default'], p['optional'])
                             for p in av.get_additional_config_props(target_machine["id"],
                                                                     target_machine["key"])])
        logger.debug("additional application components = %s" % av.get_app_dependency_names())
        
        config_choices.choice_history[APPLICATION_ARCHIVE_PROP] = archive_path
        config_choices.choice_history["_application_components"] = av.get_app_dependency_names()

    password_list = []
    # now go through all the properties that we need to potentially override in the install spec
    for cp in config_props:
        if isinstance(cp.type, PasswordType):
            # for password values we need special handling
            pw_key = cp.resource + "/" + cp.name
            v = config_choices.get_password(cp.name, pw_key, description=cp.description)
            password_list.append((pw_key, v),)
            r = find_resource(cp.resource, install_spec)
            assert r, "Unable to find resource %s in install spec" % cp.resource
            add_config_prop(r, cp.name, pw_key)
        else:
            default = cp.type.get_default(cp.default, config_choices.choice_history)
            v = config_choices.get_user_input(cp.name, default=default, validator=cp.type,
                                              optional=cp.optional, description=cp.description)
            # some properties are optional: if the user does not specify a value, then we don't set the property
            # in the install spec. This has the effect of having the config engine find a value for the property
            # instead.
            if cp.optional and v=='':
                continue # skipping the setting of this property
            # set the property in the install spec
            r = find_resource(cp.resource, install_spec)
            assert r, "Unable to find resource %s in install spec" % cp.resource
            add_config_prop(r, cp.name, cp.type.convert_to_json_type(v, config_choices.choice_history))

    # now save the new file
    with open(install_spec_file, "wb") as f:
        json.dump(install_spec, f, indent=2)

    return password_list


def system(command, cwd=None, shell=True):
    """Run a command as a subprocess. If the command fails, we thow an
    exception. The default is to use the shell. The command arg can be
    either a string or a list.
    """
    print command.__repr__()
    p = Popen(command, cwd=cwd, shell=shell)
    (pid, exit_status) = os.waitpid(p.pid, 0)
    rc = exit_status >> 8 # the low byte is the signal ending the proc
    if rc != 0:
        raise Exception("Command execution failed: '%s'" % command)


class InstallRequest(object):
    """This class is for processing the command line arguments of the installer
    and storing the resulting state as members.
    """
    def __init__(self):
        self.options = None
        self.installer_name = None
        self.installer_file_layout = None
        self.deployment_home = None
        self.config_choices = None
        self.upgrade_from = None
        self.error_file = None
        self.config_error_file = None
        
    def process_args(self, argv, installer_file_layout=None):
        usage = "usage: %prog [options] installer_name"
        parser = OptionParser(usage=usage)
        cmdline_script_utils.add_standard_cmdline_options(parser)
        parser.add_option("--config-choices-file", dest="config_choices_file",
                          default=None, help="If specified, get configuration choices from this json file, rather than interactively from the user")
        parser.add_option("--config-choices-history-file", dest="history_file",
                          default=None, help="If specified, save config choices to this file")
        parser.add_option("--upgrade", "-u", dest="upgrade_from", action="store",
                          default=None,
                          help="If specified, we are doing an upgrade from the app backed up to the specified source directory")
        parser.add_option("--application-archive", "-a", dest="application_archive", action="store",
                          default=None,
                          help="If specified, override the application_archive property in config choices file with this value")
        parser.add_option("--mgt-backends", dest="mgt_backends", default=None,
                          help="If specified, a list of management backend plugin(s)")
        parser.add_option("--dry-run", dest="dry_run",
                          default=False, action="store_true",
                          help="If specified, do a dry run of the install.")
        parser.add_option("--no-rollback-on-failed-upgrades", dest="no_rollback_on_failed_upgrades",
                          default=False, action="store_true",
                          help="If specified, do not roll back a failed upgrade (helpful for debugging).")
        parser.add_option("--force-stop-on-error", dest="force_stop_on_error",
                          default=False, action="store_true",
                          help="If specified, force stop any running daemons if the install fails. Default is to leave things running (helpful for debugging).")
        parser.add_option("-y", "--use-defaults", dest="use_defaults",
                          default=False, action="store_true",
                          help="If specified, always pick default for input options")


        (self.options, args) = parser.parse_args(args=argv)

        if len(args)>1:
            parser.error("Extra arguments - expecting only installer name")

        if self.options.config_choices_file:
            config_choices_file = os.path.abspath(os.path.expanduser(self.options.config_choices_file))
            if not os.path.exists(config_choices_file):
                parser.error("Configuration choices file %s does not exist" % config_choices_file)
            self.config_choices = ConfigChoices(config_choices_file)
        else:
            self.config_choices = ConfigChoices(use_defaults=self.options.use_defaults)

        # processing of --application-archive option
        if self.options.application_archive:
            app_archive = os.path.abspath(os.path.expanduser(self.options.application_archive))
            if not os.path.exists(app_archive):
                parser.error("Application archive %s does not exist" % app_archive)
            if self.options.config_choices_file:
                self.config_choices.choices_from_file[APPLICATION_ARCHIVE_PROP] = app_archive
            else:
                self.config_choices.app_archive_value = app_archive
            
        # figure out which installer we are running
        if installer_file_layout:
            self.installer_name = installer_file_layout.installer_name
            if len(args)==1 and installer_file_layout.installer_name!=args[0]:
                parser.error("installer name '%s' provided on commmand line does not match installer name provided by installer_file_layout '%s'"
                             % (args[0], installer_file_layout.installer_name))
        elif self.options.config_choices_file:
            if len(args)>0:
                parser.error("Do not specify installer on command line if running from a config choices file")
            self.installer_name = self.config_choices.get_installer_name()
        else:
            if len(args)==0:
                parser.error("Must provide name of installer")
            self.installer_name = args[0]

        self.config_choices.set_installer_name(self.installer_name)

        (self.installer_file_layout, self.deployment_home) = \
            cmdline_script_utils.process_standard_options(self.options, parser, installer_file_layout,
                                                          installer_name=self.installer_name)

        if self.options.upgrade_from:
            self.upgrade_from = os.path.abspath(os.path.expanduser(self.options.upgrade_from))
            if not os.path.isdir(self.upgrade_from):
                parser.error("Application backup directory %s does not exist" % self.upgrade_from)

        self.error_file = os.path.join(self.installer_file_layout.get_log_directory(),
                                       "user_error.json")
        self.config_error_file = get_config_error_file(self.installer_file_layout)

        if self.options.mgt_backends:
            import mgt_registration
            mgt_registration.validate_backend_names(self.options.mgt_backends, parser)
            # save backends in history for use in upgrades
            self.config_choices.choice_history[MGT_BACKENDS_PROP] = self.options.mgt_backends
        elif self.config_choices.choices_from_file and \
                self.config_choices.choices_from_file.has_key(MGT_BACKENDS_PROP):
            # If a previous run had management backends specified, use those
            self.options.mgt_backends = self.config_choices.choices_from_file[MGT_BACKENDS_PROP]
            import mgt_registration
            mgt_registration.validate_backend_names(self.options.mgt_backends, parser)


def run(req, logger):
    install_spec_option_no = select_configuration(req.installer_file_layout, req.config_choices)
    
    # If what the installer_config file says about passwords -- will be either True, False or None
    password_required = req.installer_file_layout.get_installer_config().is_password_required(install_spec_option_no)
    if req.options.no_password_file and password_required==True:
        parser.error("--no-password-file is not permitted with this installer")
    use_password = (password_required==True) or (password_required==None and (not req.options.no_password_file)) or \
                   (req.options.force_password_file==True)
    
    # need to manually record the deployment home in the choice history, as it is used
    # to validate other inputs
    req.config_choices.choice_history["Install directory"] = req.deployment_home

    # create the install spec
    target_machine = get_target_machine_resource(req.deployment_home, req.installer_file_layout.get_log_directory())
    hosts = create_install_spec(target_machine,
                                req.installer_file_layout.get_install_spec_template_file(install_spec_option_no),
                                req.installer_file_layout.get_install_spec_file(install_spec_option_no),
              req.installer_file_layout, logger)

    def get_pw_file_and_salt():
        return \
          (os.path.join(req.installer_file_layout.get_password_file_directory(),
                        pw_repository.REPOSITORY_FILE_NAME),
           os.path.join(req.installer_file_layout.get_password_file_directory(),
                        pw_repository.SALT_FILE_NAME))

    if req.upgrade_from and os.path.exists(os.path.join(req.installer_file_layout.get_password_file_directory(), "pw_repository")):
        # If we are running an upgrade and the old password file exists, we read it.
        # TODO: what if we need to add or change the password file?
        import engage.utils.pw_repository as pw_repository
        load_from_file = pw_repository.PasswordRepository.load_from_file
        (pw_file, pw_salt_file) = get_pw_file_and_salt()
        passwords = load_from_file(pw_file, pw_salt_file,
                                   get_password_input("Sudo password:",
                                                      read_from_stdin=req.options.subproc))
        req.config_choices.password_repository = passwords

    # here is were we handle any additional configuration inputs
    password_list = set_install_spec_properties(req.installer_file_layout, install_spec_option_no,
                                                req.config_choices, target_machine, logger)
    
    ## if req.upgrade_from and os.path.exists(os.path.join(req.installer_file_layout.get_password_file_directory(), "pw_repository")):
    ##     # If we are running an upgrade and the old password file exists, we read it.
    ##     # TODO: what if we need to add or change the password file?
    ##     import engage.utils.pw_repository as pw_repository
    ##     load_from_file = pw_repository.PasswordRepository.load_from_file
    ##     (pw_file, pw_salt_file) = get_pw_file_and_salt()
    ##     passwords = load_from_file(pw_file, pw_salt_file,
    ##                                get_password_input("Sudo password:",
    ##                                                   read_from_stdin=req.options.subproc))
    ## elif use_password or len(password_list)>0:
    if req.config_choices.password_repository:
        pass # already did the setup above
    elif use_password or len(password_list)>0:
        # Otherwise, if there is a fresh install, we generate a new password file
        # and pass along the in-memory copy of the database to the install engine.
        import engage.utils.pw_repository as pw_repository
        logger.info("Creating password file at %s" %
                    os.path.join(req.installer_file_layout.get_password_file_directory(), pw_repository.REPOSITORY_FILE_NAME))
        passwords = pw_repository.PasswordRepository(get_password_input("Sudo password:", read_from_stdin=req.options.subproc))
        passwords.add_key(target_machine['config_port']['sudo_password'],
                          passwords.user_key)
        for (key, value) in password_list:
            passwords.add_key(key, value)
        (pw_file, pw_salt_file) = get_pw_file_and_salt()
        passwords.save_to_file(pw_file,
                               salt_filename=pw_salt_file)
    else:
        passwords = None
        pw_file = None
        pw_salt_file = None

    # save the history file to user location, if provided
    if req.options.history_file:
        req.config_choices.save_history_file(os.path.abspath(os.path.expanduser(req.options.history_file)))
    # if fresh install, always save choices to config directory, for use in future upgradesa
    req.config_choices.save_history_file(os.path.join(req.installer_file_layout.get_config_choices_file(req.deployment_home)))
    

    # run the configuration engine
    preprocess_and_run_config_engine(req.installer_file_layout,
        req.installer_file_layout.get_install_spec_file(install_spec_option_no))

    # for now, dry run just exits at this point
    if req.options.dry_run:
        return 0

    if not req.upgrade_from: # this is a fresh install
        for host in hosts:
            if host["id"] != "master-host":
                setup_slave_host(host, req.deployment_home, pw_file, pw_salt_file)
        install_engine_args = []
        if passwords == None:
            install_engine_args.append("--no-password-file")
        if req.options.deployment_home:
            install_engine_args.append("--deployment-home=%s" % req.options.deployment_home)
        if req.options.force_stop_on_error:
            install_engine_args.append("--force-stop-on-error")
        if req.options.mgt_backends:
            install_engine_args.append("--mgt-backends=%s" % req.options.mgt_backends)
        install_engine_args = install_engine_args + log_setup.extract_log_options_from_options_obj(req.options)
        install_engine_args = install_engine_args + [req.installer_file_layout.get_install_script_file()]
        print "Invoking install engine with arguments %s" % install_engine_args
        return install_engine.main(install_engine_args, passwords)
    else:
        return upgrade_engine.upgrade(req.upgrade_from, req.installer_file_layout, req.deployment_home, req.options, passwords,
                                      atomic_upgrade=(not req.options.no_rollback_on_failed_upgrades))

def main(argv, installer_file_layout=None):
    install_request = InstallRequest()
    install_request.process_args(argv, installer_file_layout)
    logger = log_setup.setup_engage_logger(__name__)
    if os.path.exists(install_request.error_file):
        os.remove(install_request.error_file)
    if os.path.exists(install_request.config_error_file):
        os.remove(install_request.config_error_file)
    try:
        return run(install_request, logger)
    except upgrade_engine.UpgradeRollbackInProgress, e:
        e.write_error_to_file(os.path.join(install_request.installer_file_layout.get_log_directory(), "upgrade_error.json"))
        return 3 # magic number to indicate rollback is in progress
    except UserError, e:
        if installer_file_layout:
            raise # if called from another script, let that one handle it
        logger.exception("Aborting install due to error.")
        if not os.path.exists(install_request.error_file):
            e.write_error_to_file(install_request.error_file)
        return 1
    except:
        (ec, ev, et) = sys.exc_info()
        logger.exception("Unexpected exception: %s(%s)" %  (ec.__name__, ev))
        user_error = convert_exc_to_user_error(sys.exc_info(),
                                               errors[ERR_UNEXPECTED_EXC])
        user_error.write_error_to_log(logger)
        if not os.path.exists(install_request.error_file):
            user_error.write_error_to_file(install_request.error_file)
        return 1
        

def call_from_console_script():
    sys.exit(main(sys.argv[1:]))

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

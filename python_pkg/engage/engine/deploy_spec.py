"""Deploy based on an install specification.
"""
import os
import sys
import os.path
from optparse import OptionParser
import getpass
import json

# fix path if necessary (if running from source or running as test)
import fixup_python_path

import cmdline_script_utils
from host_resource_utils import get_target_machine_resource
from engage.engine.preprocess_resources import create_install_spec, validate_install_spec
import config_engine
import install_engine
from engage.utils.file import NamedTempFile
import engage.utils.process as procutils
import engage.utils.rdef as rdef
import engage.utils.log_setup as log_setup
from engage.utils.user_error import UserError, EngageErrInf, convert_exc_to_user_error, UserErrorParseExc, parse_user_error

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info


ERR_UNEXPECTED_EXC  = 1
define_error(ERR_UNEXPECTED_EXC,
             _("Aborting install due to unexpected error."))


def generate_pw_file(pw_file, pw_salt_file, resource_def_file,
                     install_script_file, logger, dry_run=False):
    with open(resource_def_file, "rb") as f:
        g = rdef.create_resource_graph(json.load(f))
    with open(install_script_file, "rb") as f:
        ilist = json.load(f)
    def prompt_for_password(base_prompt, pw_key):
        if dry_run:
            logger.info("prompt for password '" + base_prompt + "', to be stored at key '%s'" % pw_key)
            return "test"
        else:
            while True:
                pw1 = getpass.getpass(base_prompt + ":")
                pw2 = getpass.getpass(base_prompt + " (re-enter):")
                if pw1==pw2:
                    return pw1
                else:
                    print "Sorry, passwords do not match!"
    import engage.utils.pw_repository
    if procutils.is_running_as_root():
        master_key_prompt = "Master password"
    else:
        master_key_prompt = "Sudo password"
    master_key = prompt_for_password(master_key_prompt, "master")
    repos = engage.utils.pw_repository.PasswordRepository(master_key)
    if not procutils.is_running_as_root():
        sudo_pw_key = "GenForma/%s/sudo_password" % getpass.getuser()
        repos.add_key(sudo_pw_key, master_key)
        logger.info("Added sudo password to password repository as key %s" %
                    sudo_pw_key)
    for inst in ilist:
        r = g.get_resource(inst["key"])
        for (prop, default_val) in r.get_password_properties().items():
            if inst.has_key("config_port") and inst["config_port"].has_key(prop):
                pw_key = inst["config_port"][prop]
            elif default_val!=None:
                pw_key = default_val
            else:
                raise Exception("Resource instance %s (type %s) is missing a value for password property %s" % (inst["id"], inst["key"], prop))
            if not repos.has_key(pw_key):
                pw = prompt_for_password("Password for %s, property %s" %
                                         (inst["id"],prop), pw_key)
                repos.add_key(pw_key, pw)
    if not dry_run:
        repos.save_to_file(pw_file, pw_salt_file)
    logger.info("Wrote password file %s" % pw_file)
    return repos

class DeployRequest(object):
    """This class is for processing the command line arguments of the deployment
    and storing the resulting state as members.
    """
    def __init__(self):
        self.options = None
        self.ifl = None # installer file layout
        self.deployment_home = None
        self.error_file = None
        self.config_error_file = None
        self.tr = None # target resource
        self.input_spec_file = None
        self.pw_file = None
        self.pw_salt_file = None
        self.generate_pw_file = False

    def process_args(self, argv, installer_file_layout=None):
        usage = "usage: %prog [options] install_specification_file"
        parser = OptionParser(usage=usage)
        cmdline_script_utils.add_standard_cmdline_options(parser,
                                                          uses_pw_file=True)
        parser.add_option("--mgt-backends", dest="mgt_backends", default=None,
                          help="If specified, a list of management backend plugin(s)")
        parser.add_option("--generate-password-file", "-g",
                          dest="generate_password_file",
                          default=False, action="store_true",
                          help="If specified, generate a password file and exit")
        parser.add_option("--dry-run", dest="dry_run",
                          default=False, action="store_true",
                          help="If specified, do a dry run of the install.")

        (self.options, args) = parser.parse_args(args=argv)

        if len(args)!=1:
            parser.error("Incorrect number of arguments - expecting install spec name")
        self.input_spec_file = args[0]
        if not os.path.exists(self.input_spec_file):
            parser.error("Install specification file %s does not exist" %
                         self.input_spec_file)

        (self.ifl, self.deployment_home) = \
            cmdline_script_utils.process_standard_options(self.options, parser,
                                                          installer_file_layout,
                                                          installer_name=None)
        self.error_file = os.path.join(self.ifl.get_log_directory(),
                                       "user_error.json")
        self.config_error_file = config_engine.get_config_error_file(self.ifl)

        self.tr = get_target_machine_resource(self.deployment_home,
                                              self.ifl.get_log_directory())

        # figure out the password file stuff
        if not self.options.no_password_file:
            pw_dir = self.ifl.get_password_file_directory()
            self.pw_file = os.path.join(pw_dir, "pw_repository")
            self.pw_salt_file = os.path.join(pw_dir, "pw_salt")
            if os.path.exists(self.pw_file) and not self.options.generate_password_file:
                if not os.path.exists(self.pw_salt_file):
                    parser.error("Password salt file %s exists, but password file %s missing" % (self.pw_salt_file, self.pw_file))
            else:
                self.generate_pw_file = True
        else:
            if self.options.generate_password_file:
                parser.error("Cannot specify both --generate-password-file and --no-password-file")


        if self.options.mgt_backends:
            import mgt_registration
            mgt_registration.validate_backend_names(self.options.mgt_backends, parser)


    def _build_install_engine_args(self):
        install_engine_args = []
        if not self.pw_file:
            install_engine_args.append("--no-password-file")
        if self.options.deployment_home:
            install_engine_args.append("--deployment-home=%s" %
                                       self.options.deployment_home)
        if self.options.mgt_backends:
            install_engine_args.append("--mgt-backends=%s" %
                                       self.options.mgt_backends)
        install_engine_args.extend(log_setup.extract_log_options_from_options_obj(self.options))
        install_engine_args.append(self.ifl.get_install_script_file())
        return install_engine_args
            
            
    def run(self, logger):
        hosts = create_install_spec(self.tr, self.input_spec_file,
                                    self.ifl.get_install_spec_file(),
                                    self.ifl, logger)
        validate_install_spec(self.ifl.get_install_spec_file())
        config_engine.preprocess_and_run_config_engine(self.ifl,
                                                       self.ifl.get_install_spec_file())
        if self.generate_pw_file:
            pw_repos = generate_pw_file(self.pw_file, self.pw_salt_file,
                                        self.ifl.get_preprocessed_resource_file(),
                                        self.ifl.get_install_script_file(),
                                        logger,
                                        dry_run=self.options.dry_run)
        else:
            pw_repos = None
        ie_args = self._build_install_engine_args()
        if self.options.dry_run:
            logger.info("Call to install engine with args %s" % ie_args)
            logger.info("Deployment dry run successful.")
            return 0
        elif self.options.generate_password_file:
            logger.info("Password file complete, exiting")
            return 0
        else:
            return install_engine.main(ie_args, pw_database=pw_repos)

        
def main(argv, installer_file_layout=None):
    dr = DeployRequest()
    dr.process_args(argv, installer_file_layout)
    logger = log_setup.setup_engage_logger(__name__)
    if os.path.exists(dr.error_file):
        os.remove(dr.error_file)
    if os.path.exists(dr.config_error_file):
        os.remove(dr.config_error_file)
    try:
        return dr.run(logger)
    except UserError, e:
        if installer_file_layout:
            raise # if called from another script, let that one handle it
        logger.exception("Aborting install due to error.")
        if not os.path.exists(dr.error_file):
            e.write_error_to_file(dr.error_file)
        return 1
    except:
        (ec, ev, et) = sys.exc_info()
        logger.exception("Unexpected exception: %s(%s)" %  (ec.__name__, ev))
        user_error = convert_exc_to_user_error(sys.exc_info(),
                                               errors[ERR_UNEXPECTED_EXC])
        user_error.write_error_to_log(logger)
        if not os.path.exists(dr.error_file):
            user_error.write_error_to_file(dr.error_file)
        return 1
        

def call_from_console_script():
    sys.exit(main(sys.argv[1:]))

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


"""Deploy based on an install specification.
"""
import os
import sys
import os.path
from optparse import OptionParser
import json

# fix path if necessary (if running from source or running as test)
import fixup_python_path

import cmdline_script_utils
from host_resource_utils import get_target_machine_resource
from engage.engine.preprocess_resources import create_install_spec, validate_install_spec, merge_new_install_spec_into_existing
import config_engine
import install_engine
from engage.utils.file import NamedTempFile
import engage_utils.process as procutils
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



class DeployRequest(object):
    """This class is for processing the command line arguments of the deployment
    and storing the resulting state as members.
    """
    def __init__(self):
        self.options = None
        self.efl = None # installer file layout
        self.deployment_home = None
        self.error_file = None
        self.config_error_file = None
        self.tr = None # target resource
        self.input_spec_file = None
        self.pw_file = None
        self.pw_salt_file = None
        self.generate_pw_file = False

    def process_args(self, argv, engage_file_layout=None):
        usage = "usage: %prog [options] install_specification_file"
        parser = OptionParser(usage=usage)
        parser.add_option("-a", "--additive-install", default=False,
                          action="store_true",
                          help="If specified, an install already exists and we are adding resources to the deployment")
        cmdline_script_utils.add_standard_cmdline_options(parser,
                                                          uses_pw_file=True)
        (self.options, args) = parser.parse_args(args=argv)

        if len(args)!=1:
            parser.error("Incorrect number of arguments - expecting install spec name")
        self.input_spec_file = args[0]
        if not os.path.exists(self.input_spec_file):
            parser.error("Install specification file %s does not exist" %
                         self.input_spec_file)

        (self.efl, self.deployment_home) = \
            cmdline_script_utils.process_standard_options(self.options, parser,
                                                          engage_file_layout,
                                                          installer_name=None)
        ir_file = self.efl.get_installed_resources_file(self.deployment_home)
        if self.options.additive_install:
            if not os.path.exists(ir_file):
                parser.error("--additive-install specified, but existing install file %s does not exist" % ir_file)
        else:
            if os.path.exists(ir_file):
                parser.error("Installed resources file %s already exists. Specify --additive-install if you want to add resources to this deployment home" %
                             ir_file)
                
        self.error_file = os.path.join(self.efl.get_log_directory(),
                                       "user_error.json")
        self.config_error_file = config_engine.get_config_error_file(self.efl)

        self.tr = get_target_machine_resource(self.deployment_home,
                                              self.efl.get_log_directory())

        if self.options.mgt_backends:
            import mgt_registration
            mgt_registration.validate_backend_names(self.options.mgt_backends,
                                                    parser)

    def run(self, logger):
        if self.options.additive_install:
            # For an additive install, we rename the original install spec
            # and then create a new one that merges the spec with the already
            # installed resources.
            orig_spec_file = self.input_spec_file
            self.input_spec_file = orig_spec_file.replace('.json', '.merged.json') \
                                   if orig_spec_file.endswith('.json') \
                                   else orig_spec_file + '.merged'
            with open(orig_spec_file, 'rb') as f:
                install_spec_resources = json.load(f)
            irf = self.efl.get_installed_resources_file(self.deployment_home)
            with open(irf, 'rb') as f:
                installed_resources = json.load(f)
            merged_spec = merge_new_install_spec_into_existing(install_spec_resources,
                                                               installed_resources,
                                                               logger)
            with open(self.input_spec_file, 'wb') as f:
                json.dump(merged_spec, f)
            # Rename the old installed resource file so we don't lose it if
            # things fail.
            os.rename(irf, irf + '.prev') 
        try:
            hosts = create_install_spec(self.tr, self.input_spec_file,
                                        self.efl.get_install_spec_file(),
                                        self.efl, logger)
            validate_install_spec(self.efl.get_install_spec_file())
            config_engine.preprocess_and_run_config_engine(self.efl,
                                                           self.efl.get_install_spec_file())
        except:
            if self.options.additive_install:
                logger.debug("Additive install: Problem in preparing new install spec, reverting old install spec file")
                os.rename(irf + '.prev', irf)
            raise
        try:
            ie_args = cmdline_script_utils.extract_standard_options(self.options)
            return install_engine.main(ie_args, file_layout=self.efl,
                                       installer_supplied_pw_key_list=None)
        except:
            if self.options.additive_install and not os.path.exists(irf):
                logger.debug("Additive install: Problem in new install, reverting old install spec file")
                os.rename(irf + '.prev', irf)
            raise

        
def main(argv, engage_file_layout=None):
    dr = DeployRequest()
    dr.process_args(argv, engage_file_layout)
    logger = log_setup.setup_engage_logger(__name__)
    if os.path.exists(dr.error_file):
        os.remove(dr.error_file)
    if os.path.exists(dr.config_error_file):
        os.remove(dr.config_error_file)
    try:
        return dr.run(logger)
    except UserError, e:
        if engage_file_layout:
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


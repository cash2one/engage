#
# Main file for install engine
#

import sys
import os.path
from optparse import OptionParser
import json
import logging
import traceback

from engage.drivers.resource_metadata import parse_resource_from_json, parse_install_soln
from engage.engine.library import parse_library_files
from engage.utils.log_setup import parse_log_options, \
                                   setup_engine_logger, FakeLogger
from engage.engine.engage_file_layout import get_engine_layout_mgr
import engage.utils.pw_repository as pw_repository
import cmdline_script_utils
from engage.utils.user_error import UserError, EngageErrInf, convert_exc_to_user_error
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_MISSING_ARGS   = 1
ERR_WRONG_ARGCNT   = 2
ERR_BAD_SOLN_FILE  = 3
ERR_BAD_LIB_FILE   = 4
ERR_UNEXPECTED_EXC = 5
ERR_BAD_CACHE_DIR  = 6

define_error(ERR_MISSING_ARGS,
             _("Required Command line arguments were not specified."))
define_error(ERR_WRONG_ARGCNT,
             _("Wrong number of command line arguments, expecting %(argcnt)d."))
define_error(ERR_BAD_SOLN_FILE,
             _("Install solution file '%(filename)s' does not exist."))
define_error(ERR_BAD_LIB_FILE,
             _("Library file '%(filename)s' does not exist."))
define_error(ERR_UNEXPECTED_EXC,
             _("Aborting install due to unexpected error."))
define_error(ERR_BAD_CACHE_DIR,
             _("Software package cache directory '%(dirname)s' does not exist."))




class CmdLineError(UserError):
    def __init__(self, error_info, msg_args=None, option_parser=None):
        UserError.__init__(self, error_info, msg_args=msg_args)
        self.option_parser = option_parser
        if self.option_parser:
            self.command_args = \
                self.option_parser.usage.replace("%prog",
                                                 os.path.basename(sys.argv[0]))
            self.context = ["Usage: " + self.command_args]

    def __str__(self):
        return self.user_msg


class InstallEngineBase:
    """API for the install engine. This is implemented by InstallEngine
    as well as by test stubs for the installer.
    """
    def __init__(self):
        pass

    def run(self, install_soln_file, library_file):
        pass


class InstallEngine(InstallEngineBase):
    def __init__(self, logger, arg_info, pw_database=None):
        InstallEngineBase.__init__(self)
        self.logger = logger
        self.arg_info = arg_info
        self.pw_database = pw_database

    def _run_worker(self, multi_node=False):
        import install_plan
        import install_sequencer
        import install_context as ctx
        if not os.path.exists(self.arg_info.install_soln_file):
            raise CmdLineError(errors[ERR_BAD_SOLN_FILE],
                               msg_args={"filename":
                                         self.arg_info.install_soln_file})
        if not os.path.exists(self.arg_info.library_file):
            raise CmdLineError(errors[ERR_BAD_LIB_FILE],
                               msg_args={"filename": self.arg_info.library_file})
        resource_list = parse_install_soln(self.arg_info.install_soln_file)
        self.logger.info("Using software library %s." % self.arg_info.library_file)
        library = parse_library_files(self.arg_info.file_layout)
        if self.arg_info.options.no_password_file:
            assert self.pw_database==None
            # if no password file is being used, created a dummy password
            # object
            self.pw_database = pw_repository.PasswordRepository("")
        ctx.setup_context(self.arg_info.password_repository_dir,
                          self.arg_info.subproc, library, self.pw_database)
        if multi_node:
            install_sequencer.run_multi_node_install(install_plan.create_multi_node_install_plan(resource_list),
                                                     library, self.arg_info.options.force_stop_on_error)
            # TODO: need to consider whether we need to make any calls to the management API
            # for the master node in multi-node. Is there a way to register cross-node dependencies?
        else: # single node or slave
            mgr_pkg_list = [install_sequencer.get_manager_and_package(instance_md, library)
                            for instance_md in install_plan.create_install_plan(resource_list)]
            install_sequencer.run_install(mgr_pkg_list, library, self.arg_info.options.force_stop_on_error)
            if self.arg_info.options.mgt_backends:
                import mgt_registration
                mgt_registration.register_with_mgt_backends(self.arg_info.options.mgt_backends,
                                                            [mgr for (mgr, pkg) in mgr_pkg_list],
                                                            self.arg_info.deployment_home,
                                                            sudo_password=ctx.get_sudo_password(),
                                                            upgrade=False)

    def run(self):
        self._run_worker(False)


class InstallEngineMultiNode(InstallEngine):
    def __init__(self, logger, arg_info, pw_database=None):
        InstallEngineBase.__init__(self)
        self.logger = logger
        self.arg_info = arg_info
        self.pw_database = pw_database

    def run(self):
        self._run_worker(True)


class ArgInfo:
    """This class represents the parsed command line arguments and options.
    """
    def __init__(self, args, options, file_layout, deployment_home):
        self.install_soln_file = args[0]
        self.library_file = file_layout.get_software_library_file()
        self.password_repository_dir = file_layout.get_password_file_directory()
        self.options = options
        self.subproc = options.subproc
        self.file_layout = file_layout
        self.deployment_home = deployment_home

        
def parse_command_args(argv, file_layout):
    usage = "usage: %prog [options] install_model_file"
    parser = OptionParser(usage=usage)
    cmdline_script_utils.add_standard_cmdline_options(parser)
    parser.add_option("-m", "--multinode", action="store_true", dest="multinode",
                      default=False, help="Installation requires multiple nodes")
    parser.add_option("--force-stop-on-error", dest="force_stop_on_error",
                      default=False, action="store_true",
                      help="If specified, force stop any running daemons if the install fails. Default is to leave things running (helpful for debugging).")
    parser.add_option("--mgt-backends", dest="mgt_backends", default=None,
                      help="If specified, a list of management backend plugin(s)")
    (options, args) = parser.parse_args(args=argv)
    if len(args)==0:
        raise CmdLineError(errors[ERR_MISSING_ARGS], msg_args=None,
                           option_parser=parser)
    if len(args)!=1:
        raise CmdLineError(errors[ERR_WRONG_ARGCNT], msg_args={"argcnt":1},
                           option_parser=parser)
    parse_log_options(options, file_layout.get_log_directory())
    if options.deployment_home:
        deployment_home = options.deployment_home
    elif file_layout.has_deployment_home():
        deployment_home = file_layout.deployment_home
    else:
        parser.error("Running from source tree or dist home but did not specify deployment home via -d option")
    return ArgInfo(args, options, file_layout, deployment_home)



def main(argv, pw_database=None, file_layout=None):
    subproc = False # this will be overwritten after call to parse_command_args, if successful
    logger = FakeLogger()
    try:
        if file_layout==None:
            file_layout = get_engine_layout_mgr()
        try:
            arg_info = parse_command_args(argv, file_layout)
            subproc = arg_info.subproc
            logger = setup_engine_logger(__name__)
            if arg_info.options.multinode:
                install_engine = InstallEngineMultiNode(logger, arg_info, pw_database)
            else:
                install_engine = InstallEngine(logger, arg_info, pw_database)
            install_engine.run()
            return 0
        except CmdLineError, e:
            if subproc: raise # we don't print any help in subprocess mode
            sys.stderr.write(e.__str__() + "\n")
            if e.option_parser:
                e.option_parser.print_help()
            return 1
    except UserError, e:
        if __name__ != "__main__":
            raise # if called from another script, let that one handle it
        logger.exception("Aborting install due to error.")
        e.write_error_to_log(logger)
        if subproc and file_layout:
            e.write_error_to_file(os.path.join(file_layout.get_log_directory(), "error.json"))
            return 1
        else:
            raise # if running directly, let exception bubble to top
    except:
        (ec, ev, et) = sys.exc_info()
        logger.exception("Unexpected exception: %s(%s)" %  (ec.__name__, str(ev)))
        user_error = convert_exc_to_user_error(sys.exc_info(),
                                               errors[ERR_UNEXPECTED_EXC])
        if subproc and file_layout:
            user_error.write_error_to_file(os.path.join(file_layout.get_log_directory(), "user_error.json"))
            return 1
        else:
            raise # if running directly, let exception bubble to top
        
            
def call_from_console_script():
    sys.exit(main(sys.argv[1:]))
    

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


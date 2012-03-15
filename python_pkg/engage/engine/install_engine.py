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
import engage.engine.password as password
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


class InstallEngine(object):
    def __init__(self, engage_file_layout,
                 installer_supplied_pw_key_list=None):
        self.engage_file_layout = engage_file_layout
        self.installer_supplied_pw_key_list = installer_supplied_pw_key_list
        self.options = None
        self.args = None
        self.deployment_home = None
        self.logger = None
        self.pw_database = None

    def parse_command_args(self, argv):
        usage = "usage: %prog [options]"
        parser = OptionParser(usage=usage)
        cmdline_script_utils.add_standard_cmdline_options(parser)
        parser.add_option("-m", "--multinode", action="store_true",
                          dest="multinode",
                          default=False,
                          help="Installation requires multiple nodes")
        (self.options, self.args) = parser.parse_args(args=argv)
        if len(self.args) > 0:
            parser.error("Extra arguments for install engine")
        (dummy, self.deployment_home) = \
          cmdline_script_utils.process_standard_options(self.options,
                                                        parser,
                                                        self.engage_file_layout)
        self.logger = setup_engine_logger(__name__)
            

    def _run_worker(self, multi_node=False):
        import install_plan
        import install_sequencer
        import install_context as ctx
        efl = self.engage_file_layout
        install_script_file = efl.get_install_script_file()
        if not os.path.exists(install_script_file):
            raise CmdLineError(errors[ERR_BAD_SOLN_FILE],
                               msg_args={"filename":install_script_file})
        library_file = efl.get_preprocessed_library_file()
        resource_list = parse_install_soln(install_script_file)
        self.logger.info("Using software library %s." % library_file)
        library = parse_library_files(efl)
        gp = password.generate_pw_file_if_necessary
        self.pw_database = \
            gp(efl, self.deployment_home, resource_list, library,
               installer_supplied_pw_key_list=self.installer_supplied_pw_key_list,
               master_password_file=self.options.master_password_file,
               read_master_pw_from_stdin=self.options.subproc,
               suppress_master_password_file=self.options.suppress_master_password_file,
               generate_random_passwords=self.options.generate_random_passwords,
               dry_run=self.options.dry_run)
        if not self.pw_database:
            # if no password file is being used, created a dummy password
            # object
            self.pw_database = pw_repository.PasswordRepository("")
        ctx.setup_context(efl.get_password_file_directory(),
                          self.options.subproc, library, self.pw_database)
        if self.options.dry_run:
            self.logger.info("Dry run complete.")
            return
        ## if self.options.generate_password_file:
        ##     self.logger.info("Password file at %s, password salt file at %s." %
        ##                      (efl.get_password_database_file(),
        ##                       efl.get_password_salt_file()))
        ##     return

        if multi_node:
            install_sequencer.run_multi_node_install(install_plan.create_multi_node_install_plan(resource_list),
                                                     library,
                                                     self.options.force_stop_on_error)
            # TODO: need to consider whether we need to make any calls to the management API
            # for the master node in multi-node. Is there a way to register cross-node dependencies?
        else: # single node or slave
            mgr_pkg_list = [install_sequencer.get_manager_and_package(instance_md, library)
                            for instance_md in install_plan.create_install_plan(resource_list)]
            install_sequencer.run_install(mgr_pkg_list, library, self.options.force_stop_on_error)
            if self.options.mgt_backends:
                import mgt_registration
                mgt_registration.register_with_mgt_backends(self.options.mgt_backends,
                                                            [mgr for (mgr, pkg) in mgr_pkg_list],
                                                            self.deployment_home,
                                                            sudo_password=ctx.get_sudo_password(),
                                                            upgrade=False)

    def run(self):
        self._run_worker(self.options.multinode)


def main(argv, installer_supplied_pw_key_list=None, file_layout=None):
    subproc = False # this will be overwritten after call to parse_command_args, if successful
    logger = FakeLogger()
    try:
        if file_layout==None:
            file_layout = get_engine_layout_mgr()
        engine = InstallEngine(file_layout, installer_supplied_pw_key_list)
        try:
            engine.parse_command_args(argv)
            subproc = engine.options.subproc
            logger = engine.logger
            engine.run()
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


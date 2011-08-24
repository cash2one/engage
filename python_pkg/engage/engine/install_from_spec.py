
import sys
import os
import os.path
from optparse import OptionParser
import json
from subprocess import Popen
import getpass

# fix path if necessary (if running from source or running as test)
import fixup_python_path

import engage.utils.log_setup as log_setup
import engage.engine.install_engine as install_engine
from engage.engine.engage_file_layout import get_engine_layout_mgr



# TODO: need to figure out if we should allow getting
# password input from a file.
def get_password_input(prompt):
    while True:
        input1 = getpass.getpass(prompt)
        input2 = getpass.getpass("Retype password:")
        if input1 == input2:
            return input1
        else:
            print "Passwords do not match!"
    

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

def run_config_engine(installer_file_layout, install_spec_file):
    install_script_file = installer_file_layout.get_install_script_file()
    # we run the config engine from the same directory as where we want
    # the install script file, as it write the file to the current
    # directory.
    system("%s %s %s" % (installer_file_layout.get_configurator_exe(),
                         installer_file_layout.get_resource_def_file(),
                         install_spec_file),
           cwd=os.path.dirname(install_script_file))
    if not os.path.exists(install_script_file):
        raise Exception("Configuration engine must have encountered a problem: install script %s was not generated" % install_script_file)


def main(argv, installer_file_layout=None):
    usage = "usage: %prog [options] install_spec_file"
    parser = OptionParser(usage=usage)
    parser.add_option("-n", "--no-password-file", action="store_true", dest="no_password_file",
                      default=False, help="If specified, there is no password file to parse")
    parser.add_option("--force-stop-on-error", dest="force_stop_on_error",
                      default=False, action="store_true",
                      help="If specified, force stop any running daemons if the install fails. Default is to leave things running (helpful for debugging).")
    parser.add_option("--deployment-home", "-d", dest="deployment_home",
                      default=None,
                      help="Location of deployed application - can figure this out automatically unless installing from source")
    log_setup.add_log_option(parser)
    (options, args) = parser.parse_args(args=argv)

    if len(args)==0:
        parser.error("Missing install spec filename")
    if len(args)>1:
        parser.error("Extra arguments - expecting only install spec filename")
    install_spec_file = args[0]
    if not os.path.exists(install_spec_file):
        parser.error("Install spec file %s does not exist" % install_spec_file)

    installer_file_layout = get_engine_layout_mgr()
    

    log_setup.parse_log_options(options, installer_file_layout.get_log_directory())
    
    use_password = not options.no_password_file
    
    # setup the password repository
    if use_password:
        import engage.utils.pw_repository as pw_repository
        passwords = pw_repository.PasswordRepository(get_password_input("Sudo password:"))
        passwords.add_key(target_machine['config_port']['sudo_password'],
                          passwords.user_key)
    else:
        passwords = None

    # save the password files, if provided
    if use_password:
        passwords.save_to_file(os.path.join(installer_file_layout.get_password_file_directory(), pw_repository.REPOSITORY_FILE_NAME),
                               salt_filename=os.path.join(installer_file_layout.get_password_file_directory(), pw_repository.SALT_FILE_NAME))

    # run the configuration engine
    run_config_engine(installer_file_layout, install_spec_file)
    print "Configuration successful."

    install_engine_args = []
    if passwords == None:
        install_engine_args.append("--no-password-file")
    if options.force_stop_on_error:
        install_engine_args.append("--force-stop-on-error")
    install_engine_args = install_engine_args + log_setup.extract_log_options_from_options_obj(options)
    install_engine_args = install_engine_args + [installer_file_layout.get_install_script_file()]
    print "Invoking install engine with arguments %s" % install_engine_args
    return install_engine.main(install_engine_args, passwords)


def call_from_console_script():
    sys.exit(main(sys.argv[1:]))

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

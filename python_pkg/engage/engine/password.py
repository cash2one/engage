"""Utilities related to the password database.
"""
import sys
import os
import os.path
import json
import getpass
import copy
from optparse import OptionParser
import random
import string

# fix path if necessary (if running from source or running as test)
import fixup_python_path

import engage.utils.rdef as rdef
import engage.utils.pw_repository as pw_repository
from engage.drivers.resource_metadata import parse_resource_from_json
import engage.engine.engage_file_layout as engage_file_layout
import engage.utils.process as procutils
from engage.utils.log_setup import setup_engage_logger
logger = setup_engage_logger(__name__)

RANDOM_PW_LEN=12
RANDOM_CHARS=string.letters+string.digits

join = os.path.join
def abspath(p):
    return os.path.abspath(os.path.expanduser(p))


def _prompt_for_password(base_prompt, pw_key,
                         ask_only_once=False,
                         generate_random=False,
                         dry_run=False):
    if dry_run:
        logger.info("prompt for password '" + base_prompt + "', to be stored at key '%s'" % pw_key)
        return "test"
    elif generate_random:
        return ''.join([random.choice(RANDOM_CHARS) for i in range(RANDOM_PW_LEN)])
    else:
        while True:
            pw1 = getpass.getpass(base_prompt + ":")
            if ask_only_once:
                return pw1
            pw2 = getpass.getpass(base_prompt + " (re-enter):")
            if pw1==pw2:
                return pw1
            else:
                print "Sorry, passwords do not match!"

SUDO_PW_KEY = "GenForma/%s/sudo_password" % getpass.getuser()

def _add_sudo_password_to_repository(repos, dry_run=False):
    prompt = "Sudo password"
    def prompt_for_password():
        if dry_run:
            logger.info("prompt for password '" + prompt +
                        "', to be stored at key '%s'" % SUDO_PW_KEY)
            return "test"
        else:
            second_try = False
            while True:
                pw1 = getpass.getpass(prompt + ":")
                if pw1=="" and second_try:
                    raise Exception("User requested cancel of install")
                pw2 = getpass.getpass(prompt + " (re-enter):")
                if pw1==pw2:
                    logger.debug("Test the sudo password by running an ls")
                    try:
                        # test that the password actually works
                        procutils.run_sudo_program(["/bin/ls", "/"], pw1,
                                                   logger)
                        logger.debug("Successfully validated sudo password")
                        return pw1
                    except Exception, e:
                        logger.debug("Sudo password is not working, got exception %s" % e)
                        print "The sudo password is not working, please re-enter the password or hit return to cancel install"
                        second_try = True
                else:
                    print "Sorry, passwords do not match!"
    repos.update_key(SUDO_PW_KEY, prompt_for_password())


def _default_master_pwfile(deployment_home):
    return abspath(join(join(deployment_home, "config"), "master.pw"))

def _read_pwfile(fpath):
    with open(fpath, "r") as f:
        return f.read().rstrip()

def _get_master_password(deployment_home=None,
                         master_password_file=None,
                         read_master_pw_from_stdin=False,
                         ask_only_once=False,
                         dry_run=False):
    if deployment_home:
        default_pw_file = _default_master_pwfile(deployment_home)
    else:
        default_pw_file = None
    if master_password_file!=None:
        return _read_pwfile(master_password_file)
    elif default_pw_file and os.path.exists(default_pw_file):
        return _read_pwfile(default_pw_file)
    elif read_master_pw_from_stdin:
        return sys.stdin.read().rstrip()
    else:
        return _prompt_for_password("Master password", "master",
                                    ask_only_once=ask_only_once,
                                    dry_run=dry_run)

    
def generate_pw_file_if_necessary(engage_file_layout,
                                  deployment_home,
                                  parsed_install_solution,
                                  library,
                                  installer_supplied_pw_key_list=None,
                                  master_password_file=None,
                                  read_master_pw_from_stdin=False,
                                  suppress_master_password_file=False,
                                  generate_random_passwords=False,
                                  dry_run=False):
    """Do the password database setup.
    """
    # helper functions
    def get_master_password(ask_only_once=False):
        return _get_master_password(deployment_home,
                                    master_password_file,
                                    read_master_pw_from_stdin,
                                    ask_only_once=ask_only_once,
                                    dry_run=dry_run)
    def get_new_pw_db():
        return pw_repository.PasswordRepository(get_master_password())

    # Get some file locations from the engage_file_layout object
    efl = engage_file_layout
    preprocessed_resource_def_file = efl.get_preprocessed_resource_file()
    pw_file = efl.get_password_database_file()
    pw_salt = efl.get_password_salt_file()
                                   
    # First, load the resource definitions and instances
    with open(preprocessed_resource_def_file, "rb") as f:
        g = rdef.create_resource_graph(json.load(f))

    # read the existing password db if it exists
    if os.path.exists(pw_file):
        assert os.path.exists(pw_salt), "Password file present, but no password salt file at %s" % pw_salt
        load_from_file = pw_repository.PasswordRepository.load_from_file
        pw_db = load_from_file(pw_file, pw_salt,
                               get_master_password(ask_only_once=True))
        orig_pw_db = copy.copy(pw_db)
    else:
        pw_db = None
        orig_pw_db = None

    # obtain passwords referenced in the installer_config.json file, if any
    if installer_supplied_pw_key_list!=None and \
       len(installer_supplied_pw_key_list)>0:
        if pw_db==None:
            pw_db = get_new_pw_db()
        for (pw_key, pw_desc) in installer_supplied_pw_key_list:
            # we only ask if the pw is not already present
            if not pw_db.has_key(pw_key):
                pw_db.add_key(pw_key,
                              _prompt_for_password(pw_desc, pw_key,
                                                   generate_random=generate_random_passwords,
                                                   dry_run=dry_run))
                
    # Go through the install script. Check to see if there are any resources
    # that require root access. Also, see what passwords are missing,
    # and prompt for those.
    requires_root_access = False
    always_requires_pw_file = False
    for inst_md in parsed_install_solution:
        entry = library.get_entry(inst_md)
        if entry==None:
            raise Exception("Unable to find resource library entry for resource %s" % inst_md.key.__repr__())
        # See if the resource requires root access. If the resource says it
        # needs root access, we also check if it is already installed (according
        # to the installed property on the resource metadta). If it is already
        # installed and isn't a service, we don't need root access.
        if entry.requires_root_access() and \
           ((not inst_md.is_installed()) or
            hasattr(entry.get_manager_class(), "start")):
            logger.debug("Resource %s requires root access." % inst_md.id)
            requires_root_access = True
        if entry.always_requires_password_file():
            always_requires_pw_file = True
        r = g.get_resource(inst_md.key)
        pw_props = r.get_password_properties()
        if len(pw_props)==0:
            continue # no passwords on this resource
        if pw_db==None:
            pw_db = get_new_pw_db() # we lazily create the pw db
        for (prop, default_val) in pw_props.items():
            if inst_md.config_port.has_key(prop):
                pw_key = inst_md.config_port[prop]
            elif default_val!=None:
                pw_key = default_val
            else:
                raise Exception("Resource instance %s (type %s) is missing a value for password property %s" % (inst["id"], inst["key"], prop))
            if not pw_db.has_key(pw_key):
                pw_db.add_key(pw_key,
                              _prompt_for_password("Password for %s, property %s" %
                                                   (inst_md.id,prop), pw_key,
                                                   generate_random=generate_random_passwords,
                                                   dry_run=dry_run))

    # see if we need the sudo password. If so, ask for it and add to
    # password database
    if requires_root_access:
        if procutils.is_running_as_root():
            logger.debug("Root access required, but no sudo password is required as we are running as root")
        else:
            logger.debug("Root access required, asking for sudo password")
            if pw_db==None:
                pw_db = get_new_pw_db()
            _add_sudo_password_to_repository(pw_db, dry_run=dry_run)

    # In some cases, a resource may want to ensure that there always is a
    # password file.
    if always_requires_pw_file and pw_db==None:
        pw_db = get_new_pw_db()
    
    # write out the password database, if it changed
    if pw_db and (orig_pw_db==None or orig_pw_db.data!=pw_db.data):
        logger.info("Writing password file to %s" % pw_file)
        if not dry_run:
            pw_db.save_to_file(pw_file, pw_salt)
    if pw_db and (not suppress_master_password_file) and deployment_home:
        # write out the master password to the default file if it was not already
        # there.
        master_pwfile = _default_master_pwfile(deployment_home)
        if (not os.path.exists(master_pwfile)) or \
           _read_pwfile(master_pwfile)!=pw_db.user_key:
            with open(master_pwfile, "w") as f:
                f.write(pw_db.user_key)
        os.chmod(master_pwfile, 0600)
            
    if pw_db==None:
        logger.info("No password database required")
    return pw_db


def get_password_db(engage_file_layout, options):
    """Utilities run after the initial deployment use this to get the password
    database or a dummy.
    """
    efl = engage_file_layout
    if os.path.exists(efl.get_password_database_file()):
        logger.debug("Password database file found")
        pw_file = efl.get_password_database_file()
        pw_salt = efl.get_password_salt_file()
        master_password = _get_master_password(efl.get_deployment_home(),
                                               options.master_password_file,
                                               options.subproc,
                                               ask_only_once=True,
                                               dry_run=False)
        return pw_repository.PasswordRepository.load_from_file(pw_file,
                                                               pw_salt,
                                                               master_password)
    else:
        logger.debug("No password database file found")
        return pw_repository.PasswordRepository("")
        

def create_password_db(deployment_home, master_password,
                       password_dict, sudo_password=None):
    """Create a password database file in the specified deployment home.
    This is helpful for running tests that require passwords or for
    other automation. password_dict should be a map of key/value pairs.
    If sudo_password is provided, its value is added to the repository
    as the sudo password.
    """
    if not os.path.exists(deployment_home):
        raise Exception("Deployment home %s does not exist" % deployment_home)
    config_dir = os.path.join(deployment_home, "config")
    if not os.path.exists(config_dir):
        raise Exception("Configuration directory %s is missing" %
                        config_dir)
    pw_db = pw_repository.PasswordRepository(master_password,
                                             data=password_dict)
    if sudo_password:
        pw_db.add_key(SUDO_PW_KEY, sudo_password)
    pw_file = os.path.join(config_dir, pw_repository.REPOSITORY_FILE_NAME)
    pw_salt = os.path.join(config_dir, pw_repository.SALT_FILE_NAME)
    pw_db.save_to_file(pw_file, salt_filename=pw_salt)


def main():
    """This provides a command line interface to the password database,
    with awareness of a deployment home's file layout
    """
    usage = "\n %prog [options] view [key]\n %prog [options] create input_filename\n %prog [options] update key"
    parser = OptionParser(usage=usage)
    parser.add_option("--deployment-home", "-d", dest="deployment_home",
                      default=None,
                      help="Location of deployed application - can figure this out automatically unless installing from source")
    (options, args) = parser.parse_args()

    # check the command line
    valid_commands = ["view", "view-json", "update", "create"]
    if len(args)==0:
        command = "view"
    else:
        command = args[0]
        if command not in valid_commands:
            parser.error("Invalid command %s" % command)        
    if len(args)>2:
        parser.error("Too many arguments")
    if command=="update" and len(args)!=2:
        paser.error("Need to specify key to be updated")
    if command=="create":
        if len(args)!=2:
            parser.error("Need to specify input filename")
        create_input_filename = abspath(args[1])
        if not os.path.exists(create_input_filename):
            parser.error("Input file %s does not exist" % create_input_filename)
    if command=="view-json" and len(args)>1:
        parser.error("view-json does not accept any additional arguments")

    # setup the file layout
    efl = engage_file_layout.get_engine_layout_mgr()
    if options.deployment_home:
        dh = abspath(options.deployment_home)
        if not os.path.exists(dh):
            parser.error("Deployment home %s not found" % dh)
    elif efl.has_deployment_home():
        dh = efl.get_deployment_home()
    else:
        parser.error("Not running from a deployment home, and -d was not specified")
    
    # read the existing password database, if present
    pw_dir = os.path.join(dh, "config")
    pw_file = os.path.join(pw_dir, pw_repository.REPOSITORY_FILE_NAME)
    salt_file = os.path.join(pw_dir, pw_repository.SALT_FILE_NAME)
    if os.path.exists(pw_file) and command!="create":
        pw_db = \
          pw_repository.PasswordRepository.load_from_file(pw_file, salt_file,
                                                          _get_master_password(ask_only_once=True))
    else:
        pw_db = pw_repository.PasswordRepository(_get_master_password())

    # run the commands
    if command=="view":
        if len(args)==2:
            key = args[1]
            if not pw_db.has_key(key):
                print "Password database does not contain key '%s'" % key
                return -1
            print "'%s' password is '%s'" % (key, pw_db.get_value(key))
            return 0
        else:
            for (k, v) in pw_db.items():
                print "'%s' password is '%s'" % (k, v)
            print "%d entries found." % len(pw_db.items())
            return 0
    elif command=="view-json":
        print json.dumps(pw_db.data, indent=2)
        return 0
    elif command=="update":
        key = args[1]
        pw_db.update_key(key,
                         _prompt_for_password("Enter password for key '%s'" %
                                              key, key))
        pw_db.save_to_file(pw_file, salt_file)
        print "Updated password database with key '%s'" % key
        return 0
    else:
        assert command=="create"
        try:
            with open(create_input_filename, "rb") as f:
                data = json.load(f)
        except e:
            parser.error("Unable to parse input JSON file %s: %s" %
                         (input_filename, string(e)))
        if not isinstance(data, dict):
            parser.error("Input file %s does not contain an object/dictionary" %
                         input_filename)
        for (k, v) in data.items():
            pw_db.add_key(k, v)
        pw_db.save_to_file(pw_file, salt_file)
        print "Created password database"
        return 0

if __name__ == "__main__": sys.exit(main())

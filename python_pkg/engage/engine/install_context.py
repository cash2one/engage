"""Global context for install engine. Currently, this is just a bunch of
global variables initialized via install_engine.py. Eventually, should refactor into
a context object which is passed to each resource manager.
"""

import os.path
import sys
import getpass

import engage.utils.pw_repository as pwr


password_repository = None
config_dir = None
cipher_file = None
salt_file = None

# we save the package library in a global so that resource managers can load
# additional packages (e.g. patches) during the install
package_library = None



def setup_context(config_dir_, subprocess_mode, package_library_, pw_database):
    """Setup some global state.
    
    Load the password repository and set the password_repository module variable.
    This requires obtaining a password from the user. If running in subprocess mode,
    we read the password from stdin. Otherwise, we use getpass to prompt the user for
    the password from the tty.

    In the event that we already have a password database, we just use that.
    """
    global password_repository, config_dir, cipher_file, salt_file, \
           package_library
    config_dir = config_dir_
    package_library = package_library_
    if pw_database:
        #If we already have an in-memory password database,
        # us that and don't try to read from the file.
        password_repository = pw_database
        return
    cipher_file = os.path.join(config_dir, pwr.REPOSITORY_FILE_NAME)
    salt_file = os.path.join(config_dir, pwr.SALT_FILE_NAME)
    if subprocess_mode:
        user_key = sys.stdin.read().rstrip()
    else:
        user_key = getpass.getpass()
    password_repository = pwr.PasswordRepository.load_from_file(cipher_file,
                                                                salt_file,
                                                                user_key)

def get_sudo_password(username=None):
    """Return the sudo password entry. If no entry is present,
    returns None. If the username is not specified, we use
    getpass.getuser(), the same as used by system_info.py.
    """
    global password_repository
    if not password_repository:
        return None
    if not username:
        username = getpass.getuser()
    key = "GenForma/%s/sudo_password" % username
    if not password_repository.has_key(key):
        return None
    return password_repository.get_value(key)

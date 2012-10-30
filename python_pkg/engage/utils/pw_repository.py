"""Module to maintain an encrypted password repository in a file. The repository is
just a set of key-value pairs. There is a command line interface to set and read the
repository. We currently use the AES encryption standard. This has limitations on
the length of keys and the data to be encrypted (both must be a multiple of 16).
To get around the key length issue, we extend the user's key with a portion of
a randomly generated "salt" string. The full salt string (whose length is always
KEY_LENGTH) is stored in a separate file.

This module uses the Python Cryptography Toolkit
(http://www.amk.ca/python/code/crypto.html) to do the actual encryption.
"""
import sys
import os
import os.path
from optparse import OptionParser
from random import choice, randint
import string, sys
import json
import getpass
import traceback
import gettext
import base64
_ = gettext.gettext

from user_error import UserError, convert_exc_to_user_error, InstErrInf
import logging

logger = logging.getLogger(__name__)

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = InstErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_PW_DECRYPTION  = 1
ERR_UNEXPECTED_EXC = 2
ERR_PW_WRONG_ARGS  = 3
ERR_PW_INTERNAL    = 4
ERR_PW_BAD_DIR     = 5
ERR_PW_INVALID_KEY = 6
ERR_PW_PYCRYPTO    = 7


define_error(ERR_PW_DECRYPTION,
             _("Unable to decrypt password repository. Perhaps the wrong key was specified."))
define_error(ERR_UNEXPECTED_EXC,
             _("Unexpected error in password repository."))
define_error(ERR_PW_WRONG_ARGS,
             _("Wrong number of arguments: expecting 1 (repository file directory), got %(argcnt)d"))
define_error(ERR_PW_INTERNAL,
             _("Internal error in password repository."))
define_error(ERR_PW_BAD_DIR,
             _("Repository directory %(dirname)s does not exist"))
define_error(ERR_PW_INVALID_KEY,
             _("Repository does not contain an entry for key '%(key)s'"))
define_error(ERR_PW_PYCRYPTO,
             _("The Crypto python module (www.pycrypto.org) is required, but either not installed or installed incorrectly. The python used was at '%(py)s'. The error thrown when attempting to import it was '%(exc)s'"))


# Import the crypto libraries. These are not set up by default on
try:
    import Crypto
    from Crypto.Cipher import AES
    logger.debug("Imported Crypto module successfully.")
except ImportError:
    (et, ev, tb) = sys.exc_info()
    logger.exception("Unable to import Crypto.Cipher.AES")
    exc = convert_exc_to_user_error((et, ev, tb), errors[ERR_PW_PYCRYPTO],
                                    msg_args={"exc":"%s(%s)" % (et.__name__, str(ev)),
                                              "py":sys.executable})
    exc.developer_msg = "If on MacOSX, and you are having trouble installing pycrypto, take a look at http://mike.pirnat.com/2011/02/08/building-pycrypto-on-snow-leopard-and-non-apple-python/"
    raise exc


#
# Constants
#

# length of key to use
KEY_LENGTH = 32

# key length must be a multiple of the following AES-specfic value
KEY_MOD = 16
# length of data passed to low level encryption alg. must be a multiple of the following AES-specific value
DATA_MOD = 16

REPOSITORY_FILE_NAME = "pw_repository"
SALT_FILE_NAME = "pw_salt"


def gen_password(length, chars=string.letters+string.digits):
    return ''.join([ choice(chars) for i in range(length) ])


def get_new_salt(key_len):
    return gen_password(key_len)


def user_key_to_internal_key_and_salt(user_key, key_len):
    """
    AES Keys must be either 16, 24, or 32 bytes long. We take an arbitrary length
    user key and create a key 32 bytes long,  by adding part of a salt to it (if the
    user key is less than 32 bytes) or truncating the user key. Returns the
    internal key and the salt.
    
    >>> (k, s) = user_key_to_internal_key_and_salt("1234567890", 32)
    >>> len(k)
    32
    >>> len(s)
    32
    >>> k[0:10]
    '1234567890'
    >>> k[10:32]==s[0:22]
    True
    >>> (k, s) = user_key_to_internal_key_and_salt("12345678911234567892123456789312", 32)
    >>> k
    '12345678911234567892123456789312'
    >>> (k, s) = user_key_to_internal_key_and_salt("123456789112345678921234567893123", 32)
    >>> k
    '12345678911234567892123456789312'
    """
    salt = get_new_salt(key_len)
    salt_use_len = key_len - len(user_key)
    if salt_use_len > 0:
        internal_key = user_key + salt[0:salt_use_len]
    else:
        internal_key = user_key[0:key_len]
    return (internal_key, salt)


def user_key_and_salt_to_internal_key(user_key, salt, key_len):
    """Given the user key (of arbitrary length) and a key_len-byte salt, return the
    key_len-byte internal key.
    >>> uk = "1234567890"
    >>> (ik, s) = user_key_to_internal_key_and_salt(uk, 32)
    >>> ik2 = user_key_and_salt_to_internal_key(uk, s, 32)
    >>> ik2 == ik
    True
    >>> uk = "123456789112345678921234567893123"
    >>> (ik, s) = user_key_to_internal_key_and_salt(uk, 32)
    >>> ik2 = user_key_and_salt_to_internal_key(uk, s, 32)
    >>> ik2 == ik
    True
    """
    assert len(salt) == key_len
    if len(user_key)<key_len:
        salt_use_len = key_len - len(user_key)
        return user_key + salt[0:salt_use_len]
    else:
        return user_key[0:key_len]


def encrypt(user_key, message, key_len, salt=None):
    assert (len(message) % DATA_MOD) == 0 # AES data must be multiple of DATA_MOD
    assert (key_len % KEY_MOD) == 0 # keys must be multiples of KEY_MOD
    if salt == None:
        (internal_key, salt) = user_key_to_internal_key_and_salt(user_key, key_len)
    else:
        internal_key = user_key_and_salt_to_internal_key(user_key, salt, key_len)
    obj = AES.new(internal_key, AES.MODE_ECB)
    ciphertext = obj.encrypt(message)
    return (ciphertext, salt)


def decrypt(user_key, salt, key_len, ciphertext):
    """
    >>> key = "foobar"
    >>> message = "this is a test of the emergency "
    >>> (ciphertext, salt) = encrypt(key, message, 32)
    >>> ciphertext != message
    True
    >>> plaintext = decrypt(key, salt, 32, ciphertext)
    >>> plaintext == message
    True
    """
    assert (len(ciphertext) % DATA_MOD) == 0
    assert (key_len % KEY_MOD) == 0
    iternal_key = user_key_and_salt_to_internal_key(user_key, salt, key_len)
    obj = AES.new(iternal_key, AES.MODE_ECB)
    return obj.decrypt(ciphertext)


def encrypt_object(user_key, obj, salt=None, key_len=KEY_LENGTH, add_random_padding=True):
    """Encrypt a json-able python object, returning a pair consisting of
    the ciphertext and a random salt. The resulting cyphertext is binary.
    """
    data = json.dumps(obj)
    data = data + '\0' # end of object character
    data_len = len(data)
    random_padding_blocks = randint(0, 10) if add_random_padding else 0
    padding_len = (DATA_MOD - (data_len % DATA_MOD)) + (random_padding_blocks*DATA_MOD)
    padding = ''.join([ choice(string.printable) for i in range(padding_len) ])
    data = data + padding
    assert (len(data) % DATA_MOD) == 0
    return encrypt(user_key, data, key_len, salt)


def encrypt_object_as_string(user_key, obj, salt=None, key_len=KEY_LENGTH, add_random_padding=True):
    """Encrypt a json-able python object, returning a pair consisting of
    the ciphertext and a random salt. The resulting cyphertext is an
    ASCII string.
    """
    (ciphertext, salt) = encrypt_object(user_key, obj, salt, key_len, add_random_padding)
    return (base64.standard_b64encode(ciphertext), salt)


def decrypt_object(user_key, salt, ciphertext, key_len=KEY_LENGTH):
    """Decrypt the provided ciphertext and then parse the json, returning the resulting
    python object.
    >>> d = {"foo":"bar", "bit":346, "t":True}
    >>> uk = "this is a test"
    >>> (c, s) = encrypt_object(uk, d)
    >>> d1 = decrypt_object(uk, s, c)
    >>> d1 == d
    True
    """
    data = decrypt(user_key, salt, key_len, ciphertext)
    idx = data.find("\0")
    if idx == (-1):
        raise UserError(errors[ERR_PW_DECRYPTION],
                        developer_msg="Unable to find end of object marker in decrypted text")
    obj_data = data[0:idx]
    try:
        return json.loads(obj_data)
    except:
        raise UserError(errors[ERR_PW_DECRYPTION],
                        developer_msg="Unable to parse decrypted, serialized representation")

def decrypt_object_from_string(user_key, salt, ciphertext, key_len=KEY_LENGTH):
    """Decrypt the object, where the cipher text was base64 encoced
    """
    binary_ciphertext = base64.standard_b64decode(ciphertext)
    return decrypt_object(user_key, salt, binary_ciphertext, key_len)


class StaticMethod:
    """Decorator to create a static method
    """
    def __init__(self, anycallable):
        self.__call__ = anycallable

class PasswordRepository:
    """Maintains a password repository in memory as a set of key value pairs.
    """
    def __init__(self, user_key, data=None, salt=None):
        self.user_key = user_key
        self.key_len = KEY_LENGTH
        if data != None: self.data = data
        else: self.data = {}
        if salt != None: self.salt = salt
        else: self.salt = get_new_salt(self.key_len)

    def add_key(self, key, value):
        assert self.data.has_key(key) == False
        self.data[key] = value

    def update_key(self, key, value):
        self.data[key] = value

    def has_key(self, key):
        return self.data.has_key(key)

    def get_value(self, key):
        if not self.data.has_key(key):
            raise UserError(errors[ERR_PW_INVALID_KEY],
                            msg_args={"key":key})
        return self.data[key]

    def items(self):
        """Return the contents of the repository as a sequence of key, value pairs.
        """
        return self.data.items()

    def num_entries(self):
        """Return the number of entries.
        """
        return len(self.data)

    def get_salt(self):
        return self.salt

    def dumps(self):
        """Returns the encrypted representation of the repository.
        """
        (ciphertext, s) = encrypt_object(self.user_key, self.data,
                                         self.salt, self.key_len)
        return ciphertext

    def save_to_file(self, filename, salt_filename=None):
        """Save the encrypted repository the the specified file. If specified, also
        saves the salt to a file.
        """
        ciphertext = self.dumps()
        f = open(filename, "wb")
        os.fchmod(f.fileno(), 0600) # change permissions to make this unreadable to other users
        f.write(ciphertext)
        f.close()
        if salt_filename != None:
            sf = open(salt_filename, "wb")
            os.fchmod(sf.fileno(), 0600) # change permissions to make this unreadable to other users
            sf.write(self.salt)
            sf.close()

    def __repr__(self):
        d = {}
        for k in self.data.keys():
            v = self.data[k]
            if v==None:
                d[k] = None
            elif len(v)==0:
                d[k] = ""
            else:
                d[k] = "*" * len(v)
        return d.__repr__()

    @StaticMethod
    def loads(ciphertext, salt, user_key):
        """Static (class-level) method to create a password repository from a
        ciphertext string, salt, and user key.

        >>> uk = "foobar1"
        >>> r1 = PasswordRepository(uk)
        >>> r1.add_key("pw1", "qwerty")
        >>> r1.add_key("pw2", "this is a pw")
        >>> r1.num_entries()
        2
        >>> ciphertext = r1.dumps()
        >>> salt = r1.get_salt()
        >>> r2 = loads(ciphertext, salt, uk)
        >>> r2.num_entries()
        2
        >>> r2.get_value("pw1")
        'qwerty'
        >>> r2.get_value("pw2")
        'this is a pw'
        """
        data = decrypt_object(user_key, salt, ciphertext, KEY_LENGTH)
        return PasswordRepository(user_key, data, salt)
    
    @StaticMethod
    def load_from_file(filename, salt_filename, user_key):
        """Static (class-level) method to create a password repository from an
        encrypted file and salt file.
        """
        sf = open(salt_filename, "rb")
        salt = sf.read()
        sf.close()
        cf = open(filename, "rb")
        ciphertext = cf.read()
        cf.close()
        assert len(salt) == KEY_LENGTH
        return PasswordRepository.loads(ciphertext, salt, user_key)


def _test():
    print "Running tests for %s ..." % sys.argv[0]
    import doctest
    results = doctest.testmod()
    if results.failed>0: return 1
    else: return 0


def main():
    usage = "usage: %prog [options] repository_directory"
    parser = OptionParser(usage=usage)
    parser.add_option("--test", action="store_true", dest="test",
                      default=False, help="Run tests and exit")
    parser.add_option("--subproc", "-s", action="store_true", dest="subproc",
                      default=False, help="Run in subprocess mode")
    parser.add_option("--set-from-stdin", action="store_true", dest="set_from_stdin",
                      default=False,
                      help="Set value of repository from JSON data passed via standard input")
    parser.add_option("--install-eng-dir", action="store", dest="install_eng_dir",
                      default=".",
                      help="Install engine directory (used in subprocess mode)");
    parser.add_option("--errorfile", action="store", dest="errorfile",
                      default="install.error",
                      help="Location of error file (used in subprocess mode)")
    parser.add_option("--debug", action="store_true", dest="debug",
                      default=False, help="Set debug mode (not currently used)")
    parser.add_option("--repository-file", action="store", dest="repository_file",
                      default=REPOSITORY_FILE_NAME,
                      help="Name of password repository file (defaults to '%s')" %
                           REPOSITORY_FILE_NAME)
    parser.add_option("--salt-file", action="store", dest="salt_file",
                      default=SALT_FILE_NAME,
                      help="Name of password repository file (defaults to '%s')" %
                           SALT_FILE_NAME)
    (options, args) = parser.parse_args()
    try:
        if options.test:
            return _test()
        if len(args) != 1:
            if not options.subproc: parser.print_help()
            raise UserError(errors[ERR_PW_WRONG_ARGS], msg_args={"argcnt":len(args)})
        repository_dir = args[0]
        if not os.path.exists(repository_dir):
            raise UserError(errors[ERR_PW_BAD_DIR],
                            msg_args={"dirname":repository_dir});
        cipher_file = os.path.join(repository_dir, options.repository_file)
        salt_file = os.path.join(repository_dir, options.salt_file)

        if options.set_from_stdin:
            serialized_json_data = sys.stdin.read()
            json_data = json.loads(serialized_json_data)
            user_key = json_data[u"user_key"]
            repos = json_data[u"repos"]
            if not isinstance(repos, dict):
                raise UserError(errors[ERR_PW_INTERNAL],
                                developer_msg="Password repository must be a dictionary/map.")
            r = PasswordRepository(user_key, repos)
            r.save_to_file(cipher_file, salt_file)
            logger.debug("Saved repository with %d keys" % r.num_entries())
        else:
            user_key = getpass.getpass()
            repos = PasswordRepository.load_from_file(cipher_file, salt_file, user_key)
            print "*********** Repository Data ***************"
            for (key, value) in repos.items():
                print "Key: '%s', value: '%s'" % (key, value)
            print "******* End of Repository Data ************"
        return 0
    except UserError, e:
        logger.error("Aborting due to error.")
        e.write_error_to_log(logger)
        if options.subproc:
            e.write_error_to_file(options.errorfile)
            return 1
        else:
            raise # if running directly, let exception bubble to top
    except:
        error = convert_exc_to_user_error(sys.exc_info(),
                                          errors[ERR_UNEXPECTED_EXC])
        error.write_error_to_log(logger)
        if options.subproc:
            error.write_error_to_file(options.errorfile)
            return 1
        else:
            raise # if running directly, let exception bubble to top
    
    
if __name__ == "__main__": sys.exit(main())

"""
User level error handing. We define a special exception class, UserError,
to identify errors which can be displayed directly to the end user. The
set of these errors can be determined statically (by importing each of the
modules) for translation and documentation purposes.

The code in the engage.utils package should, as a rule, not make use of the
user error facility. If it makes sense for a given function in engage.utils
to throw a UserError, it should be clearly documented in the function's docstring.

It is assumed that the public methods for resource managers can throw user errors.
For utility functions, it is recommend to document if the function can throw any
user errors.


Boilerplate
===========
Unfortunately, due to the lack of macros in Python, you need to put a little
bit of boilerplate code in each module that will use this facility. This
code defines the set up error messages used by the module. See the annotated
example below.

Example Code
------------
# import the relevant functions from this module
from engage.utils.user_error import UserError, EngageErrInf, convert_exc_to_user_error

# this is for translation. Nesting all error message strings in _() which maps
# to gettext.gettext
import gettext
_ = gettext.gettext

# The errors dict is a mapping from error message code to
# ErrorInfo objects. This name must always be 'errors' so that static
# tools can get to this data.
errors = { }

# This is a convenience function that defines a new error and
# adds it to the errors dict. It must be defined in each module due
# to the __name__ parameter passed to the ErrorInfo object (used as the
# subarea for the error). The subarea should always be __name__ in order to
# ensure that each module forms a unique namespace.
def define_error(error_code, msg):
    global errors
    # instantiate an ErrorInfo object
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# Here is where we define the constants used for identifying each
# error in the file. This mapping should not be changed (changing it could
# screw up translations and documentation).
BACKUP_FILE_NOT_FOUND_ERROR = 1
EXC_IN_BACKUP_CALL          = 2
EXC_IN_RESTORE_CALL         = 3

# here is where we define the actual error messages
define_error(BACKUP_FILE_NOT_FOUND_ERROR,
             _("Unable to find backup file for resource '%(id)s', tried '%(file)s' and '%(compressed_file)s'"))
define_error(EXC_IN_BACKUP_CALL,
             _("An exception was thrown during backup of resource '%s(id)s' to %(file)s"))
define_error(EXC_IN_RESTORE_CALL,
             _("An exception was thrown during restore of resource '%s(id)s' from %(file)s"))

"""

import sys
import traceback
import json

# error area definitions
AREA_ENGAGE="Engage"
AREA_CONFIG="Config" # used by the Ocaml configuration engine
AREA_DJANGO_SDK="DjangoSDK"
AREA_PAAS="PaaS" # platform as a service

# old error area definitions, just for backward compatibility
AREA_INSTALL = AREA_ENGAGE
AREA_SCRIPTS = AREA_ENGAGE
AREA_GUI = AREA_ENGAGE


class ErrorInfo:
    def __init__(self, area, subarea, error_code, message_templ):
        self.area = area
        if subarea=="__main__":
            # if called from the main module of a program, use the program's
            # name as a subarea
            self.subarea = sys.argv[0].replace(".py", "")
        else:
            self.subarea = subarea
        self.error_code = error_code
        self.message_templ = message_templ

class EngageErrInf(ErrorInfo):
    """Use this in Engage modules to statically define an error.
    Each module should have a map called "errors" which is indexed by error code
    and has an InstErrInf entry for each error defined by the module.
    """
    def __init__(self, subarea, error_code, message_templ):
        ErrorInfo.__init__(self, AREA_ENGAGE, subarea, error_code, message_templ)

# for backwards compatibility
InstErrInf = EngageErrInf
ScriptErrInf = EngageErrInf

class UserError(Exception):
    def __init__(self, error_info, msg_args=None, developer_msg=None,
                 context=None):
        self.area = error_info.area
        self.subarea = error_info.subarea
        self.error_code = error_info.error_code
        if msg_args != None:
            self.user_msg = error_info.message_templ % msg_args
        else:
            self.user_msg = error_info.message_templ
        self.developer_msg = developer_msg
        self.context = context

    def __str__(self):
        return "[%s][%s][%d] %s" % (self.area, self.subarea, self.error_code,
                                    self.user_msg)

    def json_repr(self):
        """Return an in-memory, unserialized json representation of the
        error.
        """
        json = {"usererror": self.user_msg, "logarea": self.subarea,
                "component": self.area, "errorcode": self.error_code}
        if self.developer_msg:
            json["deverror"] = self.developer_msg
        if self.context:
            context_list = []
            for entry in self.context:
                context_list.append(entry.__str__())
            json["context"] = context_list
        return json

    def write_error_to_log(self, logger):
        logger.error(self.user_msg)
        logger.error("Error code: [%s][%s][%d]" % (self.area, self.subarea,
                                                   self.error_code))
        if self.developer_msg != None:
            logger.debug("Developer message: %s" % self.developer_msg)
        if self.context != None:
            logger.debug("Context:")
            for line in self.context:
                logger.debug("  %s" % line.__str__())

    def write_error_to_file(self, filename):
        errfile = open(filename, "wb")
        json.dump(self.json_repr(), errfile, indent=2)
        errfile.close()

    def append_to_context_bottom(self, msg):
        """Add a message to the bottom (most nested part) of the context stack.
        """
        if self.context != None:
            self.context.append(msg)
        else:
            self.context = [msg]

    def append_to_context_top(self, msg):
        """Add a message to the top of the context stack.
        """
        if self.context != None:
            self.context.insert(0, msg)
        else:
            self.context = [msg]


def convert_exc_to_user_error(exc_info, error_info, msg_args=None, nested_exc_info=None,
                              user_error_class=UserError):
    """Create a user error from an exception. exc_info is the exception info
    array returned from sys.exc_info(). The user message, error code, etc
    are taken from error_info.
    The exception type and value are stored in the developer message and the
    stack traceback used to create a context stack. If a nested exception's information
    is provided through nested_exc_info, this is addeded to the end of the context
    list.

    Here is an example of using this function.

    try:
        call_something_that_can_throw_an_exception()
    except UserError:
         # if this call can throw a user error,
         # let it propagage up
        raise
    except:
        exc_info = sys.exc_info()
        raise convert_exc_to_user_error(exc_info, errors[ERR_WSGI_SCRIPT],
                                        msg_args={'script':config_mod_wsgi_file})
    
    """
    (exc_class, exc_val, exc_tb) = exc_info
    exc_name = exc_class.__name__
    if nested_exc_info != None:
        context = traceback.extract_tb(exc_tb) + traceback.extract_tb(nested_exc_info[2])
    else:
        context = traceback.extract_tb(exc_tb)
    return user_error_class(error_info, msg_args,
                            developer_msg="%s: %s" % (exc_name, exc_val.__str__()),
                            context=context)

class UserErrorParseExc(Exception):
    def __init__(self, msg, json_repr):
        super(UserErrorParseExc, self).__init__(msg)
        self.json_repr = json_repr


def parse_user_error(json_repr, component=None):
    if not isinstance(json_repr, dict):
        raise UserErrorParseExc("Unable to parse user error json representation: object not a dict",
                                json_repr)
    required_keys = ['usererror', 'logarea', 'errorcode']
    for key in required_keys:
        if not json_repr.has_key(key):
            raise UserErrorParseExc("Unable to parse user error json representation: missing required key '%s'" % key, json_repr)
    if json_repr.has_key("context"):
        context = json_repr['context']
    else:
        context = None
    if json_repr.has_key("deverror"):
        developer_msg = json_repr['deverror']
    else:
        developer_msg = None
    if not component:
        if not json_repr.has_key("component"):
            raise UserErrorParseExc("Unable to parse user error json representation: missing required key 'component'")
        component = json_repr['component']
    err_info = ErrorInfo(component,
                         json_repr['logarea'],
                         json_repr['errorcode'],
                         json_repr['usererror'])
    return UserError(err_info, context=context,
                     developer_msg=developer_msg)
                         

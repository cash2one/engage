"""Tracking and representation of settings validation results"""

import sys
import os.path
import json
import traceback

try:
    from engage_django_sdk.version import VERSION
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from engage_django_sdk.version import VERSION

from errors import ValidationError

# Return codes
SUCCESS_RC                   = 0
SETTINGS_VALIDATION_ERROR_RC = 1
ARG_PARSE_ERROR_RC           = 2
ARCHIVE_VALIDATION_ERROR_RC  = 3
UNEXPECTED_EXC_RC            = 4
INTERNAL_ERROR_RC            = 5

_rc_descriptions = {
    SUCCESS_RC: "Success",
    SETTINGS_VALIDATION_ERROR_RC: "Settings Validation Errors",
    ARG_PARSE_ERROR_RC: "Command Line Agument Error",
    ARCHIVE_VALIDATION_ERROR_RC: "Archive Validation Error",
    UNEXPECTED_EXC_RC: "Unexpected Exception",
    INTERNAL_ERROR_RC: "InternalError"
}

class ResultsBase(object):
    def __init__(self, version=VERSION, error_messages=None, warning_messages=None,
                 exception=None, product=None, product_version=None,
                 python_path_subdirectory=None, installed_apps=None,
                 fixtures=None, migration_apps=None, components=None,
                 post_install_commands=None, media_root_subdir=None,
                 media_url_path=None, static_root_subdir=None, static_url_path=None):
        self.version = version
        if error_messages:
            self.error_messages = error_messages
        else:
            self.error_messages = []
        if warning_messages:
            self.warning_messages = warning_messages
        else:
            self.warning_messages = []
        self.exception = exception
        self.product = product
        self.product_version = product_version
        self.python_path_subdirectory = python_path_subdirectory
        self.installed_apps = installed_apps
        self.fixtures = fixtures
        self.migration_apps = migration_apps
        self.components = components
        self.post_install_commands = post_install_commands
        self.media_root_subdir = media_root_subdir
        self.media_url_path = media_url_path
        self.static_root_subdir = static_root_subdir
        self.static_url_path = static_url_path

    def get_return_code(self):
        raise Exception("%s does not implement get_return_code()!" % self.__type__.__name__)

    def get_return_code_desc(self):
        if _rc_descriptions.has_key(self.get_return_code()):
            return  _rc_descriptions[self.get_return_code()]
        else:
            return "Unexpected Return Code"
        
    def to_json(self):
        js = { u"validator_version":self.version,
               u"return_code": self.get_return_code(),
               u"return_code_desc": self.get_return_code_desc(),
               u"error_messages": self.error_messages,
               u"warning_messages": self.warning_messages,
               u"exception": self.exception,
               u"product": self.product,
               u"product_version": self.product_version,
               u"python_path_subdirectory":self.python_path_subdirectory,
               u"installed_apps": self.installed_apps,
               u"fixtures": self.fixtures,
               u"migration_apps":self.migration_apps,
               u"components":self.components,
               u"post_install_commands":self.post_install_commands,
               u"media_root_subdir":self.media_root_subdir,
               u"media_url_path":self.media_url_path,
               u"static_root_subdir":self.static_root_subdir,
               u"static_url_path":self.static_url_path}
        return js


class FatalErrorResults(ResultsBase):
    def __init__(self, return_code, exc_type, exc_value, exc_traceback):
        if isinstance(exc_value, ValidationError):
            msg = "%s: %s" % (exc_type.__name__, str(exc_value))
        else:
            msg = "Unexpected exception: %s(%s)" % (exc_type.__name__, str(exc_value))
        ResultsBase.__init__(self, error_messages=[msg],
                             exception=traceback.format_exception(exc_type,
                                                                  exc_value,
                                                                  exc_traceback))
        self.return_code = return_code

    def get_return_code(self):
        return self.return_code
                             

class ParsedJsonResults(ResultsBase):
    """This object represents the results file after it has been
    read back in and parsed. Most of the work is done in the __init__
    function which converts from a dictionary to object fields.
    """
    def __init__(self, json_obj):
        try:
            if not type(json_obj)==dict:
                raise Exception("Invalid content in results file, data was %s" %
                                json_obj.__repr__())
            props = [u"return_code", u"return_code_desc",
                     u"validator_version", u"error_messages",
                     u"warning_messages", u"exception",
                     u"product", u"product_version",
                     u"python_path_subdirectory",
                     u"installed_apps",
                     u"fixtures",
                     u"migration_apps",
                     u"components",
                     u"post_install_commands",
                     u"media_root_subdir",
                     u"media_url_path",
                     u"static_root_subdir",
                     u"static_url_path"]
            for prop in props:
                if not json_obj.has_key(prop):
                    raise Exception("Invalid results file, missing property %s" %
                                    prop)
            ResultsBase.__init__(self,
                                 version=json_obj[u"validator_version"],
                                 error_messages=json_obj[u"error_messages"],
                                 warning_messages=json_obj[u"warning_messages"],
                                 exception=json_obj[u"exception"],
                                 product=json_obj[u"product"],
                                 product_version=json_obj[u"product_version"],
                                 python_path_subdirectory=json_obj[u"python_path_subdirectory"],
                                 installed_apps=json_obj[u"installed_apps"],
                                 fixtures=json_obj[u"fixtures"],
                                 migration_apps=json_obj[u"migration_apps"],
                                 components=json_obj[u"components"],
                                 post_install_commands=json_obj[u"post_install_commands"],
                                 media_root_subdir=json_obj[u"media_root_subdir"],
                                 media_url_path=json_obj[u"media_url_path"],
                                 static_root_subdir=json_obj[u"static_root_subdir"],
                                 static_url_path=json_obj[u"static_url_path"])
            self.return_code = json_obj[u"return_code"]
            self.return_code_desc = json_obj[u"return_code_desc"]
        except Exception, v:
            ResultsBase.__init__(self, "Unknown", [ v ], [])
            self.return_code = INTERNAL_ERROR_RC
            self.return_code_desc = _rc_descriptions[INTERNAL_ERROR_RC]

    def get_return_code(self):
        return self.return_code
    
    def run_was_successful(self):
        return self.return_code == SUCCESS_RC
    
    def get_return_code_desc(self):
        return self.return_code_desc

    def get_validator_version(self):
        return self.validator_version

    def has_error_messages(self):
        return len(self.error_messages) > 0

    def get_error_messages(self):
        return self.error_messages

    def has_warning_messages(self):
        return len(self.warning_messages) > 0

    def get_warning_messages(self):
        return self.warning_messages

    def all_checks_passed(self):
        return len(self.warning_messages)==0 and \
               len(self.error_messages)==0
    
    def print_final_status_message(self, logger):
        if self.all_checks_passed():
            logger.info(">> All settings checks passed.")
        else:
            logger.error(">> %d errors, %d warnings in settings validation." %
                         (len(self.error_messages),
                          len(self.warning_messages)))

    def format_messages(self):
        s = ""
        if self.has_error_messages():
            s += "Errors:\n"
            for i in range(1, len(self.error_messages)+1):
                s += "  [%02d] %s\n" % (i, self.error_messages[i-1])
        else:
            s += "Errors: None\n"
        if self.has_warning_messages():
            s += "Warnings:\n"
            for i in range(1, len(self.warning_messages)+1):
                s += "  [%02d] %s\n" % (i, self.warning_messages[i-1])
        else:
            s += "Warnings: None\n"
        return s

    def has_exception(self):
        return self.exception


class SettingValidationResults(ResultsBase):
    """This class is used for tracking the progress of the settings validation tests.
    """
    def __init__(self, version, logger):
        ResultsBase.__init__(self, version)
        self.logger = logger
        self.errors = 0
        self.warnings = 0

    def error(self, msg):
        self.errors += 1
        self.error_messages.append(msg)
        self.logger.error("ERROR: " + msg + "\n")

    def warning(self, msg):
        self.warnings += 1
        self.warning_messages.append(msg)
        self.logger.warn("WARNING: " + msg + "\n")

    def has_errors(self):
        return self.errors > 0

    def has_warnings(self):
        return self.warnings > 0

    def all_checks_passed(self):
        return (self.errors == 0) and (self.warnings == 0)

    def print_final_status_message(self, logger):
        if self.all_checks_passed():
            self.logger.info(">> All settings checks passed.")
        else:
            self.logger.error(">> %d errors, %d warnings in settings validation." %
                              (self.errors, self.warnings))
        
    def get_return_code(self):
        if self.has_errors(): return SETTINGS_VALIDATION_ERROR_RC
        else: return SUCCESS_RC # if we get warnings but not errors, still return ok

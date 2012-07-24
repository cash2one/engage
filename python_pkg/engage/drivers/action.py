"""
Library of actions for use in resource managers.

Goals
-----
The goal of this library is to:
 * Provide management of the config properties and other context needed
   by most installation and service management actions.
 * Provide standardized error handling and logging.
 * Make it easy to compose sequences of actions.
 * Make it easy to test and debug action sequences.

Object Types
------------
There are two main object types in this framework:
 * The context object (an instance of the Context class) provides the
   shared global state needed by the actions running under a driver. This
   is similar to the $_ object in jQuery.
 * Actions do the actual work. Action classes are not instantiated or run
   directly. Instead, the context object provides methods to run the actions
   (r() and rv()). This allows the context object to call either run() or dry_run()
   based on whether context was created with dry_run set or not. In addition,
   the r() and rv() methods handle logging and errors.

There are two categories of actions:
 1. Subclasses from the Action class are executed for effect and do not return
    a value.
 2. Subclasses from the ValueAction class return a value. They may have side-effects.
    Ideally they should be itempotent.


The Context Object
------------------
The context object should be created in the constructor of your resource manager.
Usually, this is done in an separate function (e.g. make_context) so that it can be
testing outside of the resource manager.

The Context constructor takes the following parameters:

 resource_config_props
   this is the json of the resource instance

 logger
   the logger object for the driver (obtained by engage.utils.log_setup.setup_engage_logger)

 filepath
   the __file__ variable

 sudo_password_fn
   a function which returns the sudo password. You need this if you
   are going to call any of the sudo\_ actions. Typically, this
   function is obtained by subclassing from
   password_repo_mixin.PasswordRepoMixin.

 dry_run
  if set to True, the dry_run method will be called for all actions.
  This should have the effect of logging what would happen if you ran
  the install, without actually making any of the external changes.

Context object fields
~~~~~~~~~~~~~~~~~~~~~
The context object has the following public fields:

  props
    this field provides a representation of the resource instance JSON
    as a python object. For example, if the JSON contains
    {"input_ports":{"host":{"hostname":"localhost"}}}, you can access
    the hostname property as ctx.props.input_ports.host.hostname

  logger
    the logger. This is used by actions

  dry_run
    True if we are running in dry-run mode

  substitutions
    this is a map from qualified property names in the JSON resource
    instance to string values. For example, given the JSON example
    above, we would include the mapping "input_ports.host.hostname" =>
    "localhost".  This map is used for template substitutions (see the
    template and get_template_subst actions).

Context object methods
~~~~~~~~~~~~~~~~~~~~~~
The context object has the following methods:

  add()
    Add a new key, value entry to the props and substitutions fields.
    This key can be a qualified name (e.g.
    "input_ports.host.hostname"), The add() method is useful when
    computing properties (e.g. via os.path.join).

  checkp()
    Check that the specified qualified property name is present in the
    ctx.props field.

  check_port()
    Check that the specified properties are present in the specified
    port.

  r()
    Run an action.

  rv()
    Run a value action.

  poll_rv()
    Run a value action multiple times until either a specified
    result is returned or a timeout occurs.

  check_poll()
    Run a value action until a predicate is true and return the last
    result. If timeout occurs, raise an error.

  _get_sudo_password
    This method is used by actions to get the super user password.


Action Naming Conventions
-------------------------
We use the following naming conventions:

  "get\_"
    is used for value actions.

  "check\_"
    is used for validation actions that subclass from Action. They throw a
    user error if the check fails. When run in dry-run mode, they log a warning if
    the check fails.

  "ensure\_"
    is used for actions that have an effect, but are itempotent. For example,
    ensure_dir_exists will check for the presence of a directory and create it if it
    does not already exist.

  "sudo\_"
    is used for actions that are run as the super user.


Defining Actions
----------------
To define a new action, subclass from Action or Value action as appropriate, set a
class field called NAME to the action's name, and override the run() method. You can
also override the dry_run() method as well if there is some checking you want to do in
dry-run mode.

Defining an action involves a bit of boilerplate code. If you do not have any code
that should be executed in dry_run mode, you can use the @make_action and
@make_value action decorators to create action classes directly from a function,
avoiding the boilerplate.


Shorthand
---------
Dereferencing the methods and properties of the context can be tedious in driver code.
By convention, we use the following shorter variables where appropriate::

  r = self.ctx.r
  rv = self.ctx.rv
  poll_rv = self.ctx.poll_rv
  p = self.ctx.props

  These should be defined and used at the method level.


Example Code
------------
Here is some example code that excercises the action api in the REPL::

    from action import *
    # setup the context. At a minimum we need the resource instance
    # properties, a logger and the name of the current file (usually
    # obtained via __file__).
    rc = {"id":"apache2", "key":{"name":"apache2", "version":"2.2"},
          "config_port": { "prop1":"/foo/bar", "prop2":34 }}
    from engage.utils.log_setup import logger_for_repl
    logger = logger_for_repl()
    ctx = Context(rc, logger, "./action.py")

    # properties are accessible via the props member of the context
    print ctx.props.config_port.prop1
    
    import os.path
    # add a computed property
    ctx.add("prop3", os.path.join(ctx.props.config_port.prop1, "test"))
    print ctx.props.prop3

    # run a value action which instantiates the test.txt template file
    ctx.rv(substitute, "test.txt")


Actions
-------
The following actions are defined by this module:

 * check_dir_exists <dir-path>
 * check_file_exists <file-path>
 * check_installable_to_dir <install-dir>
 * check_port_available <hostname> <port>
 * copy_file <src> <dest>
 * create_engage_dist <target_path>
 * ensure_dir_exists <dir-path>
 * ensure_shared_perms<path> <group_name> {writable_to_group=False}
 * sudo_ensure_shared_perms<path> <group_name> {writable_to_group=False}
 * extract_package_as_dir <package> <desired-install-path>
 * instantiate_template_str <src_string> <target_path>
 * run_program <program_and_args> {cwd=None} {env_mapping=None} {input=None} {hide_input=False} {hide_command=False}
 * set_file_mode_bits <path> <mode_bits>
 * mkdir <dir_path>
 * move_old_file_version <file_path> {backup_name=None} {leave_old_backup_file=False}
 * start_server <cmd_and_args> <log_file> <pid_file> {cwd="/"} {environment={}} {timeout_tries=10} {time_between_tries=2.0}
 * stop_server <pid_file> {timeout_tries=10} {force_stop=False}
 * subst_in_file <filename> <pattern_list> {subst_in_place=False}
 * subst_in_file_and_check_count <filename> <pattern_list> <num_expected_changes> {subst_in_place=False}
 * sudo_add_config_file_line <config-file> <line>
 * sudo_copy <copy_args>
 * sudo_mkdir <path> {create_intermediate_dirs=False}
 * sudo_run_program <program_and_args> {cwd=None}
 * sudo_start_server <cmd_and_args> <log_file> {cwd=None} {environment={}}
 * sudo_set_file_permissions <path> <user-id> <group-id> <mode-bits>
 * sudo_set_file_perms_by_name <path> <mode_bits> {user_name=effective_user} {group_name=effective_group}
 * template <src-data-file> <target-path>


Value Actions
-------------
The following value actions are defined by this module:
 * get_server_status <pid_file> {remove_pidfile_if_dead_proc=False}
 * get_template_subst <src_data_file>
 * wait_for_file <file_path> <timeout_tries> <time_between_tries>
 * sudo_cat_file <path>
 * sudo_run_program_and_scan_results <program_and_args> <re_map> {env=None} {cwd=None} {log_output=False}


Classes and functions
----------------------
We now look at the individual classes and functions defined this module.
"""
import sys
import os
import os.path
import string
import time
import shutil
import unittest
import pwd
import grp

try:
    import engage.utils
except:
    sys.exc_clear()
    sys.path.append(os.path.abspath(
        os.path.expanduser(os.path.join(os.path.dirname(__file__), "../.."))))

import engage.utils.file as fileutils
import engage.utils.process as procutils
import engage.utils.regexp as regexp
import engage.utils.path as pathutils
import engage.utils.cfg_file as cfg_file
import engage.utils.http as httputils
from engage.utils.user_error import UserError, EngageErrInf, convert_exc_to_user_error
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_DIR_NOT_FOUND            =  1
ERR_FILE_NOT_FOUND           =  2
ERR_TMPL_KEY                 =  3
ERR_UNEXPECTED_EXC_IN_ACTION =  4
ERR_PROP_NOT_FOUND           =  5
ERR_PROP_TYPE_NOT_STR        =  6
ERR_PROP_TYPE_NOMATCH        =  7
ERR_MISSING_ID_PROP          =  8
ERR_INSTDIR_NOT_WRITABLE     =  9
ERR_INSTDIR_ALREADY_EXISTS   = 10
ERR_NO_SUDO_PW               = 11
ERR_TMPLSTR_KEY              = 12
ERR_CREATE_DIST_FAILED       = 13
ERR_CHECK_POLL_TIMEOUT       = 14
ERR_SUBPROCESS_RC            = 15
ERR_PORT_TAKEN               = 16
ERR_ACTION_POLL_TIMEOUT      = 17
ERR_SERVER_STOP_TIMEOUT      = 18
ERR_WRONG_SUBST_COUNT        = 19


define_error(ERR_DIR_NOT_FOUND,
             _("Required directory '%(dirpath)s' not found for resource %(resid)s"))
define_error(ERR_FILE_NOT_FOUND,
             _("Required file '%(filepath)s' not found for resource %(resid)s"))
define_error(ERR_TMPL_KEY,
             _("Error in resource '%(resid)s' action '%(action)s', Template file '%(file)s' has key '%(key)s', which was not in substitution map"))
define_error(ERR_UNEXPECTED_EXC_IN_ACTION,
             _("Unexpected exception '%(exc)s' in resource '%(id)s' action: %(action)s"))
define_error(ERR_PROP_NOT_FOUND,
             _("Resource '%(id)s' missing required property '%(name)s'"))
define_error(ERR_PROP_TYPE_NOT_STR,
             _("Property '%(name)s' of resource '%(id)s' has wrong type: expecting str or unicode, got '%(type)s'"))
define_error(ERR_PROP_TYPE_NOMATCH,
             _("Property '%(name)s' of resource '%(id)s' has wrong type: expecting '%(exptype)s', got '%(type)s'"))
define_error(ERR_MISSING_ID_PROP,
             _("Resource context missing required property 'id'"))
define_error(ERR_INSTDIR_NOT_WRITABLE,
             _("Installation parent directory '%(dir)s' is not writable for resource '%(id)s'"))
define_error(ERR_INSTDIR_ALREADY_EXISTS,
             _("Installation directory '%(dir)s' already exists for resource '%(id)s'"))
define_error(ERR_NO_SUDO_PW,
             _("Sudo password is required by resource %(id) action %(action), but none provided"))
define_error(ERR_TMPLSTR_KEY,
             _("Error in resource '%(resid)s' action '%(action)s', Template string has key '%s(key)s' which was not in substitution map. Target file was %(file)s"))
define_error(ERR_CREATE_DIST_FAILED,
             _("Error in creating engage distribution from deployment home in resource %(id)s. Target path for distribution was '%(file)s'"))
define_error(ERR_CHECK_POLL_TIMEOUT,
             _("Action %(action)s timed out after %(time).1f in resource %(id)s"))
define_error(ERR_SUBPROCESS_RC,
             _("Subprocess execution filed in resource %(id)s, command was '%(cmd)s'"))
define_error(ERR_PORT_TAKEN,
             _("Pre-install check failed for resource %(id)s: something is already running on port %(port)d."))
define_error(ERR_ACTION_POLL_TIMEOUT,
             _("Action %(action)s timed out waiting for %(description)s after %(time).1f in resource %(id)s"))
define_error(ERR_SERVER_STOP_TIMEOUT,
             _("Action %(action)s timed out after %(timeout)d seconds waiting for pid %(pid)d to stop in resource %(id)s"))
define_error(ERR_WRONG_SUBST_COUNT,
             _("Incorrect number of substitutions for file %(file)s: expecting %(exp)d, actual was %(actual)d in resource %(id)s"))


def _format_action_args(action_name, *args, **kwargs):
    s = action_name
    for arg in args:
        s += " %s" % str(arg)
    for (k ,v) in kwargs.items():
        s += " %s=%s" % (k, str(v))
    return s


class Action(object):
    """Actions are run for their side effects.
    """
    def __init__(self, ctx):
        self.ctx = ctx

    def run(self, *args, **kwargs):
        """This method executes the action. Will be overridden in
        subclasses to take the specific arguments needed by the action.
        """
        pass

    def dry_run(self, *args, **kwargs):
        """Dry run version of action. By default does nothing. Should still
        be overriden in subclasses to take the specific arguments needed by the
        action.
        """
        pass

    def format_action_args(self, *args, **kwargs):
        """Return a string representation of the action name and
        arguments passed to this action. This is used in ctx.r() for logging.
        Usually, this version is sufficient. Potential reasons
        to override this include eliding passwords or suppressing the
        logging of really big data structures.
        """
        return _format_action_args(self.NAME, *args, **kwargs)


class SudoAction(Action):
    """Subclass of action that includes sudo_run()
    """
    def __init__(self, ctx):
        super(SudoAction, self).__init__(ctx)

    def sudo_run(self, *args, **kwargs):
        """Execute an action under sudo. This method should accept the same
        arguments as the run() method. The implementer of sudo_run()
        is responsible for making the appropriate sudo calls
        (e.g. using procutils.sudo_run_program()). The calling context
        object will ensure that 1) this method is only called if sudo access is
        required (not running as root) and 2) ensure that
        ctx._get_sudo_password() returns a value.
        """
        pass


class ValueAction(object):
    """Value actions return a value
    """
    def __init__(self, ctx):
        self.ctx = ctx

    def run(self, *args, **kwargs):
        """This method executes the action. Will be overridden in
        subclasses to take the specific arguments needed by the action, run
        the action, and return a value.
        """
        pass

    def dry_run(self, *args, **kwargs):
        """Dry run version of action. By default does nothing. Should still
        be overriden in subclasses to take the specific arguments needed by the
        action. Return value may be None - return values are not guaranteed
        by dry run actions.
        """
        pass

    def format_action_args(self, *args, **kwargs):
        """Return a string representation of the action name and
        arguments passed to this action. This is used in ctx.rv() for logging.
        Usually, this version is sufficient. Potential reasons
        to override this include eliding passwords or suppressing the
        logging of really big data structures.
        """
        return _format_action_args(self.NAME, *args, **kwargs)

    def format_action_result(self, result):
        """Return a string representation of the action name and result value.
        This is used in ctx.rv() for logging.
        Usually, this version is sufficient. It only returns the actual value
        if it is something simple, like a bool or int or None. Otherwise,
        it just returns the type of the result.
        """
        if not (isinstance(result, bool) or isinstance(result, int) or result==None or result==''):
            result = "instance of %s" % type(result).__name__
        return "%s => %s" % (self.NAME, result)


class SudoValueAction(ValueAction):
    """Subclass of value action that includes sudo_run()
    """
    def __init__(self, ctx):
        super(SudoValueAction, self).__init__(ctx)

    def sudo_run(self, *args, **kwargs):
        """Execute a value action under sudo. This method should accept the same
        arguments as the run() method. The implementer of sudo_run()
        is responsible for making the appropriate sudo calls
        (e.g. using procutils.sudo_run_program()). The calling context
        object will ensure that 1) this method is only called if sudo access is
        required (not running as root) and 2) ensure that
        ctx._get_sudo_password() returns a value.
        """
        pass


class _Config(object):
    def __init__(self, props, _qualified_name=None):
        self.__dict__["_props"] = {}
        self.__dict__["_qualified_name"] = _qualified_name
        for (prop_name, prop_val) in props.items():
            self._props[prop_name] = self._wrap_child_val(prop_name, prop_val)

    def _get_child_prop_qname(self, name, list_idx=None):
        if list_idx:
            name = "%s[%d]" % (name, list_idx)
        if self._qualified_name:
            return self._qualified_name + "." + name
        else:
            return name

    def _wrap_child_val(self, prop_name, prop_val):
        if isinstance(prop_val, dict):
            return _Config(prop_val, self._get_child_prop_qname(prop_name))
        elif isinstance(prop_val, list):
            child_list = []
            for i in range(len(prop_val)):
                child_list.append(self._wrap_child_val(prop_name + "[%d]" % i,
                                                       prop_val[i]))
            return child_list
        else:
            return prop_val
        
    def _add(self, name, value):
        name_comps = name.split(".")
        key = name_comps[0]
        rest = name_comps[1:]
        if len(rest)==0:
            if self._props.has_key(key):
                raise AttributeError, \
                      "Cannot overwrite attribute %s" % \
                      self._get_child_prop_qname(key)
            else:
                self._props[name] = value
        else:
            if self._props.has_key(key):
                nested_val = self._props[key]
                if isinstance(nested_val, _Config):
                    nested_val._add(".".join(rest), value)
                else:
                    raise AttributeError, \
                      "Cannot overwrite attribute %s" % \
                      self._get_child_prop_qname(key)
            else:
                new_child = _Config({}, self._get_child_prop_qname(key))
                self._props[key] = new_child
                new_child._add(".".join(rest), value)

    def _get(self, qualified_name):
        name_comps = qualified_name.split(".")
        key = name_comps[0]
        rest = name_comps[1:]
        if len(rest)==0 and self._props.has_key(key):
            return self._props[key]
        elif self._props.has_key(key) and isinstance(self._props[key], _Config):
            return self._props[key]._get(".".join(rest))
        else:
            raise AttributeError, \
                  "Property '%s' not found" % \
                  self._get_child_prop_qname(key)
                
    def _make_flattened_map(self, map):
        for (prop_name, prop_val) in self._props.items():
            key = self._get_child_prop_qname(prop_name)
            if isinstance(prop_val, _Config):
                prop_val._make_flattened_map(map)
            elif isinstance(prop_val, list):
                # the flattened map notation does not really work
                # with lists. We just add the string representation of
                # the list
                map[key] = prop_val.__repr__()
            else:
                map[key] = str(prop_val)
    
    def __getattr__(self, name):
        if self._props.has_key(name): return self._props[name]
        else: raise AttributeError, "%s not an attribute" % name

    def __setattr__(self, name, value):
        raise AttributeError, \
            "Error in setting attribute '%s': Configuration objects are read-only"

    def __str__(self):
        if self._qualified_name:
            return "<Resource Config Props %s>" % self._qualified_name
        else:
            return "<Resource Config Props>"

    def __repr__(self):
        return self._props.__repr__()


class Context(object):
    """This is the main state object used by actions. It should be
    created by the driver using the resource metadata.
    """
    def __init__(self, resource_config_props, logger, filepath,
                 sudo_password_fn=None,
                 dry_run=False):
        self.props = _Config(resource_config_props)
        self.logger = logger
        # we have an extra log level called "action" which is inbetween
        # info and debug. If it isn't present, just map to debug.
        if not hasattr(self.logger, "action"):
            self.logger.action = self.logger.debug
        self.filepath = os.path.abspath(os.path.expanduser(filepath))
        self.sudo_password_fn = sudo_password_fn
        self.dry_run = dry_run
        self.substitutions = {}
        self.props._make_flattened_map(self.substitutions)
        if not self.substitutions.has_key("id"):
            raise UserError(errors[ERR_MISSING_ID_PROP])

    def add(self, key, value):
        """Add a property and value to the existing metadata. Useful for
        dynamically computed properties. Property names may be of the form
        "x.y.z".
        """
        if self.substitutions.has_key(key):
            raise AttributeError, \
                  "Context already has a value for key %s" % key
        self.props._add(key, value)
        if isinstance(value, _Config) or isinstance(value, dict) or \
           isinstance(value, list):
            self.substitutions[key] = value.__repr__()
        else:
            self.substitutions[key] = str(value)

    def checkp(self, qualified_prop_name, typ=None):
        """Check that specified property is present in the props field.

        If the property is not present, raise an error. The type of
        the property is also checked against the typ parameter (which should
        be a python type object that can be compared using isinstance(). If the
        type parameter is not specified, we assume a string of either type str
        or unicode.

        Returns a context instance.
        """
        if not self.substitutions.has_key(qualified_prop_name):
            raise UserError(errors[ERR_PROP_NOT_FOUND],
                            msg_args={"id": self.props.id,
                                      "name":qualified_prop_name})
        name_comps = qualified_prop_name.split(".")
        v = self.props._get(qualified_prop_name)
        if typ==None and not (isinstance(v, str) or isinstance(v, unicode)):
            raise UserError(errors[ERR_PROP_TYPE_NOT_STR],
                            msg_args={"id":self.props.id,
                                      "name":qualified_prop_name,
                                      "value":v.__repr__(),
                                      "type":type(v).__name__})
        elif typ!=None and not isinstance(v, typ):
            raise UserError(errors[ERR_PROP_TYPE_NOMATCH],
                            msg_args={"id":self.props.id,
                                      "name":qualified_prop_name,
                                      "value":v.__repr__(),
                                      "type":type(v).__name__,
                                      "exptype":typ.__name__})
        return self

    def check_port(self, port_name, **kwargs):
        """Check the properties for a port.

        port_name
          qualified name of a port (e.g. 'config_port' or 'input_ports.apache')
        kwargs
          properties defined for the port. keyword is the prop name,
          value is the type. If the type is str or unicode we allow either one.
        """
        for (prop, typ) in kwargs.items():
            if typ==str or typ==unicode:
                self.checkp(port_name + "." + prop)
            else:
                self.checkp(port_name + "." + prop, typ=typ)
        return self

    def r(self, action, *args, **kwargs):
        """Run the specified Action, providing it the given arguments.
        """
        a = action(self)
        assert isinstance(a, Action), \
               "r() passed an action of type %s, not an instance of Action" % type(a).__name__
        action_and_args = a.format_action_args(*args, **kwargs)
        self.logger.action(action_and_args)
        try:
            if not self.dry_run:
                a.run(*args, **kwargs)
            else:
                a.dry_run(*args, **kwargs)
        except UserError:
            raise
        except Exception, e:
            exc_info = sys.exc_info()
            self.logger.exception("Exception executing action %s: %s" %
                                  (action_and_args, e.__repr__()))
            raise convert_exc_to_user_error(sys.exc_info(), errors[ERR_UNEXPECTED_EXC_IN_ACTION],
                                            msg_args={"exc":e.__repr__(), "action":action_and_args,
                                                      "id":self.props.id})
        return self

    def r_su(self, sudo_action, *args, **kwargs):
        """Run the specified SudoAction, providing it the given arguments. If
        running as root, calls the run() method. Otherwise, calls the sudo_run()
        method.
        """
        a = sudo_action(self)
        assert isinstance(a, SudoAction), \
               "r() passed an action of type %s, not an instance of SudoAction"\
               % type(a).__name__
        action_and_args = a.format_action_args(*args, **kwargs)
        self.logger.action(action_and_args)
        try:
            if procutils.SUDO_PASSWORD_REQUIRED!=None:
                if procutils.SUDO_PASSWORD_REQUIRED==True and \
                       (not self.sudo_password_fn()):
                    raise UserError(errors[ERR_NO_SUDO_PW],
                                    msg_args={"id":self.props.id,
                                              "action":a.name})
                if not self.dry_run:
                    a.sudo_run(*args, **kwargs)
                else:
                    a.dry_run(*args, **kwargs)
            else: # running as root, no need to sudo
                if not self.dry_run:
                    a.run(*args, **kwargs)
                else:
                    a.dry_run(*args, **kwargs)
        except UserError:
            raise
        except Exception, e:
            exc_info = sys.exc_info()
            self.logger.exception("Exception executing action %s: %s" %
                                  (action_and_args, e.__repr__()))
            raise convert_exc_to_user_error(sys.exc_info(), errors[ERR_UNEXPECTED_EXC_IN_ACTION],
                                            msg_args={"exc":e.__repr__(), "action":action_and_args,
                                                      "id":self.props.id})
        return self

    def rv(self, value_action, *args, **kwargs):
        """Run the specified ValueAction, providing it the given arguments.
        """
        a = value_action(self)
        assert isinstance(a, ValueAction), \
               "rv() passed an action of type %s, not an instance of ValueAction" % type(a).__name__
        action_and_args = a.format_action_args(*args, **kwargs)
        self.logger.action(action_and_args)
        try:
            if not self.dry_run:
                result = a.run(*args, **kwargs)
                self.logger.debug(a.format_action_result(result))
                return result
            else:
                return a.dry_run(*args, **kwargs)
        except UserError:
            raise
        except Exception, e:
            exc_info = sys.exc_info()
            self.logger.exception("Exception executing action %s: %s" %
                                  (action_and_args, e.__repr__()))
            raise convert_exc_to_user_error(sys.exc_info(), errors[ERR_UNEXPECTED_EXC_IN_ACTION],
                                            msg_args={"exc":e.__repr__(), "action":action_and_args,
                                                      "id":self.props.id})

    def rv_su(self, sudo_value_action, *args, **kwargs):
        """Run the specified ValueAction as the super user, providing it the
        given arguments. If running as root, calls the run() method. Otherwise,
        calls the sudo_run() method.
        """
        a = sudo_value_action(self)
        assert isinstance(a, SudoValueAction), \
            "rv() passed an action of type %s, not an instance of SudoValueAction"\
            % type(a).__name__
        action_and_args = a.format_action_args(*args, **kwargs)
        self.logger.action(action_and_args)
        try:
            if procutils.SUDO_PASSWORD_REQUIRED!=None:
                if procutils.SUDO_PASSWORD_REQUIRED==True and \
                       (not self.sudo_password_fn()):
                    raise UserError(errors[ERR_NO_SUDO_PW],
                                    msg_args={"id":self.props.id,
                                              "action":a.name})
                if not self.dry_run:
                    result = a.sudo_run(*args, **kwargs)
                    self.logger.debug(a.format_action_result(result))
                    return result
                else:
                    return a.dry_run(*args, **kwargs)
            else: # running as root
                if not self.dry_run:
                    result = a.run(*args, **kwargs)
                    self.logger.debug(a.format_action_result(result))
                    return result
                else:
                    return a.dry_run(*args, **kwargs)
        except UserError:
            raise
        except Exception, e:
            exc_info = sys.exc_info()
            self.logger.exception("Exception executing action %s: %s" %
                                  (action_and_args, e.__repr__()))
            raise convert_exc_to_user_error(sys.exc_info(), errors[ERR_UNEXPECTED_EXC_IN_ACTION],
                                            msg_args={"exc":e.__repr__(), "action":action_and_args,
                                                      "id":self.props.id})

    def poll_rv(self, timeout_tries, time_between_tries, stop_pred, value_action, *args, **kwargs):
        """Method which runs a value action multiple times until it either returns true or times out.
        stop_pred is a function to convert the result of the value action into a boolean signifying True
        if the polling should stop, False otherwise.
        """
        self.logger.debug("Running poll on action %s, with %d timeout tries and %s seconds between tries" %
                          (value_action.NAME, timeout_tries, time_between_tries))
        if self.dry_run:
            # if dry_run, then run the action once and return
            self.rv(value_action, *args, **kwargs)
            return None

        for i in range(timeout_tries):
            if stop_pred(self.rv(value_action, *args, **kwargs)):
                return True
            else:
                if i != (timeout_tries-1): time.sleep(time_between_tries)
        self.logger.debug("Poll on action %s timed out after %d tries" % (value_action.NAME, timeout_tries))
        return False

    def check_poll(self, timeout_tries, time_between_tries, stop_pred, value_action, *args, **kwargs):
        """Method which runs a value action multiple times until it a predicate is true. It
        returns the final value of the action. If the specified number of tries is reached
        without the predicate turning true, a user error is thrown.
        """
        self.logger.debug("Running poll on action %s, with %d timeout tries and %s seconds between tries" %
                          (value_action.NAME, timeout_tries, time_between_tries))
        if self.dry_run:
            # if dry_run, then run the action once and return
            self.rv(value_action, *args, **kwargs)
            return None

        for i in range(timeout_tries):
            v = self.rv(value_action, *args, **kwargs)
            if stop_pred(v):
                return v
            else:
                if i != (timeout_tries-1): time.sleep(time_between_tries)
        raise UserError(errors[ERR_CHECK_POLL_TIMEOUT],
                        msg_args={"id":self.props.id,
                                  "action":value_action.NAME,
                                  "time":timeout_tries*time_between_tries})

    def _get_sudo_password(self, action):
        """Method for actions to get the superuser password.
        """
        if procutils.SUDO_PASSWORD_REQUIRED==None or \
           procutils.SUDO_PASSWORD_REQUIRED==False:
            return None
        elif self.sudo_password_fn==None:
            raise UserError(errors[ERR_NO_SUDO_PW],
                            msg_args={"id":self.props.id, "action":action.NAME})
        else:
            return self.sudo_password_fn()


def make_action(fn):
    """This is a decorator which converts a function to an action. The function
    is passed the enclosing action object as first parameter.

    Example::

        @make_action
        def foo(self, x):
            self.ctx.logger.debug("In foo")
            print "x=%s" % x

        ctx.r(foo, "this is x")
    """
    class _action(Action):
        NAME=fn.__name__
        def __init__(self, ctx):
            super(_action, self).__init__(ctx)
        def run(self, *args, **kwargs):
            fn(self, *args, **kwargs)
        def dry_run(self, *args, **kwargs):
            pass
    return _action


def wrap_action(fn):
    """This function takes a function and returns an action which calls
    the function. Unlike, make_action(), it does not pass self as the
    first parameter. This is useful for wrapping existing functions.

    Example::

        self.ctx.r(wrap_action(shutil.copy), "foo.txt", "bar.txt")
    """
    class _action(Action):
        NAME=fn.__name__
        def __init__(self, ctx):
            super(_action, self).__init__(ctx)
        def run(self, *args, **kwargs):
            fn(*args, **kwargs)
        def dry_run(self, *args, **kwargs):
            pass
    return _action


def make_value_action(fn):
    """This is a decorator which converts a function to a value
    action. The function is passed the enclosing function object as its
    first parameter.

    Example::

        @make_value_action
        def foo(self, x):
            self.ctx.logger.debug("In foo")
            print "x=%s" % x
            return x

        y = ctx.rv(foo, "this is x")
    """
    class _action(ValueAction):
        NAME=fn.__name__
        def __init__(self, ctx):
            super(_action, self).__init__(ctx)
        def run(self, *args, **kwargs):
            return fn(self, *args, **kwargs)
        def dry_run(self, *args, **kwargs):
            return None
    return _action

def adapt_sudo_value_action(va):
    """Make an sudo_value_action into an action that always
    calls sudo_run() by return a new wrapper object.
    This is useful in cases where we want to always call run(),
    like ctx.check_poll().
    """
    class myaction(SudoValueAction):
        NAME = va.__name__
        def __init__(self, ctx):
            super(myaction, self).__init__(ctx)
            self.action = va(ctx)
        def run(self, *args, **kwargs):
            return self.action.sudo_run(*args, **kwargs)

        def sudo_run(self, *args, **kwargs):
            return self.action.sudo_run(*args, **kwargs)

        def dry_run(self, *args, **kwargs):
            return self.action.dry_run(*args, **kwargs)
 
        def format_action_args(self, *args, **kwargs):
            return self.action.dry_run(*args, **kwargs)

        def format_action_result(self, result):
            return self.action.format_action_result(result)
    return myaction


def _warning(action, msg):
    """Log a warning for dry run mode.
    """
    action.ctx.logger.warning("Resource '%s', action '%s': %s" %
                              (action.ctx.props.id, action.NAME, msg))


def _check_dir_exists(dir_path, action):
    if not os.path.isdir(dir_path):
        if not action.ctx.dry_run:
            raise UserError(errors[ERR_DIR_NOT_FOUND],
                            msg_args={"dirpath":dir_path,
                                      "resid":action.ctx.props.id},
                            developer_msg="action was %s" % action.NAME)
        else:
            _warning(action, "Directory '%s' does not exist" % dir_path)

def _check_file_exists(file_path, action):
    if not os.path.exists(file_path):
        if not action.ctx.dry_run:
            raise UserError(errors[ERR_FILE_NOT_FOUND],
                            msg_args={"filepath":file_path,
                                      "resid":action.ctx.props.id},
                            developer_msg="action was %s" % action.NAME)
        else:
            _warning(action, "File '%s' does not exist" % file_path)


    
class check_file_exists(Action):
    """Action: Throws an error if file does not exist"""
    NAME = "check_file_exists"
    def __init__(self, ctx):
        super(check_file_exists, self).__init__(ctx)

    def run(self, file_path):
        _check_file_exists(file_path, self)

    def dry_run(self, file_path):
        _check_file_exists(file_path, self)

class check_dir_exists(Action):
    """Action: throws an error if directory does not exist"""
    NAME = "check_dir_exists"
    def __init__(self, ctx):
        super(check_dir_exists, self).__init__(ctx)

    def run(self, dir_path):
        _check_dir_exists(dir_path, self)

    def dry_run(self, dir_path):
        _check_dir_exists(dir_path, self)


class check_installable_to_dir(Action):
    """Action: given that the installed software is supposed to end up in
    install_dir, check that we can really install there. This means that
    the parent directory is writable (or if it doesn't exist, is creatable) and
    that the directory we will create by expanding the package archive doesn't
    already exist. If these checks fails, throws an UserError.
    """
    NAME = "check_installable_to_dir"
    def __init__(self, ctx):
        super(check_installable_to_dir, self).__init__(ctx)

    def run(self, install_dir):
        parent_dir = os.path.dirname(install_dir)
        if not pathutils.dir_path_is_writable(parent_dir):
            raise UserError(errors[ERR_INSTDIR_NOT_WRITABLE],
                            msg_args={"dir":parent_dir,
                                      "id":self.ctx.props.id})
        if os.path.exists(install_dir):
            raise UserError(errors[ERR_INSTDIR_ALREADY_EXISTS],
                            msg_args={"dir":install_dir,
                                      "id":self.ctx.props.id})

    def dry_run(self, install_dir):
        parent_dir = os.path.dirname(install_dir)
        if not pathutils.dir_path_is_writable(parent_dir):
            _warning(self, "install parent directory '%s' is not writable" % install_dir)
        if os.path.exists(install_dir):
            _warning(self, "install directory '%s' already exists" % install_dir)


def _build_template_var_re():
    import engage.utils.regexp as r
    start_char = r.character_set("A-Za-z\\_")
    follow_char = r.character_set("A-Za-z0-9\\_")
    identifier = r.concat(start_char,
                          r.zero_or_more(follow_char))
    composite_identifier = r.concat(identifier,
                                    r.zero_or_more(r.concat(r.lit("."),
                                                            identifier)))
    template_var = r.concat(r.lit("${"), r.group(composite_identifier), r.lit("}"))
    escape = r.lit("$$")
    return r.or_match(escape, template_var)

_template_var_re = _build_template_var_re().compile()


class TemplateError(Exception):
    def __init__(self, msg, var):
        super(TemplateError, self).__init__(msg)
        self.var = var

def _substitute_in_string(s, substitutions):
    def sub(mo):
        s = mo.string[mo.start():mo.end()]
        if s == "$$":
            return s
        else:
            var = mo.group(1)
            if not substitutions.has_key(var):
                raise TemplateError("Variable '%s' found in document but not in substitution map" % var, var)
            return substitutions[var]
    return _template_var_re.sub(sub, s)


class get_template_subst(ValueAction):
    """ValueAction: Substitute values in a template file and return the value.

    Unless src_dir is specified, the file is assumed to be in the
    data subdirectory, relative the the calling file.
    """
    NAME="get_template_subst"
    def __init__(self, ctx):
        super(get_template_subst, self).__init__(ctx)

    def _get_src_path(self, src_file, src_dir):
        if src_dir:
            src_path = os.path.join(src_dir, src_file)
        else:
            src_path = fileutils.get_data_file_path(self.ctx.filepath,
                                                    src_file)
        return src_path
                
    def run(self, src_file, src_dir=None):
        src_path = self._get_src_path(src_file, src_dir)
        _check_file_exists(src_path, self)
        with open(src_path, "rb") as f:
            try:
                return _substitute_in_string(f.read(), self.ctx.substitutions)
            except TemplateError, e:
                raise UserError(errors[ERR_TMPL_KEY],
                                msg_args={"key":e.var,
                                          "file":src_path,
                                          "resid":self.ctx.props.id,
                                          "action":"substitute"})
        
    def dry_run(self, src_file, src_dir=None):
        src_path = self._get_src_path(src_file, src_dir)
        _check_file_exists(src_path, self)
        return ""


class template(Action):
    """Action: Instantiate a template file.
    
    Unless src_dir is specified, the file is assumed to be in the
    data subdirectory, relative the the calling file.
    """
    NAME = "template"
    def __init__(self, ctx):
        super(template, self).__init__(ctx)

    def _get_src_path(self, src_file, src_dir):
        if src_dir:
            src_path = os.path.join(src_dir, src_file)
        else:
            src_path = fileutils.get_data_file_path(self.ctx.filepath,
                                                    src_file)
        return os.path.abspath(os.path.expanduser(src_path))
                
    def run(self, src_file, target_path, src_dir=None):
        src_path = self._get_src_path(src_file, src_dir)
        target_path = os.path.abspath(os.path.expanduser(target_path))
        _check_file_exists(src_path, self)
        _check_dir_exists(os.path.dirname(target_path), self)
        with open(src_path, "rb") as f:
            try:
                data = _substitute_in_string(f.read(), self.ctx.substitutions)
            except TemplateError, e:
                raise UserError(errors[ERR_TMPL_KEY],
                                msg_args={"key":e.var,
                                          "file":src_path, 
                                          "resid":self.ctx.props.id,
                                          "action":"template"})
        with open(target_path, "wb") as f:
            f.write(data)

    def dry_run(self, src_file, target_path, src_dir=None):
        src_path = self._get_src_path(src_file, src_dir)
        target_path = os.path.abspath(os.path.expanduser(target_path))
        _check_file_exists(src_path, self)
        _check_dir_exists(os.path.dirname(target_path), self)

class instantiate_template_str(Action):
    """Action: Instantiate a template string, creating the specified file.
    """
    NAME = "instantiate_template_str"
    def __init__(self, ctx):
        super(instantiate_template_str, self).__init__(ctx)

    def _do_substitution(self, src_string, target_path):
        target_path = os.path.abspath(os.path.expanduser(target_path))
        _check_dir_exists(os.path.dirname(target_path), self)
        try:
            return _substitute_in_string(src_string, self.ctx.substitutions)
        except TemplateError, e:
            raise UserError(errors[ERR_TMPLSTR_KEY],
                            msg_args={"key":e.var,
                                      "file":target_path, 
                                      "resid":self.ctx.props.id,
                                      "action":self.NAME})
        
    def run(self, src_string, target_path):
        data = self._do_substitution(src_string, target_path)
        with open(target_path, "w") as f:
            f.write(data)
            
    def dry_run(self, src_string, target_path):
        """In dry run mode, we run the string substitution to make sure
        the input string has all the required keys. We don't actually
        write the file.
        """
        self._do_substitution(src_string, target_path)


@make_value_action
def subst_in_file(self, filename, pattern_list, subst_in_place=False):
    """Scan the specified file and substitute patterns. pattern_list is
    list of pairs, where the first element is a regular expression pattern
    and the second element is a either a string or a function. If the
    second element is a string, then occurrances of the pattern in the file
    are all replaced with the string. If the value is a function, then
    this function is called with a match object and should return the
    new value for the pattern. See the python documentation on re.sub() for
    details.

    If subst_in_place is True, then we leave only the modified file. If it
    is False, we leave the orginal file at <filename>.orig.

    Note that we set the permissions of the new file version to be the same
    as those for the original file. This is important for executable files.

    Returns the total number of substitutions made
    """
    return fileutils.subst_in_file(filename, pattern_list,
                                   subst_in_place=subst_in_place)
    

@make_action
def subst_in_file_and_check_count(self, filename, pattern_list,
                                  num_expected_changes, subst_in_place=False):
    """Action: Just like the subst_in_file value action, but checks the
    count returned against an expected count (num_expected_changes) and
    raises an error if the number does not match.
    """
    cnt = fileutils.subst_in_file(filename, pattern_list,
                                   subst_in_place=subst_in_place)
    if cnt != num_expected_changes:
        raise UserError(errors[ERR_WRONG_SUBST_COUNT],
                        msg_args={"id":self.ctx.props.id,
                                  "file":filename,
                                  "exp":num_expected_changes,
                                  "actual":cnt},
                        developer_msg="pattern_list: %s" % pattern_list.__repr__())

@make_action
def set_file_mode_bits(self, path, mode_bits):
    """Action: set the file's mode bits as specified.
    This is itempotent.
    """
    _check_file_exists(path, self)
    current_mode = os.stat(path).st_mode
    if current_mode != mode_bits:
        os.chmod(path, mode_bits)
    

class mkdir(SudoAction):
    """SudoAction: Create a directory. If parent does not exist, include the -p option.
    """
    NAME="mkdir"
    def __init__(self, ctx):
        super(mkdir, self).__init__(ctx)

    def run(self, dir_path):
        if os.path.exists(os.path.dirname(dir_path)):
            os.mkdir(dir_path)
        else:
            os.makedirs(dir_path)

    def sudo_run(self, dir_path):
        procutils.sudo_mkdir(dir_path, self.ctx._get_sudo_password(self),
                             self.ctx.logger,
                             create_intermediate_dirs=not os.path.exists(os.path.dirname(dir_path)))
        
    def dry_run(self, dir_path):
        pass


@make_action
def sudo_mkdir(self, dir_path, create_intermediate_dirs=False):
    """Action: create a directory, running as root.
    """
    if os.path.exists(dir_path):
        self.ctx.logger.debug("Directory %s already exists" % dir_path)
    else:
        procutils.sudo_mkdir(dir_path, self.ctx._get_sudo_password(self),
                             self.ctx.logger,
                             create_intermediate_dirs=create_intermediate_dirs)


@make_value_action
def sudo_cat_file(self, path):
    """ValueAction: use this to get the contents of a file that is only readable
    as root. Returns the contents of the file"""
    return procutils.sudo_cat_file(path, self.ctx.logger,
                                   self.ctx._get_sudo_password(self))


class copy_file(SudoAction):
    """SudoAction: Copy a file src to dest.
    """
    NAME="copy_file"

    def __init__(self, ctx):
        super(copy_file, self).__init__(ctx)

    def run(self, src, dest):
        _check_file_exists(src, self)
        shutil.copyfile(src, dest)

    def sudo_run(self, src, dest):
        procutils.sudo_copy([src, dest], self.ctx._get_sudo_password(self),
                            self.ctx.logger)

    def dry_run(self, src, dest):
        pass

    
@make_action
def sudo_copy(self, copy_args):
    """Action: copy files (as in the unix cp command) running as the superuser.
    copy_args is a list of arguments to the cp operation
    (e.g. [src_file, dest_file]).
    """
    procutils.sudo_copy(copy_args, self.ctx._get_sudo_password(self),
                        self.ctx.logger)

@make_action
def sudo_set_file_permissions(self, path, user_id, group_id, mode_bits):
    """Action: set the permissions of a file, running as root"""
    _check_file_exists(path, self)
    procutils.sudo_set_file_permissions(path, user_id, group_id,
                                        mode_bits, self.ctx.logger,
                                        self.ctx._get_sudo_password(self))

@make_action
def sudo_set_file_perms_by_name(self, path, mode_bits, user_name=None,
                                group_name=None):
    """Action: set the permissions of a file, running as root. This is similar to
    sudo_set_file_permissions, but instead takes user/group names rather
    than numeric ids. If the user name or group name are not specified,
    the current effective user/group ids are used.
    """
    _check_file_exists(path, self)
    if user_name==None:
        user_id = os.geteuid()
    else:
        user_id = pwd.getpwnam(user_name).pw_uid
    if group_name==None:
        group_id = os.getegid()
    else:
        group_id = grp.getgrnam(group_name).gr_gid
    procutils.sudo_set_file_permissions(path, user_id, group_id,
                                        mode_bits, self.ctx.logger,
                                        self.ctx._get_sudo_password(self))


@make_action
def sudo_ensure_user_in_group(self, group_name, user=None):
    """Action: ensure that the user is in the specified group. If user is left
    as default, we assume the current user.
    """
    procutils.sudo_ensure_user_in_group(group_name, self.ctx.logger,
                                        self.ctx._get_sudo_password(self),
                                        user=user)


@make_action
def sudo_add_config_file_line(self, config_file, line):
    """Action: add or uncomment the specified line in the config file,
    running as root.
    """
    _check_file_exists(config_file, self)
    cfg_file.add_config_file_line(config_file, line,
                                  self.ctx._get_sudo_password(self))


@make_action
def extract_package_as_dir(self, package, desired_extract_path):
    """Action: given an archive-type package, we call its extract method. Then,
    we rename the resulting directory, if necessary, to make it match
    extracted path.
    """
    parent_dir = os.path.dirname(desired_extract_path)
    desired_dirname = os.path.basename(desired_extract_path)
    extracted_dir = package.extract(parent_dir)
    if extracted_dir != desired_dirname:
        extracted_path = os.path.join(parent_dir, extracted_dir)
        # make the final name of the directory equivalent to the
        # desired dirname
        self.ctx.logger.debug("mv %s %s" % (extracted_path, desired_extract_path))
        shutil.move(extracted_path, desired_extract_path)

@make_action
def ensure_dir_exists(self, dir_path):
    """Action: if the specified directory does not exist, create it.
    """
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

@make_action
def ensure_shared_perms(self, path, group_name, writable_to_group=False):
    """Action: make sure that the specified path is accessible to the
    specified group. If a directory, this is done recursively.
    """
    _check_file_exists(path, self)
    if os.path.isdir(path):
        fileutils.set_shared_directory_group_and_permissions(path, group_name,
            self.ctx.logger, writable_to_group=writable_to_group)
    else:
        fileutils.set_shared_file_group_and_permissions(path, group_name,
            self.ctx.logger, writable_to_group=writable_to_group)

@make_action
def sudo_ensure_shared_perms(self, path, group_name, writable_to_group=False):
    """Action: make sure that the specified path is accessible to the
    specified group. If a directory, this is done recursively. This version is
    run as the super user.
    """
    _check_file_exists(path, self)
    if os.path.isdir(path):
        fileutils.sudo_set_shared_directory_group_and_permissions(path, group_name,
            self.ctx.logger, self.ctx._get_sudo_password(self),
            writable_to_group=writable_to_group)
    else:
        fileutils.set_shared_file_group_and_permissions(path, group_name,
            self.ctx.logger, writable_to_group=writable_to_group,
            sudo_password=self.ctx._get_sudo_password(self))
    fileutils.sudo_ensure_directory_group_reachable(path, group_name, self.ctx.logger,
                                                    self.ctx._get_sudo_password(self))

@make_action
def move_old_file_version(self, file_path, backup_name=None,
                          leave_old_backup_file=False):
    """Action: If the specified file exists, rename it to the backup name.
    The default backup name is <filename>.orig. If the backup file already
    exists, we delete it first, unless leave_old_backup_file is True.
    In that case, we delete the file reference by file_path, keeping the
    oldest backup.

    If the file referenced by file_path does not exist, we do nothing.
    """
    def delete_file_or_dir(fpath):
        if os.path.isdir(fpath):
            self.ctx.logger.debug("rm -r %s" % fpath)
            shutil.rmtree(fpath)
        else:
            self.ctx.logger.debug("rm %s" % fpath)
            os.remove(fpath)
            
    if not backup_name:
        backup_name = file_path + ".orig"
    if not os.path.exists(file_path):
        return # nothing to do
    if os.path.exists(backup_name):
        if leave_old_backup_file:
            delete_file_or_dir(file_path)
            return # we leave the older version
        else:
            delete_file_or_dir(backup_name)
    
    self.ctx.logger.debug("mv %s %s" % (file_path, backup_name))
    os.rename(file_path, backup_name)


def _check_poll(calling_action, stop_pred, description,
                timeout_tries=10, time_between_tries=2.0):
    """This is a utility function for use within actions when we want to
    poll multiple times waiting for something to happen. stop_pred is a function
    that will be called until it returns True. If the timeout happens before
    stop_pred returns true, then the ERR_ACTION_POLL_TIMEOUT error is thrown.
    """
    if calling_action.ctx.dry_run:
        return
    for i in range(timeout_tries):
        v = stop_pred()
        if v==True:
            return
        else:
            if i != (timeout_tries-1): time.sleep(time_between_tries)
    raise UserError(errors[ERR_ACTION_POLL_TIMEOUT],
                    msg_args={"id":calling_action.ctx.props.id,
                              "action":calling_action.NAME,
                              "description":description,
                              "time":timeout_tries*time_between_tries})
                    


class start_server(Action):
    """Action: start another process as a server.
    If started successfully, the pid of the process is written to pidfile.
    If timeout_tries>0, then we wait until the pid file has been written with
    a live process id before returning.

    Note that, if the program you are starting can daemonize itself (through an
    option like --daemonize or --detach), you should use the run_program action
    instead.
    """
    NAME="start_server"
    def __init__(self, ctx):
        super(start_server, self).__init__(ctx)

    def run(self, cmd_and_args, log_file, pid_file, cwd="/", environment={},
                 timeout_tries=10, time_between_tries=2.0):
        _check_file_exists(cmd_and_args[0], self)
        procutils.run_server(cmd_and_args, environment, log_file,
                             self.ctx.logger, pid_file, cwd)
        if timeout_tries>0:
            _check_poll(self,
                        lambda : procutils.check_server_status(pid_file,
                                                               self.ctx.logger,
                                                               self.ctx.props.id) != None,
                        "server startup", timeout_tries, time_between_tries)

    def dry_run(self, cmd_and_args, log_file, pid_file, cwd="/", environment={},
                timeout_tries=10, time_between_tries=2.0):
        pass
    


@make_action
def stop_server(self, pid_file, timeout_tries=20, force_stop=False):
    """Action: stop a server process started using start_server. Waits for
    process to exit. timeout_tries is the number of times to poll the process
    after sending the signal, with one second between each try.
    """
    try:
        procutils.stop_server_process(pid_file, self.ctx.logger,
                                      self.ctx.props.id, timeout_tries,
                                      force_stop)
    except procutils.ServerStopTimeout, e:
        raise UserError(errors[ERR_SERVER_STOP_TIMEOUT],
                        msg_args={"action":self.NAME,
                                  "id":self.ctx.props.id, "pid":e.pid,
                                  "timeout":e.timeout_in_secs})


class get_server_status(SudoValueAction):
    """SudoValueAction: check whether a server process is alive by grabbing its
    pid from the specified
    pidfile and then checking the liveness of that pid. If the pidfile doesn't
    exist, assume that server isn't alive. Returns the pid if the server is
    running and None if it isn't running.

    The sudo_run() method is for situations where the pid file is
    not readable by the engage user.

    NOTE: If you are using this in the is_running() method of a service,
    be sure to convert the result to a boolean. For example:
    return self.ctx.rv(check_server_status, pid_file) != None
    """
    NAME="get_server_status"
    def run(self, pid_file, remove_pidfile_if_dead_proc=False):
        return procutils.check_server_status(pid_file, self.ctx.logger,
                                             self.ctx.props.id,
                                             remove_pidfile_if_dead_proc)

    def sudo_run(self, pid_file, remove_pidfile_if_dead_proc=False):
        return procutils.sudo_check_server_status(pid_file, self.ctx.logger,
                                                  self.ctx._get_sudo_password(self),
                                                  self.ctx.props.id,
                                                  remove_pidfile_if_dead_proc)

    def dry_run(self, pid_file, remove_pidfile_if_dead_proc=False):
        pass

        
@make_action
def sudo_start_server(self, cmd_and_args, log_file, cwd=None, environment={}):
    """Action: start another process as a server, under root. Does not wait for
    it to complete. This daemonizes the server process, doing the voodoo needed
    (e.g. two forks, closing all fds).

    Unlike the vanilla start_server(), the program being run is responsible for
    creating a pidfile. We do this because, if we run under sudo, the child
    won't be the actual server process.
    """
    _check_file_exists(cmd_and_args[0], self)
    procutils.sudo_run_server(cmd_and_args, environment, log_file,
                              self.ctx.logger, self.ctx._get_sudo_password(self),
                              cwd)

@make_action
def sudo_run_program(self, program_and_args, cwd=None):
    """Action: Run the specified program as a super user"""
    procutils.run_sudo_program(program_and_args,
                               self.ctx._get_sudo_password(self),
                               self.ctx.logger,
                               cwd=cwd)


class sudo_run_program_and_scan_results(ValueAction):
    """ValueAction: Run the specified program as the super user and scan the
    results for the provided regular expressions.
    """
    NAME="sudo_run_program_and_scan_results"
    def __init__(self, ctx):
        super(sudo_run_program_and_scan_results, self).__init__(ctx)
    def run(self, program_and_args, re_map,
            env=None, cwd=None, log_output=False):
        return procutils.run_sudo_program_and_scan_results(program_and_args, re_map,
                                                           self.ctx.logger,
                                                           self.ctx._get_sudo_password(self),
                                                           env=env, cwd=cwd,
                                                           log_output=log_output)

    def dry_run(self, program_and_args, re_map,
                env=None, cwd=None, log_output=False):
        return (None, None)

                                       

@make_value_action
def get_path_exists(self, file_path, timeout_tries, time_between_tries):
    """ValueAction: return True if the file path exists, False otherwise.
    """
    return os.path.exists(file_path)

class run_program(Action):
    """Action: run the specified program as a subprocess and log its output.
    Throws an exception (user error) if the program's return code is nonzero.
    """
    NAME = "run_program"

    def __init__(self, ctx):
        super(run_program, self).__init__(ctx)

    def run(self, program_and_args, cwd=None, env_mapping=None,
            input=None, hide_input=False, hide_command=False):
        _check_file_exists(program_and_args[0], self)
        rc = procutils.run_and_log_program(program_and_args, env_mapping,
                                           self.ctx.logger, cwd=cwd,
                                           input=input,
                                           hide_input=hide_input,
                                           hide_command=hide_command)
        if rc!=0:
            raise UserError(errors[ERR_SUBPROCESS_RC],
                            msg_args={"cmd":' '.join(program_and_args),
                                      "id":self.ctx.props.id},
                            developer_msg="return code was %d" % rc)

    def dry_run(self, program_and_args, cwd=None, env_mapping=None,
                input=None, hide_input=False, hide_command=False):
        pass
            
class create_engage_dist(Action):
    """Action: create an engage distribution. This uses the create-distribution
    command. We do this if we are going to need a distribution for a
    distributed install. The distribution will include any extensions
    that have been added to the current deployment home.
    """
    NAME = "create_engage_dist"
    def __init__(self, ctx):
        super(create_engage_dist, self).__init__(ctx)

    def _get_command(self):
        self.ctx.checkp("input_ports.host.genforma_home")
        cmd = os.path.join(self.ctx.props.input_ports.host.genforma_home,
                           "engage/bin/create-distribution")
        _check_file_exists(cmd, self)
        return cmd
    
    def run(self, target_path):
        parent_dir = os.path.dirname(target_path)
        if not os.path.exists(parent_dir):
            logger.debug("mkdir -p %s" % parent_dir)
            os.makedirs(parent_dir)
        cmd = self._get_command()
        rc = procutils.run_and_log_program([cmd, "-a", target_path], None,
                                           self.ctx.logger)
        if rc != 0:
            raise UserError(errors[ERR_CREATE_DIST_FAILED],
                            msg_args={"id":self.ctx.props.id,
                                      "file":target_path},
                            developer_msg="return code was %d" % rc)

    def dry_run(self, target_path):
        self._get_command()


@make_action
def check_port_available(self, hostname, port):
    """Action: Verify that the port is available. If something
    responds, raise ERR_PORT_TAKEN. Otherwise, do nothing. This is
    intended to be called as a part of validate_pre_install().
    """
    if httputils.ping_webserver(hostname, port, self.ctx.logger)==True:
        raise UserError(errors[ERR_PORT_TAKEN],
                        msg_args={"id":self.ctx.props.id,
                                  "port":port},
                        developer_msg="Hostname was %s" % hostname)
    else:
        self.ctx.logger.debug("Port %d is available for %s" %
                              (port, self.ctx.props.id))


############################################################################
#                                   Tests                                  #
############################################################################
_test_data_file_contents = \
"""This is just test data for action.py

The following value should be /foo/bar:
  /foo/bar

The following value should be 34:
  34

The following value should be /foo/bar/test:
  /foo/bar/test
"""

class TestActions(unittest.TestCase):
    def setUp(self):
        rc = {"id":"apache2", "key":{"name":"apache2", "version":"2.2"},
              "config_port": { "prop1":"/foo/bar", "prop2":34 }}
        import engage.utils.log_setup
        logger = engage.utils.log_setup.logger_for_repl()
        self.ctx = Context(rc, logger, "./action.py")

    def testAdd(self):
        self.ctx.add("prop3", os.path.join(self.ctx.props.config_port.prop1, "test"))
        self.assertEqual(self.ctx.props.prop3, "/foo/bar/test")
        
    def testSubstitute(self):
        self.ctx.add("prop3", os.path.join(self.ctx.props.config_port.prop1, "test"))
        tmpl_val = self.ctx.rv(get_template_subst, "test.txt")
        self.assertEqual(_test_data_file_contents, tmpl_val)

    def testSubstituteError(self):
        try:
            tmpl_val = self.ctx.rv(get_template_subst, "test.txt")
            self.assert_(0, "Should not get here")
        except UserError, e:
            self.assertEqual(ERR_TMPL_KEY, e.error_code)

    def testTemplate(self):
        self.ctx.add("prop3", os.path.join(self.ctx.props.config_port.prop1, "test"))
        with fileutils.NamedTempFile() as f:
            self.ctx.r(template, "test.txt", f.name)
            with open(f.name, "rb") as g:
                self.assertEqual(_test_data_file_contents, g.read())

    def testCheckp(self):
        self.ctx.checkp("id").checkp("key.name").checkp("key.version")
        self.ctx.checkp("config_port.prop1").checkp("config_port.prop2", typ=int)

    def testCheckpPropNotFound(self):
        try:
            self.ctx.checkp("config_port.bogosity")
            self.assert_(0, "should not get here")
        except UserError, e:
            self.assertEqual(ERR_PROP_NOT_FOUND, e.error_code)

    def testCheckpPropNotFoun2(self):
        try:
            self.ctx.checkp("input_ports.foo")
            self.assert_(0, "should not get here")
        except UserError, e:
            self.assertEqual(ERR_PROP_NOT_FOUND, e.error_code)

    def testCheckpPropNotString(self):
        try:
            self.ctx.checkp("config_port.prop2")
            self.assert_(0, "should not get here")
        except UserError, e:
            self.assertEqual(ERR_PROP_TYPE_NOT_STR, e.error_code)

    def testCheckpPropNoMatch(self):
        try:
            self.ctx.checkp("config_port.prop1", typ=int)
            self.assert_(0, "should not get here")
        except UserError, e:
            self.assertEqual(ERR_PROP_TYPE_NOMATCH, e.error_code)
            
    def testCtxMissingIdProp(self):
        rc = {"key":{"name":"apache2", "version":"2.2"},
              "config_port": { "prop1":"/foo/bar", "prop2":34 }}
        import engage.utils.log_setup
        logger = engage.utils.log_setup.logger_for_repl()
        try:
            bad_ctx = Context(rc, logger, "./action.py")
            self.assert_(0, "Should not get here")
        except UserError, e:
            self.assertEqual(ERR_MISSING_ID_PROP, e.error_code)

    def testCheckPort(self):
        self.ctx.check_port("config_port", prop1=str, prop2=int)

    def testCheckInstallableToDir(self):
        self.ctx.r(check_installable_to_dir,
                   os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "foo")))

    def testKWArgsInActions(self):
        self_ = self
        class TestAction(Action):
            NAME="TestAction"
            def __init__(self, ctx):
                super(TestAction, self).__init__(ctx)
            def run(self, arg1, arg2, kw_arg=None):
                self_.assert_(kw_arg==arg1)
            def dry_run(self, arg1, arg2, kw_arg=None):
                self_.assert_(kw_arg==arg1)
        self.ctx.r(TestAction, "t", 2, kw_arg="t")
        self.ctx.r(TestAction, None, 2)

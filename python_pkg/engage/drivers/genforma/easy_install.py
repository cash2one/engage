"""Resource manager for easy_install packages. 
"""

import commands
import os

import engage.drivers.resource_manager as resource_manager
import engage.utils.path
import engage_utils.process as iuproc
import engage.utils.log_setup
from engage.drivers.action import *
from engage.drivers.genforma.python import is_module_installed
from engage.utils.user_error import UserError, ScriptErrInf
import gettext
_ = gettext.gettext

logger = engage.utils.log_setup.setup_script_logger(__name__)

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_POST_INSTALL = 1
ERR_PKG_INSTALL = 2

define_error(ERR_POST_INSTALL,
             _("Ran easy_install for resource %(id)s, but Python module %(module)s was not found afterward."))
define_error(ERR_PKG_INSTALL,
             _("easy_install of package %(pkg)s failed for resource %(id)s"))


class install_package(Action):
    """Action to install a Python package via easy_install.
    The library_package parameter is a package object as passed
    into the resource's install method (defined by engage.engine.library).
    """
    NAME="easy_install.install_package"
    def __init__(self, ctx):
        super(install_package, self).__init__(ctx)
        self.ctx.checkp("input_ports.setuptools.easy_install")

    def _get_cmdline(self, library_package):
        p = self.ctx.props
        cmd = [p.input_ports.setuptools.easy_install]
        if library_package.type == "Reference": 
            cmd.append(library_package.location)
        else:
            filepath = library_package.get_file()
            cmd.append(filepath)
        return cmd

    def format_action_args(self, library_package, env_mapping={}):
        mapping = "{}" if len(env_mapping)==0 else "{ ... }"
        return "%s %s env_mapping=%s" % (self.NAME, library_package, mapping)
    
    def run(self, library_package, env_mapping={}):
        p = self.ctx.props
        cmd = self._get_cmdline(library_package)
        rc = iuproc.run_and_log_program(cmd, env_mapping, self.ctx.logger,
                                        cwd=os.path.dirname(p.input_ports.setuptools.easy_install))
	if rc != 0:
            raise UserError(errors[ERR_PKG_INSTALL], {"pkg":package.__repr__(),
                                                      "id":p.id},
                            developer_msg="return code was %d" % rc)

    def dry_run(self, library_package, env_mapping={}):
        cmd = self._get_cmdline(library_package)
        self.ctx.logger.debug(' '.join(cmd))


def make_context(resource_json, sudo_password_fn,
                 dry_run=False):
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=sudo_password_fn,
                  dry_run=dry_run)
    ctx.checkp("input_ports.setuptools.easy_install") # path to executable
    # optional properties (prefix and script dirs are needed for the Trac install)
    if ctx.substitutions.has_key("config_port.install_dir"):
        ctx.add("prefix_dir", ctx.props.config_port.install_dir)
    else:
        ctx.add("prefix_dir", None)
    if ctx.substitutions.has_key("config_port.script_dir"):
        ctx.add("script_dir", ctx.props.config_port.script_dir)
    else:
        ctx.add("script_dir", None)
    # To tell whether the package is installed, we need to know the python
    # executable and a test module to try to import.
    if ctx.substitutions.has_key("input_ports.python.home"):
        ctx.add("python_exe", ctx.props.input_ports.python.home)
    else:
        ctx.add("python_exe", None)
    if ctx.substitutions.has_key("output_ports.pkg_info.test_module"):
        ctx.add("test_module", ctx.props.output_ports.pkg_info.test_module)
    else:
        ctx.add("test_module", None)
    return ctx


class Manager(resource_manager.Manager):
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(), None,
                                dry_run=dry_run)

    def validate_pre_install(self):
        assert os.path.exists(self.ctx.props.input_ports.setuptools.easy_install) or \
               self.ctx.dry_run

    def is_installed(self):
        p = self.ctx.props
        if self.metadata.is_installed():
            logger.debug("Metadata indicates that %s is already installed" %
                         p.id)
            return True
        elif (not p.python_exe) or (not p.test_module):
            # we don't have the metadata defined to check whether
            # this package is installed
            logger.debug("%s: metadata not present to tell if package is installed, so assuming not installed" % p.id)
            return False
        else:
            # try importing the test module specified in the metadata
            # to see if the package is installed
            return self.ctx.rv(is_module_installed, p.test_module)

    def install(self, package):
        p = self.ctx.props
        cmd = [p.input_ports.setuptools.easy_install]
        if p.prefix_dir != None:
            cmd.append("--prefix_dir=%s" % p.prefix_dir)
        if p.script_dir != None:
            cmd.append("--script-dir=%s" % p.script_dir)
            if not os.path.exists(p.script_dir) and not self.ctx.dry_run:
                # TODO:
                # This is a workaround for the pygments package used by trac:
                # The script is supposed to be installed in trac's bin directory,
                # but that directory does not yet exist (since pygments is a
                # dependency for trac). To solve this, we just create the script
                # directory (in this case genforma_home/trac/bin) if it does
                # not already exist. We should see if there's a better solution
                # in how we model resources.
                logger.warn("Script directory '%s' for %s does not exist, attempting to create it" %
                            (p.script_dir, package.location))
                os.makedirs(p.script_dir)
        if package.type == "Reference": # FIXME: this is defined in library.py as REFERENCE_TYPE
            # reference package type should be used for package names (e.g. Django)
            # or URL's
            cmd.append(package.location)
        else:
            # if a file or archive, then we get the local location and pass that
            # to easy install
            filepath = package.get_file()
            cmd.append(filepath)
        self.ctx.r(run_program, cmd, cwd=os.path.dirname(p.input_ports.setuptools.easy_install),
                   env_mapping={})

    def validate_post_install(self):
        p = self.ctx.props
        if (not p.python_exe) or (not p.test_module) or self.ctx.dry_run:
            return
        else:
            # try importing the test module specified in the metadata
            # to see if the package is installed
            if not self.ctx.rv(is_module_installed, p.test_module):
                raise UserError(errors[ERR_POST_INSTALL],
                                msg_args={"id":p.id, "module":p.test_module})

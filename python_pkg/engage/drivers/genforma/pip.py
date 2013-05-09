"""Resource manager for pip packages. The location for a package can be one
of the following:
 * A pypi package name
 * A local archive file name
 * A package name and version constraint containing == or >=. This goes into
   a requirements file.
"""

import commands
import os
import tempfile

import engage.drivers.resource_manager as resource_manager
import  engage.drivers.resource_metadata as resource_metadata
from engage.drivers.action import *
from engage.drivers.genforma.python import is_module_installed
import engage.engine.library as library
import engage.utils.path as path
import engage_utils.process as iuproc
import engage.utils.log_setup as iulog_setup
from engage_utils.versions import compare_versions

from engage.utils.user_error import UserError, ScriptErrInf
import gettext
_ = gettext.gettext

logger = iulog_setup.setup_script_logger(__name__)

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("pip", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_PKG = 1
ERR_POST_INSTALL = 2

PIP_TIMEOUT=45

define_error(ERR_PKG,
             _("error installing %(pkg)s using pip"))
define_error(ERR_POST_INSTALL,
             _("Ran pip for resource %(id)s, but Python module %(module)s was not found afterward."))

@make_value_action
def is_module_at_version(self, python_exe, test_module, version_property, expected_version):
    cmd = [python_exe, "-c", "import %s; print %s" % (test_module, version_property)]
    data = iuproc.run_program_and_capture_results(cmd, None, self.ctx.logger,
                                                  cwd=os.path.dirname(python_exe)).rstrip()
    if data.startswith('(') and data.endswith(')'):
        # the version is a tuple, not a string. convert to a string.
        cmd = [python_exe, "-c",
               'import %s; print ".".join([str(e) for e in %s])' % (test_module, version_property)]
        data = iuproc.run_program_and_capture_results(cmd, None, self.ctx.logger,
                                                      cwd=os.path.dirname(python_exe)).rstrip()
    cmp = compare_versions(data, expected_version)
    return (cmd==0) or (cmd==1) # true if data >= expected_version
    

def make_context(resource_json, dry_run=False):
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=None,
                  dry_run=dry_run)
    ctx.check_port("input_ports.pip",
                   pipbin=unicode)
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
    # if version_property is specified, we'll use that to see if the right
    # version was installed
    if ctx.substitutions.has_key("output_ports.pkg_info.version_property"):
        ctx.add("version_property", ctx.props.output_ports.pkg_info.version_property)
    else:
        ctx.add("version_property", None)
    return ctx


class Manager(resource_manager.Manager):
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(), dry_run=dry_run)
	try:
           self.prefix_dir = metadata.config_port["install_dir"]
        except:
           self.prefix_dir = None
	try:
           self.script_dir = metadata.config_port["script_dir"]
        except:
           self.script_dir = None
        self.pip = self.ctx.props.input_ports.pip.pipbin
        self.editable = False

    
    def validate_pre_install(self):
	pass

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
            installed = self.ctx.rv(is_module_installed, p.test_module)
            if installed and p.version_property!=None:
                # we have a version property, compare it to the resource's
                # version. If the installed version is older, we'll assume we
                # need to reinstall.
                return self.ctx.rv(is_module_at_version, p.python_exe,
                                   p.test_module,
                                   p.version_property,
                                   self.metadata.key['version'])
            else:
                return installed
            

    def install(self, package):
        p = self.ctx.props
        cmd = [self.pip, 'install', "--use-mirrors",
               "--timeout=%d" % PIP_TIMEOUT]
        if p.test_module and self.ctx.rv(is_module_installed, p.test_module):
            # if there is already a module with the same name, we need to force
            # an upgrade
            cmd.append('--upgrade')
        if self.editable:
            cmd.append('-e')
        if self.prefix_dir != None:
            cmd.append("--prefix_dir=%s" % self.prefix_dir)
        if self.script_dir != None:
            cmd.append("--script-dir=%s" % self.script_dir)
            if not os.path.exists(self.script_dir):
                # TODO:
                # This is a workaround for the pygments package used by trac:
                # The script is supposed to be installed in trac's bin directory,
                # but that directory does not yet exist (since pygments is a
                # dependency for trac). To solve this, we just create the script
                # directory (in this case genforma_home/trac/bin) if it does
                # not already exist. We should see if there's a better solution
                # in how we model resources.
                logger.warn("Script directory '%s' for %s does not exist, attempting to create it" %
                            (self.script_dir, package.location))
                if not self.ctx.dry_run:
                    os.makedirs(self.script_dir)
        req_file = None
        if package.type == library.Package.REFERENCE_TYPE:
            # reference package type should be used for package names (e.g. Django)
            # or URL's
            if "==" in package.location or ">=" in package.location:
                # this is a entry for a requirements file
                req_file = tempfile.NamedTemporaryFile(delete=False)
                req_file.write(package.location + "\n")
                req_file.close()
                logger.debug("Pip requirements file contents: %s" %
                             package.location)
                cmd.extend(["-r", req_file.name])
            else: # just a package name, can use command line directly
                cmd.append(package.location)
        else:
            # if a file or archive, then we get the local location and pass that
            # to pip 
            filepath = package.get_file()
            cmd.append(filepath)
        try:
            self.ctx.r(run_program, cmd)
        finally:
            if req_file:
                os.remove(req_file.name)


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

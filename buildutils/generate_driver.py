#! /usr/bin/env python
# Generate driver skeleton 

import re
import logging
import os
import os.path
import sys
import json
from optparse import OptionParser

LOG_LEVEL=logging.DEBUG
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(LOG_LEVEL)
logger.addHandler(handler)

try:
    import engage.version
except ImportError:
    path_dir = os.path.abspath(
                 os.path.expanduser(
                   os.path.join(
                     os.path.dirname(__file__),
                     "../python_pkg")))
    if not os.path.exists(path_dir):
        raise Exception("Cannot set up PYTHONPATH to include engage - could not find %s" % path_dir)
    sys.path.append(path_dir)

import engage.utils.rdef as rdef
import engage.engine.engage_file_layout as efl
import engage.engine.preprocess_resources as ppr
from engage.utils.file import NamedTempFile

skeleton = """
\"\"\"Resource manager for %(key)s %(version)s 
\"\"\"

# Common stdlib imports
import sys
import os
import os.path
## import commands

# fix path if necessary (if running from source or running as test)
try:
    import engage.utils
except:
    sys.exc_clear()
    dir_to_add_to_python_path = os.path.abspath((os.path.join(os.path.dirname(__file__), "../../../..")))
    sys.path.append(dir_to_add_to_python_path)

import engage.drivers.%(baseclass)s as %(baseclass)s
import engage.drivers.utils
# Drivers compose *actions* to implement their methods.
from engage.drivers.action import *

# setup errors
from engage.utils.user_error import UserError, EngageErrInf
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
# FILL IN
ERR_TBD = 0

define_error(ERR_TBD,
             _("Replace this with your error codes"))


# setup logging
from engage.utils.log_setup import setup_engage_logger
logger = setup_engage_logger(__name__)


# this is used by the package manager to locate the packages.json
# file associated with the driver
def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)

def make_context(resource_json, sudo_password_fn, dry_run=False):
    \"\"\"Create a Context object (defined in engage.utils.action). This contains
    the resource's metadata in ctx.props, references to the logger and sudo
    password function, and various helper functions. The context object is used
    by individual actions.

    If your resource does not need the sudo password, you can just pass in
    None for sudo_password_fn.
    \"\"\"
    ctx = Context(resource_json, logger, __file__,
                  sudo_password_fn=sudo_password_fn,
                  dry_run=dry_run)
%(port_checks)s
    # add any extra computed properties here using the ctx.add() method.
    return ctx

#
# Now, define the main resource manager class for the driver.
# If this driver is a service, inherit from service_manager.Manager.
# If the driver is just a resource, it should inherit from
# resource_manager.Manager. If you need the sudo password, add
# PasswordRepoMixin to the inheritance list.
#
class Manager(%(baseclass)s.Manager):
    # Uncomment the line below if this driver needs root access
    ## REQUIRES_ROOT_ACCESS = True 
    def __init__(self, metadata, dry_run=False):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        %(baseclass)s.Manager.__init__(self, metadata, package_name)
        self.ctx = make_context(metadata.to_json(),
                                None, # self._get_sudo_password,
                                dry_run=dry_run)

    def validate_pre_install(self):
        ## p = self.ctx.props
        ## self.ctx.r(check_installable_to_dir, p.config_port.home)
        assert 0, "need to implement"


    def is_installed(self):
        ## return os.path.exists(self.ctx.props.config_port.home)
        assert 0, "need to implement"

    def install(self, package):
        ## p = self.ctx.props
        ## Use the following if you need to extract an archive
        ## self.ctx.r(extract_package_as_dir, package,
        ##            p.config_port.home)
        assert 0, "need to implement"


    def validate_post_install(self):
        ## p = self.ctx.props
        ## self.ctx.r(check_dir_exists,  p.config_port.home)
        assert 0, "need to implement"

%(svcmethods)s
"""

_svc_methods = """
    def start(self):
        ## # Example code to start a server process
        ## p = self.ctx.props
        ## command_exe = ...
        ## self.ctx.r(start_server,
        ##            [command_exe, ... put args here ... ],
        ##            p.config_port.log_file,
        ##            p.config_port.pid_file,
        ##            cwd=os.path.dirname(command_exe))
        assert 0, "need to implement"

    def is_running(self):
        ## # Example code to check pid file
        ## p = self.ctx.props
        ## return self.ctx.rv(get_server_status,
        ##                    p.config_port.pid_file) != None
        assert 0, "need to implement"

    def stop(self):
        ## # Example code to terminate server process
        ## p = self.ctx.props
        ## self.ctx.r(stop_server, p.config_port.pid_file)
        assert 0, "need to implement"

    ## def get_pid_file_path(self):
    ##     """Method to return the path to the pid file for an installed service.
    ##     If there is no pid file for this service, just return None. This is
    ##     used by management tools (e.g. monit) to monitor the service.xs
    ##     """
    ##     return self.ctx.props.config_port.pid_file
"""

packages_file_example = """
[
  { "type": "Reference",
    "package_class": "DummyPackage",
    "location":""
  }
]
"""


drivertest_example = """
\"\"\"
Unit test script for %(res_name)s %(res_version)s driver.
This script is designed to be run from engage.tests.test_drivers.
\"\"\"


# Id for the resource to be tested.
# An instance with this id must be present
# in the install script.
resource_id = "%(id)s"

# The install script should be a json string
# containing a list which includes the
# resource instance for the driver being tested.
# It can use the following substitution variables:
#   deployment_home, hostname, username
_install_script = \"\"\"
[
]
\"\"\"

def get_install_script():
    return _install_script

# If the driver needs access to the password database, either for the sudo
# password or for passwords it maintains in the database, define this function.
# It should return a dict containing an required password entries, except for the
# sudo password which is added by the test driver. If you don't need the password
# database just comment out this function or have it return None.
def get_password_data():
    return {}
"""


def sanitize(s):
    """replace . and - with _"""
    return re.sub('[.-]', '_', s.replace(' ',''))

def resource_port_to_port_check(p):
    if p.port_type==rdef.Port.INPUT:
        name = "input_ports.%s" % p.name
    elif p.port_type==rdef.Port.OUTPUT:
        name = "output_ports.%s" % p.name
    else:
        name = "config_port"
    s = "    ctx.check_port('%s'" % name
    for pdef in p.properties.values():
        if isinstance(pdef.prop_type, list):
            typename = "list"
        elif isinstance(pdef.prop_type, dict):
            typename = "dict"
        elif rdef.prop_type_to_python_type.has_key(pdef.prop_type):
            typename = rdef.prop_type_to_python_type[pdef.prop_type].__name__
        else:
            typename = "unicode"
        s += ",\n                  %s=%s" % (pdef.name, typename)
    s += ")\n"
    return s
        
def generate_port_checks(res_name, res_version):
    key = {u"name":unicode(res_name), u"version":unicode(res_version)}
    with NamedTempFile() as f:
        layout_mgr = efl.get_engine_layout_mgr()
        main_rdef_file = os.path.abspath(os.path.expanduser(layout_mgr.get_resource_def_file()))
        ppr.preprocess_resource_file(main_rdef_file,
                                     layout_mgr.get_extension_resource_files(),
                                     f.name, logger)
        with open(f.name, "rb") as rf:
            g = rdef.create_resource_graph(json.load(rf))
            
    if not g.has_resource(key):
        raise Exception("Resource %s %s not found in resource definitions" %
                        (res_name, res_version))
    r = g.get_resource(key)
    if len(r.config_port.properties)>0:
        checks = resource_port_to_port_check(r.config_port)
    else:
        checks = ""
    for p in r.input_ports.values():
        checks += resource_port_to_port_check(p)
    for p in r.output_ports.values():
        checks += resource_port_to_port_check(p)
    return checks
            
        
        
def main(argv):
    try:
        parser = OptionParser(usage="\n%prog resourcekey version\nCreates a directory with a skeleton driver\n")
        parser.add_option("-t", "--generate-test", default=False,
                          action="store_true",
                          help="If specified, generate a drivertest.py file")
        parser.add_option("--service", default=False,
                          action="store_true",
                          help="If specified, the driver is for a service (will inherit from service_manager.Manager instead of resource_manager.Manager).")
        parser.add_option("--skip-port-checks", default=False,
                          action="store_true",
                          help="If specified, don't parse the resource definitions for generation of port checks")
        (options, args) = parser.parse_args(argv)
        keyname = args[0]
        versionname = args[1]

        if not options.skip_port_checks:
            port_checks = generate_port_checks(keyname, versionname)
        else:
            port_checks = ""
        if options.service:
            base_class = "service_manager"
            svc_methods = _svc_methods
        else:
            base_class = "resource_manager"
            svc_methods = ""
        dirname = sanitize(keyname) + '__' + sanitize(versionname) 
        target_dir = os.path.join(os.path.abspath("."), dirname)
        if os.path.exists(target_dir):
            parser.error("Directory %s already exists." % target_dir)
        os.mkdir(target_dir)
        print "generating __init__.py"
        f = open(os.path.join(target_dir, '__init__.py'), 'wb')
        f.close()
        print "generating driver.py"
        f = open(os.path.join(target_dir, 'driver.py'), 'wb')
        driver = skeleton.replace("%(key)s",
                                  keyname).replace("%(version)s",
                                                   versionname).replace("%(port_checks)s",
                                                                        port_checks).replace("%(baseclass)s",
                                                                                             base_class).replace("%(svcmethods)s", svc_methods)
        f.write(driver)
        f.close()
        print "generating packages.json"
        f = open(os.path.join(target_dir, 'packages.json'), "wb")
        f.write(packages_file_example)
        f.close()
        if options.generate_test:
            print "generating drivertest.py"
            f = open(os.path.join(target_dir, 'drivertest.py'), 'wb')
            f.write(drivertest_example % {"id":sanitize(keyname),
                                          "res_name":keyname,
                                          "res_version":versionname})
            f.close()
        return 0 
    except:
        raise

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

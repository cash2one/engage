"""Resource manager for sqlite3. 
"""

import commands
import engage.drivers.resource_manager as resource_manager

from engage.utils.user_error import UserError, ScriptErrInf
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("setuptools", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_SQLITE_PREINSTALL = 1
ERR_SQLITE_INSTALL = 2
ERR_SQLITE_POSTINSTALL = 3

define_error(ERR_SQLITE_PREINSTALL,
             _("preinstall for sqlite3 not supported"))
define_error(ERR_SQLITE_INSTALL,
             _("error sqlite3 installation not supported"))
define_error(ERR_SQLITE_POSTINSTALL,
             _("error sqlite3 not found"))

class Manager(resource_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
    
    def validate_pre_install(self):
	raise UserError(errors[ERR_SQLITE_PREINSTALL])

    def is_installed(self):
	return true

    def install(self, download_url):
	raise UserError(errors[ERR_SQLITE_INSTALL])


    def validate_post_install(self):
	if os.system('type sqlite3') != 0:	
		raise UserError(errors[ERR_SQLITE_POSTINSTALL])

"""
Mixins for resource managers that support creating shared resources. A
shared resource is a resource that is installed globally on the machine, may be used
simultaneously by independent genForma installs, and may used by subsequent installs
of a given app. Examples include apache, mysql, postgress, etc.
"""
import os.path
import json
import base64

from engage.utils.decorators import require_methods
import engage.utils.file as fileutils

import engage.utils.log_setup
logger = engage.utils.log_setup.setup_engage_logger(__name__)

from engage.drivers.action import *

import resource_metadata

from engage.utils.user_error import EngageErrInf, UserError, convert_exc_to_user_error

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_RESFILE_NOT_FOUND     = 1
ERR_RESFILE_PARSE         = 2
ERR_PW_NOT_FOUND          = 3

define_error(ERR_RESFILE_NOT_FOUND,
             _("Unable to find shared resource file %(file)s"))
define_error(ERR_RESFILE_PARSE,
             _("Unable to parse shared resource file %(file)s"))
define_error(ERR_PW_NOT_FOUND,
             _("Unable to find expected entry for password '%(pw)s' in resource file %(file)s"))


@make_value_action
def parse_resource_from_json(self, json_repr):
    return resource_metadata.parse_resource_from_json(json_repr)


@require_methods("_get_master_password", "_get_metadata_filedir", "_get_password_properties")
class SharedResourceWithPwDbMixin(object):
    """This mixin handles the storage of passwords needed for the
    installed resource. The following methods should be present on the
    instantiated class:
      * _get_master_password() - This usually comes from PasswordRepoMixin
      * _get_metadata_filedir() - Return the directory to store the metadata file
      * _get_password_properties() - Return a list of properties in the password repository
                                     corresponding to this resource

    The following data members must also be present:
        self.metadata (defined by resource_manager.Manager)
        self.install_context (defined by resource_manager.manager)
        self.ctx (defined by individual resource manager)
    """
    def _save_shared_resource_metadata(self):
        """Save the metadata corresponding to the resource instance. As a part
        of this process, we grade the associated password data, encrypt it,
        and store it in the metadata file. Since the metadata file contains
        this password data, we make it readable only by the root account.
        """
        assert self._get_master_password()!=None, "master password required to save shared resource metadata"
        pw_map = {}
        for pw_key in self._get_password_properties():
            pw_map[pw_key] = self.install_context.password_repository.get_value(pw_key)
        rmd = self.metadata
        from engage.utils.pw_repository import encrypt_object
        (ciphertext, salt) = encrypt_object(self._get_master_password(), pw_map)
        # we have to base64 encode the ciphertext because the json encoder
        # does not seem to handle the raw ciphertext correctly (not valid utf8)
        rmd.properties["pw_data"] = base64.b64encode(ciphertext)
        rmd.properties["pw_salt"] = salt
        target_path = self._get_metadata_filename()
        r = self.ctx.r
        with fileutils.NamedTempFile(data=json.dumps(rmd.to_json())) as tf:
            r(sudo_copy, [tf.name, target_path])
            r(sudo_set_file_permissions, target_path, 0, 0, 0400)
                                        
    def _load_shared_resource_password_entries(self):
        """Read the shared resource metadata file and store the associated password
        entries in the install context
        """
        r = self.ctx.r
        rv = self.ctx.rv
        if not self.ctx.dry_run:
            target_path = self._get_metadata_filename()
            r(check_file_exists, target_path)
            data = rv(sudo_cat_file, target_path)
            rmd = rv(parse_resource_from_json, json.loads(data))
            from engage.utils.pw_repository import decrypt_object
            ciphertext = base64.b64decode(rmd.properties['pw_data'])
            pw_map = decrypt_object(self._get_master_password(), rmd.properties['pw_salt'],
                                    ciphertext)
            for pw_key in self._get_password_properties():
                if not pw_map.has_key(pw_key):
                    raise UserError(errors[ERR_PW_NOT_FOUND],
                                    msg_args={"pw":pw_key, "file":target_path})
                self.install_context.password_repository.update_key(pw_key, pw_map[pw_key])
        else: # in dry run mode, we just add dummy passwords
            for pw_key in self._get_password_properties():
                self.install_context.password_repository.update_key(pw_key, "dummy pw")
                                     
    def _get_metadata_filename(self):
        return os.path.join(self._get_metadata_filedir(),
                            fileutils.mangle_resource_key(self.metadata.key) +
                            ".json")
                                    

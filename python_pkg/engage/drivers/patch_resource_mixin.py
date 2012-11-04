
import tempfile
import os
import os.path
import shutil

import resource_metadata
from engage_utils.process import run_and_log_program

class PatchInstallError(Exception):
    pass


class PatchResourceMixin(object):
    """This is a mixin class for resource managers which adds support for
    patching a resource during install. At the propriate point, the _has_patch()
    method should be called to see if a patch is available. If so,
    _install_patch() should then be called to apply the patch.

    The availablability of a patch is determined by the presence of the
    resource property patch_resource_key. This key should point to an
    entry in the software library containing the patch's archive file.

    This mixin requires the following members be present on the subclass:
      self.metadata     - instance of ResourceMD providing resource's metadata
      self.logger       - logger instance for the resource
      self.package_name - package name of the resource (for log messages)
      self.
    """
    def _has_patch(self):
        """Return true if a patch is available for this resource"""
        if self.metadata.properties.has_key(u"patch_resource_key"):
            return True
        else:
            return False
    
    def _install_patch(self, target_package_dir):
        assert self.metadata.properties.has_key(u"patch_resource_key")
        key = self.metadata.properties[u"patch_resource_key"]
        self.logger.debug("%s: Installing patch %s", self.package_name,
                          key.__repr__())
        patch_metadata = resource_metadata.ResourceMD(self.metadata.id + "-patch",
                                                      key)
        patch_entry = self.install_context.package_library.get_entry(patch_metadata)
        assert patch_entry != None
        package = patch_entry.get_package()
        assert package != None
        patch_parent_dir = tempfile.mkdtemp(key[u"name"])
        patch_dir = package.extract(patch_parent_dir)
        base_name = os.path.basename(patch_dir)
        assert base_name[-6:]=="-patch"
        # truncate -patch off directory name to get basename for patch file
        patchfile = base_name[0:-6] + ".diff"
        patch_file = os.path.join(patch_parent_dir,
                                  os.path.join(patch_dir, patchfile))
        if not os.path.exists(patch_file):
            raise PatchInstallError("Unable to find patch file %s" %
                                     patch_file)
        if not (os.path.exists(target_package_dir) and
                os.path.isdir(target_package_dir)):
            raise PatchInstallError("Unable to find target package directory %s" %
                                     target_package_dir)
        cmd = ["/usr/bin/patch", "-p1", "-i", patch_file]
        rc = run_and_log_program(cmd, {}, self.logger, cwd=target_package_dir)
        if rc != 0:
            raise PatchInstallError("Error in running patch")
        shutil.rmtree(patch_parent_dir)
        self.logger.info("Applied patch to %s" % self.package_name)

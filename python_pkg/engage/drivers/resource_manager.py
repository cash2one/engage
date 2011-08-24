#
# This is the runtime API used for managing resources
#


class UndefinedMethod(Exception):
    """Exception to indicate that a method wasn't overridden. We require
    that all manager methods be overridden, except for is_installed() and
    is_server(). Temporarily this isn't the case for patch, uninstall, etc.,
    which are experimental methods.
    """
    def __init__(self, resource_mgr, method):
        Exception.__init__(self, "%s.%s.%s" %
                           (resource_mgr.__module__,
                            resource_mgr.__class__.__name__,
                            method))


class Manager(object):
    """Base class for all resource managers. Each resource manager should be
    implemented in its own module and provide a class Manager, which is
    dynamically loaded. The constructor must accept one parameter:
    the metadata for the resource.
    """
    def __init__(self, metadata, package_name):
        """metadata should be an instance of ResourceMD. package_name should
        be a short name describing the package. Usually, this is done by
        extracting information from the resource key (e.g. name and version).
        """
        self.metadata = metadata
        self.id = self.metadata.id
        self.package_name = package_name
        self.install_context = None # to be set by sequencer

    def validate_pre_install(self):
        """Should throw an exception if there is a problem in
        the configuration that would prevent an install (e.g. target
        directory does not exist or is not writable). We separate this from the
        install() method so that it can be called as early as possible in
        the overall deployment. Should not change any state.

        This should NOT be called if we aren't doing the install -- some of
        the checks may only be valid if we are install the software (e.g.
        checking that target dir is writable).
        """
        raise UndefinedMethod(self, "validate_pre_install")

    def is_installed(self):
        return self.metadata.is_installed()

    def install(self, library_package):
        raise UndefinedMethod(self, "install")

    def validate_post_install(self):
        """Validate that the install is correct. Called if the package
        is already installed and we want to see if it is really setup
        correctly. Should throw an exception if there is a
        problem with the install. Should not change any state.

        This is not called explicitly by sequencer after install() -- we assume
        that install() will do its own sanity checks (perhaps by just
        calling this function).
        """
        raise UndefinedMethod(self, "validate_post_install")

    def patch(self, new_metadata):
        """Patch a package according to the new metadata.
        """
        pass


    def backup(self, backup_to_directory, compress=True):
        """Backup the files and other data for this resource
        to a unique filename or sub-directory under the
        specified directory. The resource should then be
        restorable via the restore() method.
        
        The compress flag is just a hint about whether we are more
        concerned about space vs. time.
        """
        print "backup called for %s" % self.id # XXX

    def uninstall(self, backup_to_directory, incomplete_install=False, compress=True):
        """Uninstall the resource, moving the files and other
        data for this resource to a unique filename or sub-directory under
        the specified directory. The format used should be compatible with
        the restore() method.

        If incomplete_install is True, then the install of this resource
        failed and the uninstall() method should not fail if the data to
        be backed up is incomplete. Of course, in this situation, it is not
        required to be able to restore() the resource to a functional state.

        The compress flag is just a hint about whether we are more
        concerned about space vs. time.
        """
        pass

    def restore(self, backup_to_directory, package):
        """Restore this resource, whose backup data was
        stored under backup_to_directory via either backup()
        or uninstall()
        """
        pass

    def upgrade(self, package, old_metadata, backup_root_directory):
        """Upgrade the specified resource. old_metadata is the ResourceMD
        object corresponding to the previous version of the resource instance.
        backup_root_directory is the directory to which the previous version
        was uninstalled to.

        Default implementation is just to reinstall, if not present."""
        if not self.is_installed():
            self.install(package)
        
    def is_service(self):
        return False
            
    def can_be_install_target(self):
        """Returns True if this resource manager can be an install target.
        If so, it must support the methods use_as_install_target(),
        get_genforma_home(), and move_config_data_to_targets().
        See install_target_resource.py for details.
        """
        return False

from engage.utils.process import is_running_as_root

class PasswordRepoMixin(object):
    """This is a mixin for resource managers which provides shortcuts for
       accessing the password repository. These functions should not be
       called from the resource manager's constuctor, as the install_context
       member is not initialized until later.
    """
    def _get_sudo_password(self):
        """To access the sudo password, the resource definition must have an
        input port called "host" with a "sudo_password" property. This property
        is just an entry name into the password database. Usually, this
        requirement is satisified by having an inside constraint on the host
        machine.
        """
        if not is_running_as_root():
            return \
                   self.install_context.password_repository.get_value(
                       self.metadata.input_ports['host']['sudo_password'])
        else:
            # If running as root, we don't need a password. run_sudo_program()
            # is smart enough to figure that out and just run the command directly.
            # We always return None, even if there is an associated value in the pw
            # database, because we want sudo commands run directly.
            return None

    def _get_master_password(self):
        """The master password is just the sudo password. However, in the event
        that we are running as root, we still return the password.
        """
        key = self.metadata.input_ports["host"]["sudo_password"]
        if self.install_context.password_repository.has_key(key):
            return self.install_context.password_repository.get_value(key)
        else:
            return None

    def _get_password(self, pw_key):
        """Convenience function to get passwords out of the pw repository
        """
        return self.install_context.password_repository.get_value(pw_key)

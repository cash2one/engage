"""This is the runtime API used for managing services
"""

import resource_manager

from engage.utils.log_setup import setup_engine_logger

logger = None

def get_logger():
    global logger
    if logger == None:
        logger = setup_engine_logger(__name__)
    return logger


class Manager(resource_manager.Manager):
    def __init__(self, metadata, package_name):
        resource_manager.Manager.__init__(self, metadata, package_name)

    def is_service(self):
        return True

    def start(self):
        """Startup the service. This should validate that the service was
        indeed started.
        """
        pass

    def stop(self):
        pass

    def force_stop(self):
        """The default implementation of force_stop() is to
        call stop() and swallow any exceptions. All implementations
        should return True if successful, False otherwise.
        """
        try:
            self.stop()
            return True
        except Exception, e:
            get_logger().error("Force stop of resource %s did not succeed: %s" % (self.id, e))
            return False
            
    def is_running(self):
        return False # need to override

    def get_pid_file_path(self):
        """Method to return the path to the pid file for an installed service.
        If there is no pid file for this service, just return None. This is
        used by management tools (e.g. monit) to monitor the service.xs
        """
        return None

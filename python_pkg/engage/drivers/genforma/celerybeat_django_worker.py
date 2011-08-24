import os.path
import engage.drivers.genforma.django_worker_driver as django_worker_driver

import engage.utils.log_setup
logger = engage.utils.log_setup.setup_engage_logger(__name__)

class Manager(django_worker_driver.Manager):
    def __init__(self,metadata,config=None):
        django_worker_driver.Manager.__init__(self,metadata,config)

    def start(self):
        logger.info('Starting celerybeat')
        self.start_worker('celerybeat', [])
    def stop(self):
        self.stop_worker('celerybeat')

    def force_stop(self):
        self.force_stop_worker('celerybeat')

    def is_running(self):
        return self.is_running_worker('celerybeat') 

    def get_pid_file_path(self):
        return os.path.join(self.config.input_ports.django.log_directory, 'celerybeat.pid') 

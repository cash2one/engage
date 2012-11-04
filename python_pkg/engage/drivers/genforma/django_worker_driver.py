"""Service manager base class for managing background tasks 
run through the django management class.
Examples are celeryd and celerybeat and gearman. 

This class should be subclassed by each worker. The subclass'
start routine simply calls start_worker with the name of the management
command.
The start_worker method starts the workers.
"""

import os
import os.path
import string
import time
import json

import engage.drivers.service_manager as service_manager
import engage.drivers.resource_metadata as resource_metadata
from engage.drivers.genforma.django_file_layout import create_file_layout_from_json
import engage.utils.log_setup
import engage_utils.process as iuprocess


from engage.utils.user_error import ScriptErrInf, UserError
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info

ERR_NO_DJANGO_LAYOUT_FILE = 1



define_error(ERR_NO_DJANGO_LAYOUT_FILE,
             _("Django layout file %(file)s not found"))



#####################################################################

def get_packages_filename():
    return engage.drivers.utils.get_packages_filename(__file__)

# define the configuration data used by the resource instance
_config_type = {
  "input_ports": {
    "django": {
      "home": unicode,
      "log_directory": unicode,
      "layout_cfg_file": unicode
    },
    "python": {
      "PYTHONPATH": unicode,
      "home": unicode
    }
  }
}

logger = engage.utils.log_setup.setup_engage_logger(__name__)



class Config(resource_metadata.Config):
    def __init__(self, props_in, types, id, package_name):
        resource_metadata.Config.__init__(self, props_in, types)
        #self._add_computed_prop("worker_logfile",
        #                        os.path.join(self.input_ports.django.log_directory,
        #                                     "gearman_worker.log"))
        #self._add_computed_prop("worker_pidfile",
        #                        os.path.join(self.input_ports.django.home,
        #                                     "gearman_worker.pid"))



class Manager(service_manager.Manager):
    def __init__(self, metadata, config=None):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        self.config = metadata.get_config(_config_type, Config, self.id,
                                          package_name)

    def validate_pre_install(self):
        pass

    def is_installed(self):
        return True # nothing to do for install

    def install(self, pkg):
        pass

    def validate_post_install(self):
        pass

    def start(self):
        assert False, 'start should be overridden in subclass'
    def stop(self):
        assert False, 'stop should be overridden in subclass'
    def force_stop(self):
        assert False, 'force_stop should be overridden in subclass'
    def is_running(self, worker):
        assert False, 'is_running should be overridden in subclass'
    
    def start_worker(self, worker, options):
        if not os.path.exists(self.config.input_ports.django.layout_cfg_file):
            raise UserError(errors[ERR_NO_DJANGO_LAYOUT_FILE],
                            msg_args={"file":self.config.input_ports.django.layout_cfg_file})
        with open(self.config.input_ports.django.layout_cfg_file, "rb") as f:
            dfl = create_file_layout_from_json(json.load(f))
        logfile = os.path.join(self.config.input_ports.django.log_directory, worker + '.log') 
        pidfile = os.path.join(self.config.input_ports.django.log_directory, worker + '.pid') 
        dfl.run_admin_command_as_background_task(worker, options,
                                                 logfile,
                                                 pidfile)
        
        logger.info("%s worker instance %s started successfully" %
                    (worker, self.id))


    def stop_worker(self, worker):
        pidfile = os.path.join(self.config.input_ports.django.log_directory, worker + '.pid') 
        iuprocess.stop_server_process(pidfile,
                                      logger, self.id)

    def force_stop_worker(self, worker):
        pidfile = os.path.join(self.config.input_ports.django.log_directory, worker + '.pid') 
        try:
            iuprocess.stop_server_process(pidfile,
                                          logger, self.id, force_stop=True)
        except Exception, e:
            get_logger().error("Force stop of resource %s did not succeed: %s" % (self.id, e))
            
    def is_running_worker(self, worker):
        pidfile = os.path.join(self.config.input_ports.django.log_directory, worker + '.pid') 
        return iuprocess.check_server_status(pidfile, logger, self.id)!=None

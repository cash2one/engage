"""Plugin framework for registering installed resources with management tools.

All backends are in the engage.mgt_backends package. A backend should provide
a register function with the following signature:
  register(mgt_info, sudo_password=None, upgrade=False)
"""
import os.path
from itertools import ifilter

import fixup_python_path
import engage.utils.file as fileutils
import engage.engine.install_plan as install_plan
from engage.mgt_backends.mgt_info import ServiceInfo, ManagementInfo
from engage.utils.log_setup import setup_engage_logger
logger = setup_engage_logger(__name__)


def validate_backend_names(backend_names, parser):
    """Check that the management backend is valid. Call the
    error method on the option parser if there is a problem.
    """
    backends = backend_names.split(",")
    for backend in backends:
        if backend=="mgt_info":
            parser.error("'mgt_info' is not a valid management backend")
        module_name = "engage.mgt_backends." + backend
        try:
            m = fileutils.import_module(module_name)
        except ImportError:
            parser.error("Management backend '%s' not found" % backend)
        if not hasattr(m, "register"):
            parser.error("Management backend module %s found, but is missing register function" % module_name)


def register_with_mgt_backends(backend_names, manager_list,
                               deployment_home,
                               sudo_password=None,
                               upgrade=False):
    svc_id_set = set() # set of all service ids
    svc_list = [] # list of managers that are services, in dependency order
    resource_list = [] # list of all resources, including services and non-services
    for mgr in manager_list:
        resource_list.append(mgr.metadata)
        if mgr.is_service():
            svc_list.append(mgr)
            svc_id_set.add(mgr.metadata.id)
    dependencies = install_plan.get_resource_dependencies(resource_list)
    service_info = []
    for svc in svc_list:
        service_info.append(ServiceInfo(svc.metadata.id,
                                        svc.package_name,
                                        # we only include dependencies that are
                                        # services
                                        [sid for sid in
                                         ifilter(lambda sid: sid in svc_id_set,
                                                 dependencies[svc.metadata.id])],
                                        svc.get_pid_file_path()))
    mgt_info = ManagementInfo(deployment_home,
                              os.path.join(deployment_home, "engage/bin/svcctl"),
                              service_info)
    backends = backend_names.split(",")
    for backend in backends:
        logger.info("Registering with management backend '%s'" % backend)
        module_name = "engage.mgt_backends." + backend
        m = fileutils.import_module(module_name)
        m.register(mgt_info, sudo_password=sudo_password, upgrade=upgrade)
                              

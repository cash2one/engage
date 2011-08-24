"""Classes for representing system management information.
"""
import json
from itertools import ifilter

class ServiceInfo(object):
    """Management information about a service:
    resource_id:   id for this resource
    resource_type: usually the package name and version
    dependencies:  list of other resource ids this service depends on (directly)
    pidfile:       path to pid file or None if not available.
    """
    def __init__(self, resource_id, resource_type, dependencies, pidfile=None):
        self.resource_id = resource_id
        self.resource_type = resource_type
        self.dependencies = dependencies
        self.pidfile = pidfile

    def to_json(self):
        return {"resource_id":self.resource_id,
                "resource_type":self.resource_type,
                "dependencies":self.dependencies,
                "pidfile":self.pidfile}
    
    def __str__(self):
        return json.dumps(self.to_json())
        

class ManagementInfo(object):
    """Overall management information, including all the services.

    >>> s1 = ServiceInfo("s1", "s1", [], pidfile=None)
    >>> s2 = ServiceInfo("s2", "s2", ["s1"], pidfile="/var/run/s2.pid")
    >>> s3 = ServiceInfo("s3", "s3", ["s1", "s2"], pidfile=None)
    >>> s4 = ServiceInfo("s4", "s4", ["s1", "s2", "s3"], pidfile="/var/run/s4.pid")
    >>> mi = ManagementInfo("~/apps", "~/apps/engage/bin/svcctl", [s1,s2,s3,s4])
    >>> print mi
    {
      "services": [
        {
          "dependencies": [], 
          "pidfile": null, 
          "resource_type": "s1", 
          "resource_id": "s1"
        }, 
        {
          "dependencies": [
            "s1"
          ], 
          "pidfile": "/var/run/s2.pid", 
          "resource_type": "s2", 
          "resource_id": "s2"
        }, 
        {
          "dependencies": [
            "s1", 
            "s2"
          ], 
          "pidfile": null, 
          "resource_type": "s3", 
          "resource_id": "s3"
        }, 
        {
          "dependencies": [
            "s1", 
            "s2", 
            "s3"
          ], 
          "pidfile": "/var/run/s4.pid", 
          "resource_type": "s4", 
          "resource_id": "s4"
        }
      ], 
      "deployment_home": "~/apps", 
      "svcctl_exe": "~/apps/engage/bin/svcctl"
    }
    >>> mi2 = mi.with_only_pidfile_services()
    >>> print mi2
    {
      "services": [
        {
          "dependencies": [], 
          "pidfile": "/var/run/s2.pid", 
          "resource_type": "s2", 
          "resource_id": "s2"
        }, 
        {
          "dependencies": [
            "s2"
          ], 
          "pidfile": "/var/run/s4.pid", 
          "resource_type": "s4", 
          "resource_id": "s4"
        }
      ], 
      "deployment_home": "~/apps", 
      "svcctl_exe": "~/apps/engage/bin/svcctl"
    }
    
    """
    def __init__(self, deployment_home, svcctl_exe, services):
        self.deployment_home = deployment_home
        self.svcctl_exe = svcctl_exe
        self.services = services

    def to_json(self):
        return {"deployment_home":self.deployment_home,
                "svcctl_exe": self.svcctl_exe,
                "services": [svc.to_json() for svc in self.services]}

    def __str__(self):
        return json.dumps(self.to_json(), indent=2)

    def with_only_pidfile_services(self):
        """Return another ManagementInfo object that only
        includes services which have a pidfile. The tricky part
        is that we need to filter out non-pidfile dependencies as well.
        """
        include_set = set([svc.resource_id for svc in ifilter(lambda s:s.pidfile!=None, self.services)])
        pidfile_services = [ServiceInfo(s.resource_id, s.resource_type,
                                        [sid for sid in ifilter(lambda sid:sid in include_set, s.dependencies)],
                                        s.pidfile)
                            for s in ifilter(lambda s:s.resource_id in include_set, self.services)]
        return ManagementInfo(self.deployment_home, self.svcctl_exe,
                              pidfile_services)

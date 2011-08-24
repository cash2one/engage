"""Functionality related to the preprocessing of resource definitions proir to handing
them to the config engine.
"""

import os
import os.path
import json
from itertools import ifilter


def preprocess_resource_file(primary_resource_file, extension_resource_files,
                             target_resource_file, logger,
                             drivers_dir=os.path.abspath(
                                             os.path.join(os.path.dirname(__file__),
                                                          "../drivers"))):
    """Combine primary resource file with extension resource files and any resource
    files from individual drivers, generating target_resource_file. Resource files for
    individual drivers will be in grandchild directories of engage.drivers and will be
    named resources.json
    (e.g. engage/drivers/standard/foo__1_0/resources.json for the foo 1.0 resources).

    Extension and driver-specific resource files can either be a list of resource
    definitions or can be a dict containig a resource_definitions property.
    """
    with open(primary_resource_file, "rb") as prf:
        resource_file = json.load(prf)
    resources = resource_file['resource_definitions']
    assert isinstance(resources, list)

    def add_resources_in_file(res_file):
        if os.path.exists(res_file):
            logger.debug("Adding resources from %s/%s to master file." %
                         (os.path.basename(os.path.dirname(res_file)),
                          os.path.basename(res_file)))
            with open(res_file, "rb") as rf:
                driver_resources = json.load(rf)
            if isinstance(driver_resources, list):
                resources.extend(driver_resources)
            elif isinstance(driver_resources, dict) and \
                 driver_resources.has_key('resource_definitions'):
                resources.extend(driver_resources['resource_definitions'])
            else:
                raise Exception("Invalid format for resource file %s" % ref_file)

    for f in extension_resource_files:
        add_resources_in_file(f)
    resource_group_dirs = ifilter(lambda f: \
                                      os.path.isdir(os.path.join(drivers_dir, f)) and \
                                      f!='genforma' and f!='data',
                                  os.listdir(drivers_dir))
    for group_dir in resource_group_dirs:
        group_path = os.path.join(drivers_dir, group_dir)
        for f in os.listdir(group_path):
            add_resources_in_file(os.path.join(os.path.join(group_path, f),
                                               "resources.json"))
    new_resource_file = {"resource_def_version":resource_file['resource_def_version'],
                         "resource_definitions":resources}
    with open(target_resource_file, "wb") as trf:
        json.dump(new_resource_file, trf)
                                  

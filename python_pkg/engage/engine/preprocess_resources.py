"""Functionality related to the preprocessing of resource definitions and instances
proir to handing them to the config engine.
"""

import os
import os.path
import json
from itertools import ifilter
import copy

import gettext
_ = gettext.gettext

# fix path if necessary (if running from source or running as test)
import fixup_python_path

from engage.utils.user_error import UserError, EngageErrInf, convert_exc_to_user_error

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = EngageErrInf(__name__, error_code, msg)
    errors[error_info.error_code] = error_info


ERR_SPEC_VALIDATION = 1

define_error(ERR_SPEC_VALIDATION,
             _("Error in validation of resource spec %(file)s: %(msg)s"))


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
        json.dump(new_resource_file, trf, indent=2)
                                  

def parse_raw_install_spec_file(filename):
    """Parse the un-preprocessed install spec file and find the dynamic hosts.
    Returns the parsed json list.
    """
    with open(filename, "rb") as f:
        json_data = json.load(f)
    if not isinstance(json_data, list):
        raise Exception("Invalid format for install spec file %s: expecting a list of resources" % filename)
    return json_data

def query_install_spec(spec, **kwargs):
    """The keyword args should contain key/value pairs to machine instance keys
    against (currently, keys contain only 'name' and 'version' properties). Any matching
    instances are returned.
    """
    results = []
    for inst in spec:
        key = inst["key"]
        matches = True
        for arg in kwargs.keys():
            if (not key.has_key(arg)) or (key[arg] != kwargs[arg]):
                matches = False
                break
        if matches:
            results.append(inst)
    return results

def fixup_installed_resources_in_install_spec(json_data, inst_list):
    """Given a parsed raw install spec file and a list of resource instances to
    update in the spec, fixup the
    install spec to include the desired
    resource instances, replacing any existing entries or adding if necessary.
    Also fixup any references to the resources in the inside, environment, and peer
    links.
    """
    data = copy.deepcopy(json_data)
    # create a mapping from instance ids to indices
    id_to_idx = {}
    for i in range(len(data)):
        id_to_idx[data[i]["id"]] = i
        
    # replace or add the instances
    updated_insts = set()
    for inst in inst_list:
        updated_insts.add(inst["id"])
        if id_to_idx.has_key(inst["id"]):
            data[id_to_idx[inst["id"]]] = inst
        else:
            new_idx = len(data)
            data.append(inst)
            id_to_idx[inst["id"]] = new_idx

    # get the keys of the modified instances
    id_to_key = {}
    for inst_id in updated_insts:
        id_to_key[inst_id] = data[id_to_idx[inst_id]]["key"]
            
    # fix any keys in references to the updated resources
    for idx in range(len(data)):
        inst = data[idx]
        if inst.has_key("inside"):
            inst_ref = inst["inside"]
            if inst_ref["id"] in updated_insts:
                inst_ref["key"] = id_to_key[inst_ref["id"]]
        if inst.has_key("environment"):
            assert isinstance(inst["environment"], list)
            for inst_ref in inst["environment"]:
                if inst_ref["id"] in updated_insts:
                    inst_ref["key"] = id_to_key[inst_ref["id"]]
        if inst.has_key("peers"):
            assert isinstance(inst["peers"], list)
            for inst_ref in inst["peers"]:
                if inst_ref["id"] in updated_insts:
                    inst_ref["key"] = id_to_key[inst_ref["id"]]                
    return data


def validate_install_spec(install_spec_file):
    with open(install_spec_file, "rb") as f:
        spec = json.load(f)
    used_ids = set()
    for inst in spec:
        if inst["id"] in used_ids:
            raise UserError(errors[ERR_SPEC_VALIDATION],
                            msg_args={"msg":"Resource id %s used multiple times" %
                                      inst["id"],
                                      "file":install_spec_file})
        used_ids.add(inst["id"])
        

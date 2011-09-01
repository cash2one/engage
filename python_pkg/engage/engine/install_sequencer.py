#
# Run a sequence of resource install steps
#

import os
import os.path
import sys
import json

import fixup_python_path

from engage.utils.log_setup import setup_engine_logger
import install_context
import engage.utils.process

#from provision.deploy import parser, deploy
#from provision.config import reconfig

logger = None

def get_logger():
    global logger
    if logger == None:
        logger = setup_engine_logger(__name__)
    return logger

from engage.utils.user_error import InstErrInf, UserError

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = InstErrInf("Sequencer", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_NO_ENTRY_FOR_RESOURCE_INST   = 1
ERR_NO_PACKAGE_FOR_RESOURCE_INST = 2
ERR_NO_INSTALL_TARGET_RESOURCE   = 3

define_error(ERR_NO_ENTRY_FOR_RESOURCE_INST,
             _("Unable to find matching entry in library for resource instance %(inst)s"))
define_error(ERR_NO_PACKAGE_FOR_RESOURCE_INST,
             _("Unable to find matching package for resource instance %(inst)s, of type %(name)s %(ver)s"))
define_error(ERR_NO_INSTALL_TARGET_RESOURCE,
             _("No resource has been specified as the install target."))


def get_manager_and_package(instance_md, library):
    entry = library.get_entry(instance_md)
    if entry==None:
        raise UserError(errors[ERR_NO_ENTRY_FOR_RESOURCE_INST],
                        {"inst": instance_md.id})
    resource_manager_class = entry.get_manager_class()
    resource_manager = resource_manager_class(instance_md)
    resource_manager.install_context = install_context
    ## JF 2011-07-8: We previously were checking whether the
    ## resource was installed and then only obtaining the package
    ## if the resource wasn't present. However, we should not call
    ## is_installed() for a resource until we know that all dependent
    ## resources are installed (and running if a service). This is
    ## because the is_installed() check may require a dependent resource.
    ## For example, a mysql connector may require mysql to be installed and
    ## running to create a database and user. Thus, always return the
    ## package here and defer the installation check until run_install()
    ## below. If, for some reason, getting the package manager for an installed
    ## resource causes a problem, then we'll have to revisit.
    ##
    ## if resource_manager.is_installed():
    ##     ## resource_manager.validate_post_install()
    ##     package = None
    ## else:
    ##     resource_manager.validate_pre_install()
    if True:
        package = entry.get_package()
        ## It is ok if we don't have a package at this point. If we
        ## find that the resource is NOT installed, then we need
        ## to have a package.
        ## if package == None:
        ##     raise UserError(errors[ERR_NO_PACKAGE_FOR_RESOURCE_INST],
        ##                     {"inst": instance_md.id})
    return (resource_manager, package)


def get_install_target_mgr(mgr_pkg_list):
    for (mgr, pkg) in mgr_pkg_list:
        if mgr.can_be_install_target() and mgr.use_as_install_target():
            return mgr
    # if we get here, didn't find install target
    raise UserError(errors[ERR_NO_INSTALL_TARGET_RESOURCE],
                    developer_msg="Exactly one resource instance must have the property use_as_install_target set. This is usually the resource corresponding to the physical machine.")


def run_install(mgr_pkg_list, library, force_stop_on_error=False):
    install_target_mgr = get_install_target_mgr(mgr_pkg_list)
    undo_list = []
    try:
        for (mgr, pkg) in mgr_pkg_list:
            get_logger().info("Processing resource '%s'." % mgr.id)
            if mgr.is_installed():
                mgr.validate_post_install()
                # we force the installed_bit to true
                mgr.metadata.set_installed()
                get_logger().info("Resource %s already installed." % mgr.package_name)
            else:
                if pkg == None:
                    raise UserError(errors[ERR_NO_PACKAGE_FOR_RESOURCE_INST],
                                    {"inst": mgr.metadata.id, "name":mgr.metadata.key.name,
                                     "ver":mgr.metadata.key.version})
                mgr.validate_pre_install()
                mgr.install(pkg)
                mgr.metadata.set_installed()
                get_logger().info("Install of %s successful." % mgr.package_name)
            if mgr.is_service():
                undo_list.append(mgr)
                if mgr.is_running():
                    get_logger().info("Service %s already running." % mgr.package_name)
                else:
                    mgr.start()
                    get_logger().info("Service %s started successfully." % mgr.package_name)
        install_target_mgr.write_resources_to_file([mgr for (mgr, pkg) in mgr_pkg_list])
        get_logger().info("Install completed successfully.")
    except Exception, e:
        if not force_stop_on_error:
            raise # leave in the error state
        else:
            logger.error("Got exception: %s, will attempt to force stop all services" % e)
            undo_list.reverse()
            for mgr in undo_list:
                get_logger().info("Attempting to force stop resource %s" % mgr.id)
                mgr.force_stop()
            raise

GF_BASE_DIR = '/tmp/genforma/'
FABRIC_EXE = 'fab'

class FakeServer:
    def __init__(self, id=0, private_ip=0, public_ip=0):
        self.id = id
        self.private_ip = private_ip
        self.public_ip = public_ip

def _provision_machine(m, library):
    provision_args = ["-i", "karmic", "-n", m.id, "-d", desc_file] 
    get_logger().info('Calling provision engine')
    try:
        parsed = provision.config.reconfig(provision.deploy.parser, provision_args)
        node = provision.deploy.deploy(parsed)
    except Exception, e:
        raise 
    get_logger().info('Machine %s has been provisioned' % node)
    return node 

def run_multi_node_install(multi_node_install_plan, library, dev_mode=True, force_stop_on_error=False):
    machines = { }
    if dev_mode:
        # do not provision servers, but create a subdirectory for each node
        for machine_install_plan in multi_node_install_plan:
            mpath = os.path.join(GF_BASE_DIR, machine_install_plan[0].id)
            os.mkdir(mpath)
            machines[machine_install_plan[0].id] =  FakeServer(id=id, private_ip=mpath, public_ip=id)
    else: # production mode
        try:
            for machine_install_plan in multi_node_install_plan:
                assert(len(machine_install_plan) > 0)
                node = _provision_machine(machine_install_plan[0], library)
                machines[machine_install_plan[0].id] = node
        except:
            get_logger().exception('Provision failed. Destroying provisioned nodes.')
            for m in machines.values():
                retcode = m.destroy()
                assert retcode, "Destroying node %s returned false" % m.__repr__()
            raise
    get_logger().info("Provisioning done. Ready to bootstrap and call setup_install") 
    for (m,node) in machines.items():
        print "id=%s node=(%s,%s)" % (m, node.id, node.private_ip)
    if dev_mode:
        for machine_install_plan in multi_node_install_plan:
            m = machines[machine_install_plan[0].id]
            # run bootstrap in the directory
            retcode = engage.utils.process.run_and_log_program(['python', 'bootstrap.py', m.private_ip], logger=get_logger())
            resources = [r.to_json() for r in machine_install_plan ]
            fp = open(os.path.join(m.private_ip, 'install.script'), "wb")
            json.dump(resources, fp, sort_keys=True, indent=2)
            fp.close()
            # run install script in each directory 

    else:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        for (m,machine_install_plan) in zip(machines.values(), multi_node_install_plan):
            try:
                ssh.connect(m.private_ip, username=username)
            except:
                get_logger().exception("Connection to machine %s did not succeed" % m.private_ip)
                raise
            sftp = ssh.open_sftp()
            sftp.put(bootstrap_script, bootstrap_script) 
            resources = [r.to_json() for r in machine_install_plan ]
            installscript = json.dumps(resources, sort_keys=True, indent=2)
            sftp.put(installscript, install_script)
            stdin, stdout, stderr = ssh.exec_command('bootstrap.py')
            stdin, stdout, stderr = ssh.exec_command('install installscript')
            # do error handling
            ssh.close()

def test_multi_node():
    import engage.drivers.resource_metadata as resource_metadata
    r1_key = {"name":"r1_type"}
    r2_key = {"name":"r2_type"}
    r3_key = {"name":"r3_type"}
    r4_key = {"name":"r4_type"}
    r5_key = {"name":"r5_type"}
    r1 = resource_metadata.ResourceMD("r1", r1_key)
    r2 = resource_metadata.ResourceMD("r2", r2_key,
            inside=resource_metadata.ResourceRef("r1", r1_key))
    r3 = resource_metadata.ResourceMD("r3", r3_key,
            inside=resource_metadata.ResourceRef("r1", r1_key),
            peers=[resource_metadata.ResourceRef("r2", r2_key)])
    r4 = resource_metadata.ResourceMD("r4", r4_key,
            inside=resource_metadata.ResourceRef("r1", r1_key),
            environment=[resource_metadata.ResourceRef("r3", r3_key)])
    r5 = resource_metadata.ResourceMD("r5", r5_key,
            peers=[resource_metadata.ResourceRef("r2", r2_key)])
    print "ready to import install_plan" # XXXX
    import install_plan
    plan = install_plan.create_multi_node_install_plan([r2, r5, r3, r4, r1])
    for m in plan:
        print m
    library = None
    run_multi_node_install(plan, library)

if __name__ == '__main__':
    test_multi_node()

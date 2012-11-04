"""Management backend for monit"""

import os
import shutil
import engage_utils.process as iuprocess
import engage.utils.file as iufile
import engage.utils.log_setup
import engage.utils.system_info as iusysinfo

logger = engage.utils.log_setup.setup_script_logger(__name__)

monit_exe = '/bin/monit'
if iusysinfo.get_platform() == 'macosx64':
    monit_exe = '/opt/local/bin/monit'

template = \
"""
check process %(processname)s with pidfile %(pidfile)s
  start program = "%(svcctl)s start %(processname)s" with timeout 60 seconds
  stop  program = "%(svcctl)s stop %(processname)s"
  %(dependencies)s"""

def generate_monitrc(svcctl_exe, svc):
    if svc.dependencies == []:
        dependencies = ''
    else:
        dependencies = 'depends on ' + ','.join(svc.dependencies)
    monitor = template % { 'processname' : svc.resource_id,
                 'pidfile'     : svc.pidfile,
                 'dependencies' : dependencies, 
                 'svcctl'       : svcctl_exe
               }
    return monitor
    
def register(mgt_info, sudo_password=None, upgrade=False):
    mgt_info = mgt_info.with_only_pidfile_services()
    # first copy the monitrc.template to deployment_home
    monit_substitutions = {
       'monitinterval' : 120, 
       'monitstartdelay' : 60, 
       'monitlogfile'    : os.path.join(mgt_info.deployment_home, 'log/monit.log'),
       'monitemailalertsto' : 'admin@genforma.com',
       'monithost' : 'localhost',
       'monitadmin' : 'admin',
       'monitadminpassword' : 'engage_monit'
    }
    monitrc_template_file = os.path.join(os.path.dirname(__file__), 'data/monitrc.template')
    monitrc_file = os.path.join(mgt_info.deployment_home, 'monitrc') 
    iufile.instantiate_template_file(monitrc_template_file, monitrc_file, monit_substitutions)
    with open(monitrc_file, 'a') as f:
        for svc in mgt_info.services:
            monitor = generate_monitrc(mgt_info.svcctl_exe, svc)
            f.write(monitor)
    os.chmod(monitrc_file, 0600)
    # now start monit
    iuprocess.run_and_log_program(
        [monit_exe, 
         '-c', monitrc_file], 
        {}, logger)
    print 'monit started'

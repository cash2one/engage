"""Service manager for mysql 5.1.39
"""
import os
import os.path
import shutil
import sys
import time
import tempfile
import stat

import engage.drivers.service_manager as service_manager
import engage.utils.path as iupath
import engage.utils.process as iuprocess
import engage.utils.http as iuhttp
import engage.utils.log_setup
import engage.utils.file as iufile
import engage.utils.timeout as iutimeout
import engage.engine.install_context as install_context
import xml.etree.ElementTree as et

logger = engage.utils.log_setup.setup_script_logger("MySQL5.1.39")

from engage.utils.user_error import ScriptErrInf, UserError, convert_exc_to_user_error

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("MySQL", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_MYSQL_QUERY          = 1
ERR_SECURE_EXC           = 2
ERR_STARTUP              = 3
ERR_CONFIG_FILE          = 4
ERR_SETUP_SCRIPT         = 5
ERR_MYSQLD_START         = 6
ERR_MYSQL_NO_RESPONSE    = 7
ERR_POST_CONFIG_SHUTDOWN = 8
ERR_NO_INSTALL_DIR       = 9
ERR_MYSQL_BUILD          = 10

define_error(ERR_MYSQL_QUERY,
             _("Error in running query against MySQL, return code was %(rc)d"))
define_error(ERR_SECURE_EXC,
             _("Error in securing MySQL installation"))
define_error(ERR_STARTUP,
             _("Error in starting MySQL server, return code was %(rc)d"))
define_error(ERR_CONFIG_FILE,
             _("Unable to configure MySQL: file %(file)s contents not as expected"))
define_error(ERR_SETUP_SCRIPT,
             _("Unable to configure MySQL: error in running setup script '%(script)s', return code was %(rc)d"))
define_error(ERR_MYSQLD_START,
             _("Unable to configure MyAQL: error in starting mysqld_safe, return code was %(rc)d"))
define_error(ERR_MYSQL_NO_RESPONSE,
             _("MySQL server started, but not responding"))
define_error(ERR_POST_CONFIG_SHUTDOWN,
             _("Install completed but error occurred in post-configuration shutdown"))
define_error(ERR_NO_INSTALL_DIR,
             _("MySQL install directory %(dir)s does not exist"))
define_error(ERR_MYSQL_BUILD,
             _("MySQL build failed"))

class MysqlError(UserError):
    def __init__(self, error_id, action, config, msg_args=None, developer_msg=None):
        context = ["%s of %s, instance %s" % 
                   (action, config.package_name, config.id)]
        UserError.__init__(self, errors[error_id], msg_args, developer_msg, context)


TIMEOUT_TRIES = 10
TIME_BETWEEN_TRIES = 2.0

_mysql_initd_file="""#!/bin/bash

if [[ "$1" == "start" ]]; then
    %(libexec_dir)s/mysqld --user=%(os_user)s --basedir=%(basedir)s --port=%(port)s --pid-file=%(pid_file)s --socket=%(socket_file)s --log-error=%(error_log_file)s --datadir=%(datadir)s &
else
    if [[ "$1" == "stop" ]]; then
        pid=`cat %(pid_file)s`
        echo "stopping mysql process $pid"
        kill -TERM $pid
    else
        echo "mysql start|stop"
        exit 1
    fi
fi 
"""

class MysqlConfig:
    """A class holding the configuration data we use for MySQL. This comes
    from the resource instance, but we just put it in a more strongly typed
    object to make it easier to get to and pass around as a unit to helper
    functions."""
    _format_str = \
"""{"package_name":"%s", "home_path":"%s",
  "port":%d, "admin_password":"%s",
  "os_user":"%s", "hostname":"%s",
  "home_dir_parent":"%s",
  "home_dir":"%s",
  "bin_dir":"%s",
  "libexec_dir":"%s",
  "script_dir":"%s",
  "pid_file":"%s",
  "mysqladmin_path:"%s",
  "log_path":"%s", "id":"%s"}
"""

    def __init__(self, package_name, id, home_path, port, admin_password,
                 os_user, hostname):
        self.package_name = package_name
        self.id = id
        self.home_path = os.path.abspath(home_path)
        self.admin_password = install_context.password_repository.get_value(admin_password)
 
        self.port = port
        self.os_user = os_user
        self.home_dir_parent = os.path.dirname(self.home_path)
        self.home_dir = os.path.basename(self.home_path)
        self.bin_dir = os.path.join(self.home_path, "bin")
        self.script_dir = os.path.join(self.home_path, "bin")
        self.libexec_dir = os.path.join(self.home_path, "libexec")
        self.hostname = hostname
        self.pid_file = os.path.join(os.path.join(self.home_path, "data"),
                                     self.os_user + ".pid")
        self.mysqladmin_path = os.path.join(self.bin_dir, "mysqladmin")
        self.log_path = os.path.join(self.home_path, "log")
        self.error_log_file = os.path.join(self.log_path, "mysql.err")
        self.socket_file = os.path.join(self.home_path, "mysql.sock")
        self.data_dir = os.path.join(self.home_path, "data")    
    def __str__(self):
        return MysqlConfig._format_str % \
            (self.package_name, self.home_path, self.port,
             self.admin_password, self.os_user,
             self.hostname, self.home_dir_parent, self.home_dir, self.bin_dir,
             self.script_dir, self.pid_file, self.mysqladmin_path,
             self.log_path, self.id)
                              


def _make_config_file(program, dir, root_pw, hostname, port):
    """Create a temporary config file in the specified directory containing
    the username (root) and password. The file is readable and writable only
    by the current user (at least on unix).

    The program is the name of the program this applies to - e.g. mysql,
    mysqld, or mysqladmin
    """
    return \
      iufile.make_temp_config_file("[%s]\nuser=root\npassword=%s\nport=%d\n" %
                                   (program, root_pw, port), dir)

def _do_query(query_str, config, action, root_pw=None):
    if root_pw==None:
        root_pw = config.admin_password
    cfg_filename = _make_config_file("mysql", config.bin_dir, root_pw,
                                     config.hostname, config.port)
    mysql = os.path.join(config.bin_dir, "mysql")
    defaults_file = "--defaults-file=%s" % cfg_filename
    socket = "--socket=%s" % config.socket_file
    try:
        logger.debug("Running query '%s'" % query_str)
        rc = iuprocess.run_and_log_program([mysql, defaults_file, socket], {},
                                           logger,
                                           cwd=config.home_path,
                                           input=query_str)
    finally:
        os.remove(cfg_filename)
    if rc!=0:
        raise MysqlError(ERR_MYSQL_QUERY, action, config,
                         {"rc":rc})

def _mysql_secure_installation(config):
    """This function implements the equivalent of the script
    mysql_secure_installation, which comes with the mysql install. We don't
    run that script directly, because it expects a tty for entering passwords,
    which is somewhat problematic when running from python.
    """
    try:
        # remove anonymous users
        _do_query("DELETE FROM mysql.user WHERE User='';", config, "Install",
                  root_pw="")
        # disallow remote root login
        _do_query("DELETE FROM mysql.user WHERE User='root' AND Host!='localhost';",
                  config, "Install", root_pw="")
        # remove the test databae
        _do_query("DROP DATABASE test;", config, "Install", root_pw="")
        _do_query("DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%'", config,
                  "Install", root_pw="")
        # change the root password
        pw_cmd = "UPDATE mysql.user SET Password=PASSWORD('%s') WHERE User='root';"\
            % config.admin_password
        _do_query(pw_cmd, config, "Install", root_pw="")
        # reload privilege tables
        _do_query("FLUSH PRIVILEGES;", config, "Install", root_pw="")
    except UserError:
        raise
    except:
        raise convert_exc_to_user_error(sys.exc_info(), errors[ERR_SECURE_EXC])


def check_status(config, root_pw=None):
    if not os.path.exists(config.pid_file):
        logger.debug("%s: server not up - pid file '%s' not found" %
                     (config.package_name, config.pid_file))
        return False
    file = open(config.pid_file, "rb")
    data = file.read()
    file.close()
    pid = int(data)
    if iuprocess.is_process_alive(pid)==False:
        logger.debug("%s: server not up - process %d not alive" %
                     (config.package_name, pid))
        return False
    if root_pw==None: root_pw = config.admin_password
    cfg_filename = _make_config_file("mysqladmin", None, root_pw,
                                     config.hostname, config.port)
    args = [config.mysqladmin_path, "--defaults-file=%s" % cfg_filename,
            "--socket=%s" % config.socket_file,
            "ping"]
    re_map = {'alive': 'mysqld\\ is\\ alive'}
    try:
        (rc, map) = iuprocess.run_program_and_scan_results(args, re_map,
                                                           logger,
                                                           log_output=True)
    finally:
        os.remove(cfg_filename)
    if rc!=0 or map['alive']==False:
        logger.debug("%s: server not up - mysqladmin ping failed" %
                     config.package_name)
        return False
    else:
        logger.debug("%s: server up, pid is %d" %
                     (config.package_name, pid))
        return True

def startup(config):
    logger.info('Starting mysqld')
    rc = iuprocess.run_background_program(
             [os.path.join(config.libexec_dir, "mysqld"),
              "--user=%s" % config.os_user,
              "--basedir=%s" % config.home_path,
              "--port=%d" % config.port,
              "--pid-file=%s" % config.pid_file,
              "--socket=%s" % config.socket_file,
              "--log-error=%s" % config.error_log_file,
              "--datadir=%s" % config.data_dir],
             env_mapping=None,
             logfile=os.path.join(config.log_path, "mysqld.out"),
             logger=logger,
             cwd=config.home_path)
    if rc != 0:
        raise MysqlError(ERR_STARTUP, "Startup", config, {"rc": rc})

    
def shutdown(config, root_pw=None):
    """Shutdown the mysql server using mysqladmin. Doesn't check whether
    it was running. Returns True if successful, False otherwise.
    """
    if root_pw==None:
        root_pw = config.admin_password
    cfg_filename = _make_config_file("mysqladmin", None, root_pw,
                                     config.hostname, config.port)
    args = [config.mysqladmin_path, "--defaults-file=%s" % cfg_filename,
            "--socket=%s" % config.socket_file, "shutdown"]
    try:
        rc = iuprocess.run_and_log_program(args, None, logger,
                                           cwd=config.home_path)
    finally:
        os.remove(cfg_filename)
    if rc!=0:
        return False
    else:
        return True

class Manager(service_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        service_manager.Manager.__init__(self, metadata, package_name)
        home_path = \
            os.path.abspath(self.metadata.config_port["install_dir"])
        port = self.metadata.config_port["port"]
        admin_password = self.metadata.config_port["admin_password"]
        os_user = (self.metadata.input_ports["host"])["os_user_name"]
        hostname = (self.metadata.input_ports["host"])["hostname"]
        self.config = MysqlConfig(package_name, self.id, home_path, port,
                                  admin_password, os_user, hostname)

    def validate_pre_install(self):
        if sys.platform=="win32":
            raise ConfigurationError, \
             "Installation of %s to Windows currently not supported" % \
             self.config.package_name
        #iupath.check_installable_to_target_dir(self.config.home_path,
        #                                       self.config.package_name)
        logger.debug("%s instance %s passed pre-install checks." %
                     (self.config.package_name, self.id))

    def _setup_mysql_config_files(self):
        # configure --prefix=... should take care of these
        pass
        #config_filename = os.path.join(self.config.bin_dir, "mysql_config")
        #path_pat = "\\'\\/usr\\/local\\/mysql\\/"
        #new_path = self.config.home_path + os.sep
        #cnt = iufile.subst_in_file(config_filename,
        #                           [(path_pat, new_path)])
        #if cnt==0:
        #   raise MysqlError(ERR_CONFIG_FILE, "Install", self.config,
        #                     {"file":config_filename})
        #access_filename = os.path.join(self.config.bin_dir, "mysqlaccess")
        #cnt = iufile.subst_in_file(access_filename,
        #                       [(path_pat, new_path)])
        #if cnt==0:
        #   raise MysqlError(ERR_CONFIG_FILE, "Install", self.config,
        #                   {"file":access_filename})

    def _run_setup_script(self, script_path, args, input=None):
        logger.info('running setup script')
        prog_and_args = [script_path] + args
        rc = iuprocess.run_and_log_program(prog_and_args, {},
                                                      logger,
                                                      cwd=self.config.home_path,
                                                      input=input)
        if rc != 0:
            raise MysqlError(ERR_SETUP_SCRIPT, "Install", self.config,
                             {"script":os.path.abspath(script_path),
                              "rc":rc})
        
    def install(self, package):
        # We extract the source tree into a directory called mysql_src, build, and
        # then install into mysql.
        source_dir_name = self.config.home_dir + "_src"
        source_dir_path = os.path.join(self.config.home_dir_parent, source_dir_name)
        extracted_dir = package.extract(self.config.home_dir_parent, source_dir_name)
	assert extracted_dir == source_dir_name
        # configure with prefix self.confg.home_path, make and make install
        rc = iuprocess.system('cd %s; ./configure --prefix=%s --with-mysqld-user=%s; make; make install' % 
                              (source_dir_path, self.config.home_path, self.config.os_user), logger,
                              log_output_as_info=True)
        if rc != 0:
            raise MysqlError(ERR_MYSQL_BUILD, "Install",
                             self.config, developer_msg="Return code was %d" % rc)
        # build was successful, delete the source tree
        logger.action("rm -rf %s" % source_dir_path)
        shutil.rmtree(source_dir_path)
        iupath.mkdir_p(os.path.join(self.config.home_path, 'data'))
        iupath.mkdir_p(os.path.join(self.config.home_path, 'var'))
        # modify configuration files
        self._setup_mysql_config_files()
        logger.info('extracted files. will run setup script.')
        # run setup scripts
        os_user_arg = "--user=%s" % self.config.os_user
        base_dir_arg = "--basedir=%s" % self.config.home_path
        data_dir_arg = "--datadir=%s" % self.config.data_dir
        self._run_setup_script(os.path.join(self.config.script_dir,
                                            "mysql_install_db"),
                               [os_user_arg, base_dir_arg, data_dir_arg])
        # start the server in safe mode
        logger.info('will run mysqld_safe in safe mode.')
        rc = iuprocess.run_background_program(
                 [os.path.join(self.config.bin_dir, "mysqld_safe"),
                  os_user_arg,
                  "--port=%d" % self.config.port,
                  "--pid-file=%s" % self.config.pid_file,
                  "--basedir=%s" % self.config.home_path,
                  "--datadir=%s" % self.config.data_dir,
                  "--skip-syslog",
                  "--log-error=%s" % self.config.error_log_file,
                  "--mysqld=mysqld",
                  "--socket=%s" % self.config.socket_file,
                  "--skip-grant-tables"],	# this is required to access the server without getting an access denied
                 env_mapping=None,
                 logfile=os.path.join(self.config.log_path, "mysqld_safe.out"),
                 logger=logger,
                 cwd=self.config.home_path)
        if rc != 0:
            raise MysqlError(ERR_MYSQLD_START, "Install", self.config,
                             {"rc":rc})
        # wait until server responds
        logger.info('waiting till server responds. ')
        if iutimeout.retry(check_status, TIMEOUT_TRIES, TIME_BETWEEN_TRIES,
                           self.config, root_pw=self.config.admin_password)==False:
            raise MysqlError(ERR_MYSQL_NO_RESPONSE, "Install", self.config)
        #rc = iuprocess.run_and_log_program([os.path.join(self.config.script_dir, 'mysqladmin'), '-u root', 'password', self.config.admin_password],
        #                               {}, logger, cwd=self.config.home_path, input=None)
        #if rc != 0:
        #   assert False, "cannot set root password"
        _mysql_secure_installation(self.config)
        if shutdown(self.config)==False:
            raise MysqlError(ERR_POST_CONFIG_SHUTDOWN, "Install", self.config)
        
        # write out the init.d startup script
        # we just stick it in the install directory for now and leave it to 
        # the user to manually copy it to /etc/init.d and enable it.
        startup_script = _mysql_initd_file % {
                "libexec_dir":self.config.libexec_dir,
                "os_user":self.config.os_user,
                "basedir":self.config.home_path,
                "port":self.config.port,
                "pid_file":self.config.pid_file,
                "socket_file":self.config.socket_file,
                "error_log_file":self.config.error_log_file,
                "datadir":self.config.data_dir
            }
        start_script_filepath = os.path.join(self.config.home_path, "mysql.sh")
        start_script_file = open(start_script_filepath, "wb")
        start_script_file.write(startup_script)
        start_script_file.close()
        os.chmod(start_script_filepath, 0755)
                                              
        # check that everything is now in place
        self.validate_post_install()


    def is_installed(self):
        False
        #return os.path.exists(self.config.home_path)

    def validate_post_install(self):
        if not os.path.exists(self.config.home_path):
            raise MysqlError(ERR_NO_INSTALL_DIR, "Post-install validation",
                             self.config, {"dir":self.config.home_path})

    def start(self):
        startup(self.config)
        if iutimeout.retry(check_status, TIMEOUT_TRIES, TIME_BETWEEN_TRIES,
                          self.config)==False:
            raise MysqlError(ERR_MYSQL_NO_RESPONSE, "Startup", self.config)

    def is_running(self):
        return check_status(self.config)

    def stop(self):
        shutdown(self.config)

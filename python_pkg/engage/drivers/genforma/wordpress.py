"""Resource manager for wordpress. 
"""
import re
import urllib2
import commands
import os
import engage.drivers.resource_manager as resource_manager
import engage.drivers.resource_metadata as resource_metadata

import engage.utils.log_setup
logger = engage.utils.log_setup.setup_script_logger("Wordpress")

from engage.utils.user_error import UserError, ScriptErrInf
import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = ScriptErrInf("setuptools", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
ERR_WORDPRESS = 1

define_error(ERR_WORDPRESS,
             _("error installing GitPlugin"))


class Config(resource_metadata.Config):
    def __init__(self, props_in, types, id, package_name):
        resource_metadata.Config.__init__(self, props_in, types)
	self._add_computed_prop("database_table_prefix", self.config_port.database_table_prefix)
	self._add_computed_prop("database_name", self.config_port.database_name)
	self._add_computed_prop("database_user", self.config_port.database_user)
	self._add_computed_prop("database_password", self.config_port.database_password)
	self._add_computed_prop("database_user_host", self.config_port.database_user_host)
	self._add_computed_prop("home", self.config_port.home)
	self._add_computed_prop("url", self.config_port.url)
	self._add_computed_prop("mysql_host", self.input_ports.mysql.host)
	self._add_computed_prop("mysql_port", self.input_ports.mysql.port)
        self._add_computed_prop("mysql_path",
                                os.path.join(
                                  os.path.join(
                                    self.input_ports.mysql_admin.install_dir,
                                    "bin"), "mysql"))
        self._add_computed_prop("socket_file",
                                os.path.join(
                                  self.input_ports.mysql_admin.install_dir,
                                    "mysql.sock"))
	self._add_computed_prop("mysql_admin_password", self.input_ports.mysql_admin.root_password)
	self._add_computed_prop("webserver_docs", self.input_ports.webserver.doc_dir)

def call_mysql(config, input, continue_on_error=False):
    cfg_filename = \
      iufile.make_temp_config_file(
        "[mysql]\nuser=root\npassword=%s\nport=%d\n" %
        (config.input_ports.mysql_admin.root_password,
         config.input_ports.mysql.port),
        dir=config.home)
    defaults_file = "--defaults-file=%s" % cfg_filename
    socket_file = "--socket=%s" % config.socket_file
    try:
        rc = iuprocess.run_and_log_program([config.mysql_path, defaults_file,
                                            socket_file],
                                           {},
                                           logger,
                                           cwd=config.home_path,
                                           input=input)
    finally:
        os.remove(cfg_filename)
    if rc!=0 and not continue_on_error:
        raise OpenmrsError(ERR_CALL_MYSQL, "Install", config,
                           developer_msg="Return code: '%d', Input: '%s'" % (rc, input))
    return rc

class Manager(resource_manager.Manager):
    def __init__(self, metadata):
        package_name = "%s %s" % (metadata.key["name"],
                                  metadata.key["version"])
        resource_manager.Manager.__init__(self, metadata, package_name)
	self.config = metadata.get_config({ } , Config, self.id, package_name)
    
    def validate_pre_installation(self):
	pass

    def is_installed(self):
	return True # XXX

    def install(self, package):
	logger.debug("Installing Wordpress")
	extracted_dir = package.extract(self.config.genforma_home)
	logger.debug("Extracted directory is: " + extracted_dir)
        mysql_cmds = """CREATE DATABASE %s; GRANT ALL PRIVILEGES ON %s.* TO "%s"@"%s" IDENTIFIED BY "%s"; FLUSH PRIVILEGES; EXIT""" \
                     % (self.config.database_name, self.config.database_name, self.config.database_user, self.config.database_user_host, \
                       self.config.database_password)
	logger.debug("Executing mysql command " + mysql_cmds)
	rc = call_mysql(self.config, mysql_cmds, continue_on_error=True)
	logger.debug("Created database")
	logger.debug("Now configuring wp-config.php")
        logger.debug("Getting secret keys from https://api.wordpress.org/secret-key/1.1/")
        key_generator = urllib2.urlopen('https://api.wordpress.org/secret-key/1.1/')
        secret_keys = key_generator.read()
        key_generator.close()
        wp_config = """<?php
/** 
 * The base configurations of the WordPress.
 *
 * This file has the following configurations: MySQL settings, Table Prefix,
 * Secret Keys, WordPress Language, and ABSPATH. You can find more information by
 * visiting {@link http://codex.wordpress.org/Editing_wp-config.php Editing
 * wp-config.php} Codex page. You can get the MySQL settings from your web host.
 *
 * This file is used by the wp-config.php creation script during the
 * installation. You don't have to use the web site, you can just copy this file
 * to "wp-config.php" and fill in the values.
 *
 * @package WordPress
 */

// ** MySQL settings - You can get this info from your web host ** //
/** The name of the database for WordPress */
define('DB_NAME', '%s');

/** MySQL database username */
define('DB_USER', '%s');

/** MySQL database password */
define('DB_PASSWORD', '%s');

/** MySQL hostname */
define('DB_HOST', '%s');

/** Database Charset to use in creating database tables. */
define('DB_CHARSET', 'utf8');

/** The Database Collate type. Don't change this if in doubt. */
define('DB_COLLATE', '');

/**#@+
 * Authentication Unique Keys.
 *
 * Change these to different unique phrases!
 * You can generate these using the {@link https://api.wordpress.org/secret-key/1.1/ WordPress.org secret-key service}
 * You can change these at any point in time to invalidate all existing cookies. This will force all users to have to log in again.
 *
 * @since 2.6.0
 */
/*
 define('AUTH_KEY', 'put your unique phrase here');
 define('SECURE_AUTH_KEY', 'put your unique phrase here');
 define('LOGGED_IN_KEY', 'put your unique phrase here');
 define('NONCE_KEY', 'put your unique phrase here');
*/
%s
/**#@-*/

/**
 * WordPress Database Table prefix.
 *
 * You can have multiple installations in one database if you give each a unique
 * prefix. Only numbers, letters, and underscores please!
 */
$table_prefix  = '%s';

/**
 * WordPress Localized Language, defaults to English.
 *
 * Change this to localize WordPress.  A corresponding MO file for the chosen
 * language must be installed to wp-content/languages. For example, install
 * de.mo to wp-content/languages and set WPLANG to 'de' to enable German
 * language support.
 */
define ('WPLANG', '');

/* That's all, stop editing! Happy blogging. */

/** WordPress absolute path to the Wordpress directory. */
if ( !defined('ABSPATH') )
	define('ABSPATH', dirname(__FILE__) . '/');

/** Sets up WordPress vars and included files. */
require_once(ABSPATH . 'wp-settings.php');
	""" % (self.config.database_name, self.config.database_user, self.config.database_password, self.config.mysql_host, \
               secret_keys,
       	       self.config.database_table_prefix)
	logger.debug("Now setting up webserver configuration")
	shutil.copytree(extracted_dir, self.config.webserver_docs + "/" + self.config.home)
	logger.debug("Now running install.php")
	logger.debug("Done installing Wordpress")

    def validate_post_installation(self):
	pass

		

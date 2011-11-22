Password Management
===================
Why and when the password database is created
------------------------------------------------------------------------------------------
Engage may need to store passwords to install, start, and stop various application components. If necessary,
such passwords are stored in an encrypted file within the Engage deployment home. The key for this
file is called the *master password* and is provided by the user at deployment time.
The password database file will be created only if the Engage installer determines that one or more components are
being intalled that 1) need to store a password in the password database, and/or 2) require super-user access (and Engage is not run from the ``root`` account).

During the initial install/deployment, the user will be prompted for the master password, sudo password (if needed), and the passwords for any individual components. If a password database is created,
the user will be prompted for the master password when running the ``svcctl`` management
tool. ``svcctl`` will then read the remaining passwords from the database.

Automating password input
-----------------------------------------------------------------------------------------
Master password file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In some situations (e.g. reboots), it may be necessary to run ``svcctl`` without any interactive
input. To enable this, you can use the ``-p`` (``--master-password-file``) option to specify a
file containing the master password. Here is an example (assuming your master password is ``test``::

  echo test >/etc/engage/master
  chmod 600 /etc/engage/master
  svcctl -p /etc/engage/master start

Be sure to set the read/write permissions on your password file to be restricted to only the current user.

Pre-created password file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In some situations (e.g. unattended installs or automated testing), passwords are required for an
application stack, but it is necessary to run the installer or deployer without any interactive password input. If a password repository is already present in the deployment home and it contains all the required passwords, the installer and deployer will use the existing repository without prompting the user.

You can pre-create a password repository in one of two ways:
 1. If you run the installer or deployer with the ``-g`` option, it will prompt the user for any required passwords, create the password database and exit. This repository can be used with subsequent deployments.
 2. You can manually create a password repository through the ``create`` command of the password manager utility (see below).

Once you have created a password repository, you can then use the installer's/deployer's ``-p`` command line option to specify the master password in a file, enabling a fully unattended install.


Password Manager Utility
-------------------------------------------------------------------------
The password manager utility lets you view, create, and update Engage password repositories. The script is available at ``<deployment_home>/engage/bin/password_manager``.

Viewing a password repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The password manager's ``view`` command will let you view an individual password entry or the entire repository.  To view the entire repository, just use the view command without any arguments::

  $ cd engage/bin
  $ ./password_manager view
  Master password: ****
  GenForma/host/sudo_password' password is 'sudo_pw'
  'apache-tomcat/admin_password' password is 'test'
  'mysql-macports/admin_pw' password is 'test'
  3 entries found.

To view a single entry, include the key of the entry on the command line::

  $ cd engage/bin
  $ ./password_manager view apache-tomcat/admin_password
  Master password: ****
  'apache-tomcat/admin_password' password is 'test'

You can also get a JSON representation of the password database via the ``view-json`` command::

  $ cd engage/bin
  $ ./password_manager view
  Master password: ****
  {
   "GenForma/host/sudo_password": "sudo_pw", 
    "apache-tomcat/admin_password": "test", 
    "mysql-macports/admin_pw": "test"
  }


Creating a new repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
To create a new password repository, one first creates a JSON file mapping the password keys to
the actual passwords. For example::

  $ cat ~/apps/pw_input.json
  {
   "GenForma/host/sudo_password": "sudo_pw", 
    "apache-tomcat/admin_password": "test", 
    "mysql-macports/admin_pw": "test"
  }

 Next, you run the password manager with the ``create`` command, passing it the name of your input JSON file::

  $ cd engage/bin
  $ ./password_manager create ~/apps/pw_input.json
  Master password: ****
  Master password (re-enter): ****
  Created password database


Updating an existing repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
To update an entry in an existing repository, one may use the ``update`` command. This command takes one argument, the key to be updated. For example, the following sets the password entry for Apache Tomcat to ``test2``::

  $ cd engage/bin
  $ ./password_manager view apache-tomcat/admin_password
  Master password: ****
  Enter password for key 'apache-tomcat/admin_password':
  Enter password for key 'apache-tomcat/admin_password' (re-enter):
  Updated password database with key 'apache-tomcat/admin_password'

Please note that the update command only changes the entry in the password repository. If there are corresponding configuration files in an already-deployed component (e.g. the tomcat-users.xml file for Apache Tomcat), these will not be changed by the password manager.


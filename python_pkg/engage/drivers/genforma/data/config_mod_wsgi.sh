#!/bin/bash
# The apache wsgi module needs to be configured to use the app-local version of
# python, which has a bunch of modules installed (e.g. django itself). Here's
# a script for Ubuntu Linux that does this configuration, assuming you've
# already installed the libapache2-mod-wsgi package.

# need to run this under sudo

config_file=/etc/apache2/mods-enabled/wsgi.conf

echo "setting group permissions on genforma_website"
if ! chgrp -R www-data ${genforma_home}; then
  echo "unable to change ownership of ${genforma_home} to www-data"
  exit 1
fi
if ! chmod -R g+rw ${genforma_home}; then
  echo "unable to grant group read/write permissions to ${genforma_home}"
  exit 1
fi

echo "Copying site config file to /etc/apache2/sites-enabled"
if ! cp ${app_short_name}_apache_wsgi.conf /etc/apache2/sites-enabled; then
  echo "unable to copy config file ${app_short_name}_apache_wsgi.conf"
  exit 1
fi

if [[  -a $$config_file ]]; then
  echo "Found config file $$config_file"
else
  echo "Missing wsgi.conf file $$config_file, is mod_wsgi installed?"
  exit 1
fi

if grep 'WSGIPythonHome ${genforma_home}/python/' $$config_file; then
  echo "Entry already made in wsgi.conf"
  exit 0
fi

if grep 'WSGIPythonHome' $$config_file; then
  echo "An WSGIPythonHome entry already in wsgi.conf, but not pointing at this app's python"
  exit 1
fi

echo "Adding WSGIPythonHome entry"
sed -i "1a WSGIPythonHome ${genforma_home}/python/" $$config_file

exit 0


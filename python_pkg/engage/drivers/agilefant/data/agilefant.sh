#!/bin/bash

if [[ "$1" == "start" ]]; then
  echo "Starting agilefant"
  %(mysql_install_dir)s/share/mysql/mysql.server start
  %(tomcat_install_dir)s/bin/startup.sh
else
  if [[ "$1" == "stop" ]]; then
    echo "Stopping agilefant"
    %(tomcat_install_dir)s/bin/shutdown.sh
    pid=`cat %(mysql_install_dir)s/data/%(os_user)s.pid`
    echo "Stopping mysql process $pid"
    kill -TERM $pid
  else
    if [[ "$1" == "status" ]]; then
      echo "Checking agilefant status..."
      echo "Looking for tomcat process:"
      ps -ef | grep java | grep -v grep | grep tomcat
      if [[ ! -a %(mysql_install_dir)s/data/%(os_user)s.pid ]]; then
        echo "MySQL not running"
      else
        pid=`cat %(mysql_install_dir)s/data/%(os_user)s.pid`
        echo "MySQL pid = $pid status: "
        ps -ef | grep $pid | grep -v grep
      fi
    else
      echo "agilefant start|stop|status"
      exit 1
    fi
  fi
fi
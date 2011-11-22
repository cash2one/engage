Application Packaging
==========================

For some types of applications (currently Django applications), Engage requires that you package the application before deploying/installing it. This process performs some validations, gatherers some metadata about your application, and places your application with the gethered metadata into an archive file. This process is very similar to the packaging of Java web applications into WAR files.

The Django packager is Python-based command line utility available at  http://pypi.python.org/pypi/engage-django-sdk. If you have a Django application, please view the associated documentation to see how to run the packager.

#!${python_exe}
# script to hook wsgi into django
import os
import sys

sys.path.extend('${python_path}'.split(':'))
os.environ['DJANGO_SETTINGS_MODULE'] = '${django_settings_module}'

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()

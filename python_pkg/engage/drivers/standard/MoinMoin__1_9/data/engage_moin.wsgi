#!${input_ports.python.home}
# -*- coding: iso-8859-1 -*-
"""
    MoinMoin - mod_wsgi driver script

"""

import sys, os

# a) Configuration of Python's code search path
#    If you already have set up the PYTHONPATH environment variable for the
#    stuff you see below, you don't need to do a1) and a2).

# a1) Path of the directory where the MoinMoin code package is located.
#     Needed if you installed with --prefix=PREFIX or you didn't use setup.py.
sys.path.insert(0, '${home}')

# a2) Path of the directory where wikiconfig.py / farmconfig.py is located.
#     See wiki/config/... for some sample config files.
#sys.path.insert(0, '/path/to/wikiconfigdir')
#sys.path.insert(0, '/path/to/farmconfigdir')

# b) Configuration of moin's logging
#    If you have set up MOINLOGGINGCONF environment variable, you don't need this!
#    You also don't need this if you are happy with the builtin defaults.
#    See wiki/config/logging/... for some sample config files.
from MoinMoin import log
log.load_config('${log_config_file}')

from MoinMoin.web.serving import make_application

# Creating the WSGI application
# use shared=True to have moin serve the builtin static docs
# use shared=False to not have moin serve static docs
# use shared='/my/path/to/htdocs' to serve static docs from that path
application = make_application(shared=True)


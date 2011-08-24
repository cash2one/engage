"""Resource manager for PermissionRedirectPlugin. 
"""

import trac_plugin

class Manager(trac_plugin.Manager):
    def __init__(self, metadata):
        trac_plugin.Manager.__init__(self, metadata,
                                     trac_plugin.get_config_type(),
                                     trac_plugin.Config,
                                     "permredirectplugin.*",
                                     "0.11")

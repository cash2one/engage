"""Resource manager for iniAdminPlugin. 
"""

import trac_plugin


class Manager(trac_plugin.Manager):
    def __init__(self, metadata):
        trac_plugin.Manager.__init__(self, metadata,
                                     trac_plugin.get_config_type(),
                                     trac_plugin.Config,
                                     "IniAdmin.*",
                                     "0.11")


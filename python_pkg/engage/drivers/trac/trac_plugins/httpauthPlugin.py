"""Resource manager for httpAuthPlugin. 
"""

import trac_plugin


class Manager(trac_plugin.Manager):
    def __init__(self, metadata):
        trac_plugin.Manager.__init__(self, metadata,
                                     trac_plugin.get_config_type(),
                                     trac_plugin.Config,
                                     "TracHTTPAuth.*",
                                     "0.11")


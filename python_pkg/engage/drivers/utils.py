"""Utility functions for drivers. This is for functionality that is specific
to building drivers, like functions to get metadata. General utility functions should
go under engage.utils.*
"""

import os.path
import shutil

def get_packages_filename(driver_filename):
    """Every driver that has its own packages file must implement
    a get_packages_filename() function to return the name of the packages file.
    This file is located in the same directory as the driver file.
    You can just call this function, passing in __file__ as the driver_filename
    parameter.
    """
    return os.path.abspath(os.path.expanduser(os.path.join(os.path.dirname(driver_filename), "packages.json")))




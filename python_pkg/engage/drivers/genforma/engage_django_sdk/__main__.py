#! /user/bin/env python

"""Command line interface to engage-django sdk.
"""

import sys
import os.path
from optparse import OptionParser
import logging
import traceback

from version import VERSION
import packager
import packager.command
import packager.errors

logger = logging.getLogger()

class CommandManager(packager.command.CommandManager):
    def __init__(self):
        super(CommandManager, self).__init__()
        self.verbose = False

    def add_options(self, parser):
        parser.add_option("-v", "--verbose", action="store_true", dest="verbose")
        parser.add_option("--test-install-dir", dest="test_install_dir",
                          default=None,
                          help="Use the specified directory as a target for test installation, rather than a temporary directory")
        parser.add_option("--package-cache-dir", dest="package_cache_dir",
                          default=None,
                          help="Directory to check for local copies of packages")

    def process_generic_options(self, options, args):
        self.verbose = options.verbose

command_manager = CommandManager()


command_manager.register_command(packager.PrepareDirCommand)
command_manager.register_command(packager.PrepareArchiveCommand)


def main(argv=sys.argv):
    try:
        (major_v, minor_v, micro_v, releaselevel, serial) = sys.version_info
        if major_v != 2 or minor_v < 6:
            sys.stderr.write("This program only works with Python 2.x (2.6 and later)\n")
            sys.exit(2)
        print ('engage-django-sdk version %s' % VERSION)
        command = command_manager.parse_command_args(argv)
        root_logger = logging.getLogger()
        handler = logging.StreamHandler()
        root_logger.addHandler(handler)
        if command_manager.verbose:
            root_logger.setLevel(logging.DEBUG)
            handler.setLevel(logging.DEBUG)
        else:
            root_logger.setLevel(logging.INFO)
            handler.setLevel(logging.INFO)            
        rc = command.run()
        if rc==0:
            logger.info(">> Command %s completed successfully." % command.get_name())
        else:
            logger.info(">> Command %s failed." % command.get_name())
        return rc
    except packager.errors.ValidationError:
        (exc_type, exc_value, exc_traceback) = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, None, file=sys.stderr)
        return 1
    except SystemExit, c:
        sys.exit(c)
    except:
        (exc_type, exc_value, exc_traceback) = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())

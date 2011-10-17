#!/usr/bin/env python
"""Command-line utility to validate resource definitions.
"""
import sys
import os.path
from tempfile import NamedTemporaryFile
from optparse import OptionParser
import json
import logging
logger = logging.getLogger(__name__)

try:
    import engage.utils.rdef
except ImportError:
    python_pkg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../python_pkg"))
    if not os.path.exists(python_pkg_path):
        raise # can't find path, just bail out
    sys.path.append(python_pkg_path)
    import engage.utils.rdef

import engage.engine.engage_file_layout as engage_file_layout
from engage.engine.preprocess_resources import preprocess_resource_file

def create_opt_parser():
    """Returns (options, args) pair
    """
    usage = "%prog [options] <output_resource_def_file>\nPreprocesses resource definitions and runs validations.\nIf resource definition file is not specified, use temporary file"
    parser = OptionParser(usage=usage)
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                      default=False,
                      help="Print debug information")
    parser.add_option("-r", "--resource", dest="resource", default=None,
                      help="If specified, prune nodes unreachable from resource")
    return parser


def setup_logging(level=logging.DEBUG):
    formatter = logging.Formatter("[%(levelname)s][%(name)s] %(message)s")
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    
def main(argv):
    parser = create_opt_parser()
    (options, args) = parser.parse_args(argv)
    if options.verbose:
        setup_logging(logging.DEBUG)
    else:
        setup_logging(logging.INFO)
    resource_keys = \
        engage.utils.rdef.parse_resource_keys_option(options.resource,
                                                     parser)
    if len(args)==0:
        rdef_file = NamedTemporaryFile(delete=False)
        rdef_file.close()
        filename = rdef_file.name
        using_temp_file = True
    elif len(args)==1:
        filename = os.path.abspath(os.path.expanduser(args[0]))
        using_temp_file = False
    else:
        parser.error("Too many arguments")

    try:
        layout_mgr = engage_file_layout.get_engine_layout_mgr()
        main_rdef_file = os.path.abspath(os.path.expanduser(layout_mgr.get_resource_def_file()))
        all_input_files = layout_mgr.get_extension_resource_files() + [main_rdef_file,]
        if filename in all_input_files:
            # make sure user doesn't overwrite main file
             # should only get this problem if user specified the file
            assert not using_temp_file
            parser.error("Resource definition file parameter is for generated file, not the input file!")
        logger.debug("Preprocessing resource files, output is %s" % filename)
        preprocess_resource_file(main_rdef_file,
                                 layout_mgr.get_extension_resource_files(),
                                 filename, logger)
        with open(filename, "rb") as f:
            rg = engage.utils.rdef.create_resource_graph(json.load(f))

        if resource_keys:
            rg = rg.filter(resource_keys)
            if not using_temp_file:
                rg.write_to_file(filename)
            
        (errors, warnings) = rg.validate()
        if errors==0 and warnings==0:
            print "Validation of resource definitions ok"
            return 0
        else:
            print "Validation of resource definitions found %d errors, %d warnings" \
                  % (errors, warnings)
            return 1
    finally:
        if using_temp_file:
            os.remove(filename)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

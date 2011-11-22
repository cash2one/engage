#!/usr/bin/env python
"""Command-line utility to create ReST (restructured text) documentation
for the resource definitions.
"""

import sys
import os.path
from optparse import OptionParser
import json
import string
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
from engage.utils.file import NamedTempFile

# Constants for the formatting
RDEF_GROUP_HEADER = "-"
RDEF_TITLE_HEADER = "~"


sphinx_mode = False

def setup_logging(level=logging.DEBUG):
    formatter = logging.Formatter("[%(levelname)s][%(name)s] %(message)s")
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


def create_opt_parser():
    """Returns (options, args) pair
    """
    usage = "%prog [options] [output_file]\n Generates ReST (restructured-text) documentation for resource definitions)"
    parser = OptionParser(usage=usage)
    parser.add_option("-r", "--resource", dest="resource", default=None,
                      help="If specified, prune nodes unreachable from resource")
    parser.add_option("--header", default=None,
                     help="If specified, prepend the contents of the specified file to the generated output")
    parser.add_option("-s", "--use-sphinx-references", default=False,
                      action="store_true",
                      help="If specified, use Sphinx-style references")
    parser.add_option("-q", "--quiet", default=False,
                      action="store_true",
                      help="If specified, do not emit warnings")
    return parser

## _res_trans_table = string.maketrans("._", "--")
## def mangle_resource_key(key):
##     k = str(key["name"]) + "--" + str(key["version"])
##     return k.translate(_res_trans_table)

_res_trans_table = string.maketrans("", "")
def mangle_resource_key(key):
    k = str(key["name"]) + "--" + str(key["version"])
    return k.translate(_res_trans_table, ".-_")

def make_resource_ref(key):
    if sphinx_mode:
        return ":ref:`" + mangle_resource_key(key) + "`"
    else:
        return "`%s %s`_" % (key["name"], key["version"])

def write_base_constraint_as_rst(constraint, of, rg, indent=0):
    if constraint.targets_specific_version:
        of.write((" " * indent) + "* " + make_resource_ref(constraint.key) +
                 "\n")
    else:
        of.write((" " * indent) + "* %s versions %s. Matches are: %s\n" %
                 (constraint.name,
                  engage.utils.rdef.version_to_label(constraint.version_constraint),
                 ", ".join([make_resource_ref(rg.res_map[ks].key) for ks in constraint.find_all_matching(rg.res_by_name)])))


def write_constraint_as_rst(constraint, of, rg, indent=0):
    if (not constraint.is_base_constraint()) and len(constraint.constraint_list)==1:
        write_constraint_as_rst(constraint.constraint_list[0], of, rg, indent)
    elif constraint.is_all_of_constraint():
        of.write((" " * indent) + "* All of the following:\n\n")
        for subconstraint in constraint.constraint_list:
            write_constraint_as_rst(subconstraint, of, rg, indent + 3)
    elif constraint.is_one_of_constraint():
        of.write((" " * indent) + "* One of the following:\n\n")
        for subconstraint in constraint.constraint_list:
            write_constraint_as_rst(subconstraint, of, rg, indent + 3)
    else:
        write_base_constraint_as_rst(constraint, of, rg, indent)

def write_resource_as_rst(r, of, rg):
    if sphinx_mode:
        of.write(".. _%s:\n\n" % mangle_resource_key(r.key))
    else:
        of.write(".. _%s %s:\n\n" % (r.key["name"], r.key["version"]))
    res_title = "%s %s" % (r.key["name"], r.key["version"])
    of.write(res_title + "\n")
    of.write((RDEF_TITLE_HEADER * len(res_title)) + "\n")
    of.write("**Description:** " + r.display_name + "\n")
    if len(r.config_port.properties) > 0:
        of.write("\n**Configuration properties:**\n")
        for (n, prop) in r.config_port.properties.items():
            if isinstance(prop.json, dict) and prop.json.has_key("default"):
                of.write(" * %s : %s = %s\n" %
                         (n, prop.prop_type,
                          (lambda v:
                           '"' + v + '"' if isinstance(v, unicode)
                           else v.__repr__())(prop.json["default"])))
            else:
                of.write(" * %s : %s\n" % (n, prop.prop_type))
    if r.inside_constraint or r.env_constraint or r.peer_constraint:
        of.write("\n**Dependencies:**\n")
    if r.inside_constraint != None:
        of.write(" * Deployed inside:\n\n")
        write_constraint_as_rst(r.inside_constraint, of, rg, 3)
    if r.env_constraint != None:
        of.write(" * Environment dependencies:\n\n")
        write_constraint_as_rst(r.env_constraint, of, rg, 3)
    if r.peer_constraint != None:
        of.write(" * Service dependencies:\n\n")
        write_constraint_as_rst(r.peer_constraint, of, rg, 3)
    of.write("\n")

def get_sorted_resource_keys(rg):
    names = rg.res_by_name.keys()
    names.sort()
    l = []
    for name in names:
        resources = rg.res_by_name[name]
        versions = [r.key["version"] for r in resources]
        versions.sort() # TODO: do an intelligent version comparison
        for v in versions:
            l.append({"name":name, "version":v})
    return l

def main(argv):
    global sphinx_mode
    parser = create_opt_parser()
    (options, args) = parser.parse_args(argv)
    if options.header and \
       not os.path.exists(options.header):
        parser.error("Header text file %s does not exist" %
                     options.header)
    if options.use_sphinx_references:
        sphinx_mode = True
    setup_logging(logging.INFO)
    resource_keys = \
        engage.utils.rdef.parse_resource_keys_option(options.resource,
                                                     parser)
    if len(args)>1:
        parser.error("Too many arguments")

    def warning(msg):
        if not options.quiet:
            sys.stderr.write(msg + "\n")

    # preprocess resources and build the graph
    layout_mgr = engage_file_layout.get_engine_layout_mgr()
    main_rdef_file = os.path.abspath(os.path.expanduser(layout_mgr.get_resource_def_file()))
    all_input_files = layout_mgr.get_extension_resource_files() + [main_rdef_file,]
    with NamedTempFile() as temp:
        preprocess_resource_file(main_rdef_file,
                                 layout_mgr.get_extension_resource_files(),
                                 temp.name, logger)
        with open(temp.name, "rb") as f:
            rg = engage.utils.rdef.create_resource_graph(json.load(f))
    if resource_keys:
        rg = rg.filter(resource_keys)
        
    if len(args)==0:
        of = sys.stdout
        need_to_close = False
    else:
        of = open(args[0], "wb")
        need_to_close = True

    if options.header:
        with open(options.header, "rb") as f:
            for line in f:
                of.write(line)

    # group the resources
    def is_host(r):
        return r.inside_constraint==None and r.env_constraint==None and \
               r.peer_constraint==None
    keys = get_sorted_resource_keys(rg)
    num = len(keys)
    primary_keys = rg.find_resources_not_referenced_as_dependencies()
    primary = []
    hosts = []
    other = []
    for k in keys:
        r = rg.get_resource(k)
        kstr = engage.utils.rdef.hash_key_for_res_key(k)
        if kstr in primary_keys:
            if is_host(r):
                warning("Skipping resource %s %s - it is an orphan" %
                        (r.key["name"], r.key["version"]))
            else:
                primary.append(r)
        elif is_host(r):
            hosts.append(r)
        else:
            other.append(r)

    def write_section(title, description, resources):
        of.write(title + "\n")
        of.write((RDEF_GROUP_HEADER * len(title)) + "\n")
        of.write(description + "\n\n")
        for r in resources:
            write_resource_as_rst(r, of, rg)
        of.write("\n")

    write_section("Primary Resources",
                  'The resources in this section are not referenced as dependencies by other resources. In most cases, these resources correspond to the applicaiton at the "top" of an application stack.',
                  primary)
    write_section("Host Resources",
                  'The resources in this section have no dependencies. In most cases, these resources correspond to the machine at the "bottom" of an application stack.',
                  hosts)
    write_section("Interior Resources",
                  'The resources in this section have dependencies and are dependencies for other resources. In most cases, these resources correspond to the "middle" of an application stack.',
                  other)

    if need_to_close:
        of.close()
        print "Processed %d resources." % num

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


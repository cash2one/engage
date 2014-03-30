"""Print a report of installed packages.
TODO: add support for .xls generation using xlwt package
"""
import sys
import os.path
from optparse import OptionParser
import json
import fnmatch

import engage_file_layout
import cmdline_script_utils
from engage.drivers.resource_metadata import parse_install_soln

formatter_map = {}

def _add_formatter(f):
    formatter_map[f.NAME] = f

class Formatter(object):
    """Write the output in a specified format. Should have
    a NAME class property.
    """
    def __init__(self, stream):
        self.stream = stream

    def start(self):
        pass

    def write_header(self, header_fields):
        """Given a list of field names
        """
        pass

    def write_row(self, body_fields):
        """Given a list of field values
        """
        pass

    def end(self):
        pass

class JsonFormatter(Formatter):
    NAME='json'

    def __init__(self, stream):
        Formatter.__init__(self, stream)
        self.lines = []

    def start(self):
        pass

    def write_header(self, header_fields):
        self.lines.append(header_fields)

    def write_row(self, body_fields):
        self.lines.append(body_fields)

    def end(self):
        json.dump(self.lines, self.stream, indent=2)

_add_formatter(JsonFormatter)

class CSVFormatter(Formatter):
    NAME='csv'

    def __init__(self, stream):
        try:
            import unicodecsv
        except ImportError, e:
            print "Got import exception: %s" % e
            raise Exception("Could not import unicodecsv, you may need to install it")
        Formatter.__init__(self, stream)
        self.writer = unicodecsv.writer(stream, encoding='utf-8')

    def start(self):
        pass

    def write_header(self, header_fields):
        self.writer.writerow(header_fields)

    def write_row(self, body_fields):
        self.writer.writerow(body_fields)

    def end(self):
        pass

_add_formatter(CSVFormatter)

def should_skip(package_name, skip_patterns):
    for p in skip_patterns:
        if fnmatch.fnmatchcase(package_name, p):
            return True
    return False


def write_report(format, resources, output_file=None, skip=None):
    resources = sorted(resources, key=lambda r: r.key['name'])
    if output_file:
        stream = open(output_file, 'wb')
    else:
        stream = sys.stdout

    try:
        fmtr = (formatter_map[format])(stream)
        fmtr.start()
        fmtr.write_header([
            'Package',
            'Version',
            'Description',
            'Licence',
            #'Derived from',
            'License URL'
        ])
        for r in resources:
            if skip and should_skip(r.key['name'], skip):
                continue
            if r.package:
                fmtr.write_row([
                    r.package.name,# more accurate than the resource name
                    r.package.version,
                    r.package.description,
                    r.package.license.name,
                    #r.package.license.derived_from,
                    r.package.license.url
                ])
            else:
                fmtr.write_row([
                    r.key['name'],
                    r.key['version'],
                    None,
                    None,
                    #None,
                    None
                ])
        fmtr.end()
    finally:
        if output_file:
            stream.close()


def load_installed_resources(options, parser):
    efl = engage_file_layout.get_engine_layout_mgr()
    deployment_home = cmdline_script_utils.get_deployment_home(options, parser,
                                                               efl,
                                                               allow_overrides=True)
    filepath = efl.get_installed_resources_file(deployment_home)
    if not os.path.exists(filepath):
        raise Exception("Installed resources file does not exist at %s" % filepath)
    return parse_install_soln(filepath)


def main(argv=sys.argv[1:]):
    parser = OptionParser(usage='usage: %prog [options] [output_file]')
    parser.add_option('--format', '-f', dest="format",
                      default="json",
                      help="Format of output. Valid choices are %s. Default is 'json'" %
                           ', '.join(sorted(formatter_map.keys())))
    parser.add_option("--skip", "-s", dest="skip", default=None,
                      help="If specified, a comma-separated list of package wildcards to skip")
    parser.add_option("--deployment-home", "-d", dest="deployment_home",
                      default=None,
                      help="Location of deployed application - can figure this out autmatically unless installing from source")
    (options, args) = parser.parse_args(args=argv)
    if options.format not in formatter_map.keys():
        parser.error("%s is not a valid format" % options.format)
    installed_resources = load_installed_resources(options, parser)
    if len(args)>1:
        parser.error("Specify one argument: output_file")
    write_report(options.format, installed_resources,
                 output_file=args[0] if len(args)==1 else None,
                 skip=options.skip.split(',') if options.skip else None)
    return 0

if __name__=="__main__":
    sys.exit(main())

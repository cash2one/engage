"""Utilities for dealing with json-based metadata files (e.g. software library,
   config file).
"""
import sys

class ParseError(Exception):
    pass

def _hash_string_for_key(key_map):
    """Since dicts are mutable, python won't let you use them as a hash key.
    In cases where we want to use a resource key as a dict key, we need to
    convert the resource key to a string.
    """
    keys = key_map.keys()
    keys.sort()
    return ",".join([key_name+":"+key_map[key_name].__str__()
                     for key_name in keys])


def _has_matching_prop(port_map, prop_list, value):
    """Helper function to check a port or port map to see if it has a
    matching property. The qualified property name has already been parsed into
    a list.

    >>> _has_matching_prop({"foo":{"bar":5}}, ["foo", "bar"], 5)
    True
    >>> _has_matching_prop({"foo":{"bar":5}}, ["foo", "bar"], 6)
    False
    >>> _has_matching_prop({"foo":{"bat":5}}, ["foo", "bar"], 5)
    False
    """
    map = port_map
    for prop in prop_list[:(len(prop_list)-1)]:
        if not map.has_key(prop): return False
        map = map[prop]
    last_prop = prop_list[len(prop_list)-1]
    if (not map.has_key(last_prop)) or (not (map[last_prop]==value)):
        return False
    else: return True


def _is_valid_for_resource(target_key, target_match_properties, resource_md):
    """This method checks whether the target is valid for the resource
    whose metadata is provided. This is done by first verifying that the
    keys match exactly. Then, it compares each of the provided match
    properties to see that they are present in the resource and have the
    same value. Match properties are specified using a "dot-separated" notation
    and must start with config_port, input_ports, or output_ports.

    >>> key = {u"name":u"p1"}
    >>> match = {u"config_port.os":u"mac-osx"}
    >>> from engage.drivers.resource_metadata import ResourceMD
    >>> rmd = ResourceMD(u"r1", {u"name":u"p1"},
    ...                  config_port={u"os":u"mac-osx"})
    >>> _is_valid_for_resource(key, match, rmd)
    True
    >>> rmd2 = ResourceMD(u"r1", {u"name":u"p1"},
    ...                   config_port={u"os":u"windows-xp"})
    >>> _is_valid_for_resource(key, match, rmd2)
    False
    """
    if target_key != resource_md.key: 
        return False
    for property in target_match_properties.keys():
        prop_list = property.split(".")
        if prop_list[0]=="config_port":
            if not _has_matching_prop(resource_md.config_port,
                                      prop_list[1:],
                                      target_match_properties[property]):
                return False
        elif prop_list[0]=="input_ports":
            if not _has_matching_prop(resource_md.input_ports,
                                      prop_list[1:],
                                      target_match_properties[property]):
                return False
        elif prop_list[0]=="output_ports":
            if not _has_matching_prop(resource_md.output_ports,
                                      prop_list[1:],
                                      target_match_properties[property]):
                return False
        else:
            assert 0, "Unexpected port type in resource: %s" % prop_list[0]
    return True # key matches and no mismatched properties

class MetadataContainer:
    """This class implements a container for metadata objects which are
    identified by a resource key and a set of properties which match have
    matching values in a provided resource. Each object added to this container
    must have two properties: key and match_properties.
    
    >>> container = MetadataContainer()
    >>> from engage.drivers.resource_metadata import ResourceMD
    >>> rmd = ResourceMD(u"r1", {u"name":u"p1"},
    ...                  config_port={u"os":u"mac-osx"})
    >>> rmd2 = ResourceMD(u"r1", {u"name":u"p2"},
    ...                   config_port={u"os":u"windows-xp"})
    >>> class Entry:
    ...     def __init__(self, id, key, match_properties):
    ...         self.id = id
    ...         self.key = key
    ...         self.match_properties = match_properties
    >>>
    >>> e1 = Entry(1, {u"name":u"p1"}, {u"config_port.os":u"mac-osx"})
    >>> container.add_entry(e1)
    >>> e2 = Entry(2, {u"name":u"p1"}, {u"config_port.os":u"windows-xp"})
    >>> container.add_entry(e2)
    >>> e3 = Entry(3, {u"name":u"p2"}, {u"config_port.os":u"windows-xp"})
    >>> container.add_entry(e3)
    >>> print container.get_entry(rmd).id
    1
    >>> print container.get_entry(rmd2).id
    3
    """
    def __init__(self):
        """We store the entries in a map, where the key is a stringified
        version of the resource key and the value is a list of entries with
        that key."""
        self.entries = {}

    def add_entry(self, entry):
        """Add an etry to the table. Note that, for a given key, we could have
        multiple entries, even with overlapping match properties. We always
        add new entries to the end of the list and get_entry() returns the
        first match with the resource metadata.
        """
        key_hash = _hash_string_for_key(entry.key)
        if self.entries.has_key(key_hash):
            self.entries[key_hash].append(entry)
        else:
            self.entries[key_hash] = [entry]

    def get_entry(self, resource_md):
        key_hash = _hash_string_for_key(resource_md.key)
        if not self.entries.has_key(key_hash):
            return None
        for entry in self.entries[key_hash]:
            if _is_valid_for_resource(entry.key, entry.match_properties,
                                      resource_md):
                return entry
        return None

    def entries(self):
        """Generator which enumerates all the entries"""
        for k in self.entries.keys():
            for e in self.entries[k]:
                yield e


class UnionType(object):
    def __init__(self, *args):
        self.valid_types = args

    def check(self, value, msg):
        for t in self.valid_types:
            if isinstance(value, t):
                return
        raise ParseError, \
              "%s, is the wrong type, value was '%s', expecting one of %s" \
              (msg, value, self.valid_types.__repr__())

def check_json_type(value, expected_type, msg):
    if isinstance(expected_type, UnionType):
        expected_type.check(value, msg)
    elif not isinstance(value, expected_type):
        if value=='' and expected_type==unicode:
            # This is a special case -- the json parser changed in 2.7
            # and returns a non-unicode string for empty string values
            # (but unicode for regular values)
            return
        if expected_type == str: correct_type = "string"
        elif expected_type == unicode: correct_type = "string(unicode)"
        elif expected_type == dict: correct_type = "map"
        elif expected_type == list: correct_type = "list"
        else: correct_type = expected_type.__str__()
        raise ParseError, \
            "%s, is the wrong type, should be type %s (value was '%s', type was %s)"\
            % (msg, correct_type, value, type(value))


def get_json_property(prop_name, map, expected_type, msg):
    if not map.has_key(prop_name):
        raise ParseError, \
            "%s missing required property '%s'" % (msg, prop_name)
    value = map[prop_name]
    check_json_type(value, expected_type,
                     "%s property '%s'" % (msg, prop_name))
    return value


def get_opt_json_property(prop_name, map, expected_type, msg, default):
    if not map.has_key(prop_name):
        return default
    value = map[prop_name]
    check_json_type(value, expected_type,
                     "%s property '%s'" % (msg, prop_name))
    return value


def _test():
    print "Running tests for %s ..." % sys.argv[0]
    import doctest
    results = doctest.testmod()
    if results.failed>0: sys.exit(1)

if __name__ == "__main__": _test()

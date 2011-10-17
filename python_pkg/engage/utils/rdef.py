#!/usr/bin/env python
"""Resource definition parsing and representation functions.

If run as a script, will parse and validate the specified file.
"""

import sys
import json
from optparse import OptionParser
import re
import copy
import os.path

            
            
RESOURCE_DEFINITIONS_PROP = u"resource_definitions"
RESOURCE_DEF_VERSION_PROP = u"resource_def_version"
RESOURCE_DEF_VERSION = u"1.0"
ONE_OF_CONSTRAINT = u"one-of"
ALL_OF_CONSTRAINT = u"all-of"
BASE_CONSTRAINT = u"base"

DEBUG = False

def debug(msg):
    if DEBUG:
        print msg


class ParseException(Exception):
    pass


def version_to_label(version):
    GT = u"greater-than"
    GTE = u"greater-than-or-equal"
    LT = u"less-than"
    LTE = u"less-than-or-equal"
    if len(version.keys()) == 1:
        if version.has_key(GT):
            return ">%s" % version[GT]
        if version.has_key(GTE):
            return ">=%s" % version[GTE]
        if version.has_key(LT):
            return "<%s" % version[LT]
        if version.has_key(LTE):
            return "<=%s" % version[LTE]
    else: # both a greater than and less than
        if version.has_key(GT):
            s = ">%s" % version[GT]
        else:
            s = ">=%s" % version[GTE]
        if version.has_key(LT):
            return "%s,<%s" % (s, version[LT])
        else:
            return "%s,<=%s" % (s, version[LTE])
    
def key_to_string(key):
    GT = u"greater-than"
    GTE = u"greater-than-or-equal"
    LT = u"less-than"
    LTE = u"less-than-or-equal"

    name = key[u"name"]
    version = key[u"version"]
    if (type(version)) == unicode or (type(version)==str):
        return "%s %s" % (name, version)
    else:
        assert type(version) == dict, "Unexpected key version in key %s" % key.__repr__()
        if version.has_key(GT):
            s = "%s < %s" % (version[GT], name)
        elif version.has_key(GTE):
            s = "%s <= %s" % (version[GTE], name)
        else:
            s = name
        if version.has_key(LT):
            s = "%s < %s" % (s, version[LT])
        elif version.has_key(LTE):
            s = "%s <= %s" % (s, version[LTE])
        return s

def key_to_node_name(key):
    subst_list = [(",", ""), ("\*", "any"), ("\>=", "_ge_"), ("\<=", "_le_"), ("\>", "_gt_"), ("\<", "_lt_"), ("-", "_"), ("\.", "_"), (" ", ""), ("\+", "plus")]
    s = key_to_string(key)
    for (o, n) in subst_list:
        s = re.sub(o, n, s)
    return "n" + s

def is_specific_version_constraint(target_constraint):
    target_key = target_constraint[u"key"]
    version_type = type(target_key[u"version"])
    return (version_type==str) or (version_type==unicode)

def version_matches_constraint(version, constraint):
    """Return true if the version string matches the constraint
    """
    GT = u"greater-than"
    GTE = u"greater-than-or-equal"
    LT = u"less-than"
    LTE = u"less-than-or-equal"
    if version == constraint:
        return True # special case for specific version constraints
    elif type(constraint) != dict:
        return False
    # otherwise, check that all the constraints present are satisfied
    if constraint.has_key(GT) and not (version > constraint[GT]):
        return False
    if constraint.has_key(GTE) and not (version >= constraint[GTE]):
        return False
    if constraint.has_key(LT) and not (version < constraint[LT]):
        return False
    if constraint.has_key(LTE) and not (version <= constraint[LTE]):
        return False
    return True


# map from constraint node name to actual constraint
constraint_nodes = {}

# unique id for constraint nodes
next_uid = 1

class ConstraintMap(object):
    """Keep track of constraints when printing. We want to combine equivalent nodes in the graph.
    """
    def __init__(self):
        self.map = {}
        self.next_id = 0
    def _get_label(self, constraint):
        self.next_id = self.next_id + 1
        return ("%s_%03d" % (constraint.get_constraint_type(), self.next_id)).replace("-", "_")
    def get_or_add_entry(self, constraint):
        """Returns a pair: (found, label)
        found is True if the constraint node already exists, False otherwise.
        label is the label for the constraint node.
        """
        hv = constraint.hash()
        if self.map.has_key(hv):
            clist = self.map[hv]
            for (other_constraint, label) in clist:
                if other_constraint.is_equivalent(constraint):
                    return (True, label)
            # didn't find a match
            label = self._get_label(constraint)
            clist.append((constraint, label))
            return (False, label)
        else:
            label = self._get_label(constraint)
            self.map[hv] = [(constraint,label)]
            return (False, label)

cmap = ConstraintMap()


def write_direct_link(of, source_node, target_constraint, res_by_name, style):
    assert target_constraint.is_base_constraint()
    target_key = target_constraint.key
    if not target_constraint.is_specific_version_constraint():
        (already_exists, target_node_label) = cmap.get_or_add_entry(target_constraint)
        if not already_exists:
            # the first time we encounter a constraint, create a node for it
            of.write("  %s [shape=box, label=\"%s\", style=\"filled\", fillcolor=\"yellow\"];\n" % (target_node_label,key_to_string(target_key)))
            # draw the links to the specific target resources
            for res in res_by_name[target_constraint.name]:
                if target_constraint.matches_key(res.key):
                    of.write("  %s -> %s [color=\"%s\"];\n" % (target_node_label, key_to_node_name(res.key), "red"))
    else:
        target_node_label = key_to_node_name(target_key)
    of.write("  %s -> %s [style=\"%s\"];\n" % (source_node, target_node_label, style))


def write_one_of_link(of, source_node, one_of_constraint, res_by_name, style):
    (already_exists, one_of_node) = cmap.get_or_add_entry(one_of_constraint)
    if not already_exists:
        of.write("  %s [shape=\"oval\", label=\"one-of\"];\n" % one_of_node)
        for target_constraint in one_of_constraint.constraint_list:
            write_direct_link(of, one_of_node, target_constraint, res_by_name, style)
    of.write("  %s -> %s [style=\"%s\"];\n" % (source_node, one_of_node, style))

def write_all_of_link(of, source_node, all_of_constraint, res_by_name, style):
    (already_exists, all_of_node) = cmap.get_or_add_entry(all_of_constraint)
    if not already_exists:
        of.write("  %s [shape=\"oval\", label=\"all-of\"];\n" % all_of_node)
        for target_constraint in all_of_constraint.constraint_list:
            if target_constraint.is_one_of_constraint():
                write_one_of_link(of, all_of_node, target_constraint, res_by_name, style)
            else:
                write_direct_link(of, all_of_node, target_constraint, res_by_name, style)
    of.write("  %s -> %s [style=\"%s\"];\n" % (source_node, all_of_node, style))

# map from resource names to sets of versions
resources_by_name = {}

class ValidationResults(object):
    def __init__(self):
        self.errors = 0
        self.warnings = 0

    def add_error(self):
        self.errors += 1

    def add_warning(self):
        self.warnings += 1

    
class Constraint(object):
    def is_base_constraint(self):
        return self.get_constraint_type()==BASE_CONSTRAINT
    def is_one_of_constraint(self):
        return self.get_constraint_type()==ONE_OF_CONSTRAINT
    def is_all_of_constraint(self):
        return self.get_constraint_type()==ALL_OF_CONSTRAINT
    def get_constraint_type(self):
        pass
    def find_all_matching(self, resources_by_name):
        """Return a set of matching resources"""
        pass
    def write_link_to_graph_file(self, file, src_node, res_by_name, style):
        pass
    def is_equivalent(self, other):
        """Return true if the constraints are equivalent.
        """
        raise Exception("Not implemented")
    def hash(self):
        raise Exception("Not implemented")
    def validate(self, res_map, res_by_name, vr):
        """Validate the constraint and return the number of (errors, warnings) found.
        """
        raise Exception("Not implemented")
        

class BaseConstraint(Constraint):
    def __init__(self, json_dict, parent_resource):
        self.json_dict = json_dict
        self.parent_resource = parent_resource
        assert json_dict.has_key(u"key"), "Resource %s has invalid base constraint '%s'" % \
                                          (parent_resource.key_as_string, json_dict.__repr__())
        self.key = json_dict[u"key"]
        assert self.key.has_key(u"name"), "Resource %s has invalid base constraint '%s': missing name" % \
                                          (parent_resource.key_as_string, json_dict.__repr__())
        self.name = self.key[u"name"]
        assert self.key.has_key(u"version"), "Resource %s has invalid base constraint '%s': missing version" % \
                                          (parent_resource.key_as_string, json_dict.__repr__())
        self.version_constraint = self.key[u"version"]
        if (type(self.version_constraint)==str) or (type(self.version_constraint)==unicode):
            self.targets_specific_version = True
        else:
            self.targets_specific_version = False
        if json_dict.has_key(u"port_mapping"):
            self.port_mapping = json_dict[u"port_mapping"]
        else:
            self.port_mapping = {}

    def __str__(self):
        return self.json_dict.__repr__()

    def get_constraint_type(self):
        return BASE_CONSTRAINT

    def hash(self):
        return hash(self.name)

    def is_specific_version_constraint(self):
        return self.targets_specific_version
    
    def matches_key(self, key):
        match_name = key[u"name"]
        match_version = key[u"version"]
        if self.name != match_name:
            #print "matches_key failed name=%s, version=%s" % (match_name, match_version) # XXX
            return False
        else:
            result = version_matches_constraint(match_version, self.version_constraint)
            #print "matches_key %s name=%s, version=%s" % (result, match_name, match_version) # XXX
            return result

    def find_all_matching(self, resources_by_name):
        if not resources_by_name.has_key(self.name):
            print "WARNING: Constraint '%s' in resource '%s' has no matching resources" % (self, self.parent_resource.key_as_string)
            return set()
        candidates = resources_by_name[self.name]
        result_set = set()
        for candidate in candidates:
            if self.matches_key(candidate.key):
                result_set.add(candidate.key_as_string)
        if len(result_set)==0:
            print "WARNING: Constraint '%s' in resource '%s' has no matching resources" % (self, self.parent_resource.key_as_string)
            if DEBUG:
                print "potential matches:"
                for res in resources_by_name[self.name]:
                    print " %s" % res
        return result_set

    def write_link_to_graph_file(self, file, src_node, res_by_name, style):
        write_direct_link(file, src_node, self, res_by_name, style)

    def is_equivalent(self, other):
        if not other.is_base_constraint():
            return False
        else:
            return (self.name == other.name) and (self.version_constraint == other.version_constraint)

    def validate(self, res_map, resources_by_name, vr):
        """Validate a single base constraint
        """
        matching = self.find_all_matching(resources_by_name)
        if len(matching)==0:
            vr.add_warning()
        for port in self.port_mapping.keys():
            if not self.parent_resource.input_ports.has_key(port):
                print "ERROR: Resource %s has constraint referencing undefined input port %s" % (self.parent_resource.key_as_string,
                                                                                                 port)
                vr.add_error()
                continue
            # We check the associated port in each matching resource to see that they provide
            # the properties expected by this resource
            for rkey in matching:
                r = res_map[rkey]
                if r.output_ports.has_key(self.port_mapping[port]):
                    output_port = r.output_ports[self.port_mapping[port]]
                    for prop in self.parent_resource.input_ports[port].properties.keys():
                        if not output_port.properties.has_key(prop):
                            print "ERROR: Resource %s has constraint which references non-existant property output_ports.%s.%s in resource %s" % \
                                  (self.parent_resource.key_as_string, self.port_mapping[port], prop, rkey)
                            vr.add_error()
                else:
                    print "ERROR: Resource %s has constraint which references non-existant output port %s on resource %s" % \
                          (self.parent_resource.key_as_string, self.port_mapping[port], rkey)
                    vr.add_error()
                        
                


class CompositeConstraint(Constraint):
    def is_equivalent(self, other):
        if (self.get_constraint_type()!=other.get_constraint_type()) or \
           (len(self.constraint_list)!=len(other.constraint_list)) or \
           self.hash()!=other.hash():
            return False
        # if we get here, we have lists of the same length. The orders could
        # be different, so need to compare each pair
        other_list = copy.copy(other.constraint_list)
        for sc in self.constraint_list:
            found = False
            for i in range(len(other_list)):
                if other_list[i].is_equivalent(sc):
                    del other_list[i]
                    found = True
                    break
            if not found:
                return False
        return True

    def hash(self):
        """This should always return the same value for equivalent constraints.
        We rely on the fact that xor is commutative
        """
        if len(self.constraint_list)==0:
            return 0
        else:
            hv = self.constraint_list[0].hash()
            for i in range(1,len(self.constraint_list)):
                hv = hv ^ self.constraint_list[i].hash()
            return hv


class OneOfConstraint(CompositeConstraint):
    def __init__(self, json_dict, parent_resource):
        assert json_dict.has_key(ONE_OF_CONSTRAINT)
        assert type(json_dict[ONE_OF_CONSTRAINT])==list, "One-of constraint in resource %s is of wrong type: '%s'" % \
                                                 (parent_resource.key_as_string, json_dict[ONE_OF_CONSTRAINT].__repr__())
        self.json_dict = json_dict
        self.constraint_list = []
        for constraint_dict in json_dict[ONE_OF_CONSTRAINT]:
            self.constraint_list.append(BaseConstraint(constraint_dict, parent_resource))

    def get_constraint_type(self):
        return ONE_OF_CONSTRAINT

    def __str__(self):
        return self.json_dict.__repr__()
    
    def find_all_matching(self, resources_by_name):
        result_set = set()
        for constraint in self.constraint_list:
            result_set = result_set.union(constraint.find_all_matching(resources_by_name))
        return result_set

    def write_link_to_graph_file(self, file, src_node, res_by_name, style):
        write_one_of_link(file, src_node, self, res_by_name, style)
        
    def validate(self, res_map, resources_by_name, vr):
        for constraint in self.constraint_list:
            constraint.validate(res_map, resources_by_name, vr)


class AllOfConstraint(CompositeConstraint):
    def __init__(self, json_dict, parent_resource):
        self.json_dict = json_dict
        assert json_dict.has_key(ALL_OF_CONSTRAINT)
        assert type(json_dict[ALL_OF_CONSTRAINT])==list, "All-of constraint in resource %s is of wrong type: '%s'" % \
                                                 (parent_resource.key_as_string, json_dict[ALL_OF_CONSTRAINT].__repr__())
        self.constraint_list = []
        for constraint_dict in json_dict[ALL_OF_CONSTRAINT]:
            if constraint_dict.has_key(ONE_OF_CONSTRAINT):
                self.constraint_list.append(OneOfConstraint(constraint_dict, parent_resource))
            else:
                self.constraint_list.append(BaseConstraint(constraint_dict, parent_resource))

    def get_constraint_type(self):
        return ALL_OF_CONSTRAINT

    def find_all_matching(self, resources_by_name):
        result_set = set()
        for constraint in self.constraint_list:
            result_set = result_set.union(constraint.find_all_matching(resources_by_name))
        return result_set

    def write_link_to_graph_file(self, file, src_node, res_by_name, style):
        write_all_of_link(file, src_node, self, res_by_name, style)

    def validate(self, res_map, resources_by_name, vr):
        for constraint in self.constraint_list:
            constraint.validate(res_map, resources_by_name, vr)


def create_constraint(json_dict, parent_resource):
    if json_dict.has_key(ALL_OF_CONSTRAINT):
        return AllOfConstraint(json_dict, parent_resource)
    elif json_dict.has_key(ONE_OF_CONSTRAINT):
        return OneOfConstraint(json_dict, parent_resource)
    else:
        return BaseConstraint(json_dict, parent_resource)


def _find_prop_refs_in_template_string(templ_string):
    p = "\\$\\{[a-zA-Z0-9_]+(?:\\.[a-zA-Z0-9_]+)*\\}"
    results = []
    for m in re.findall(p, templ_string):
        results.append(m[2:-1])
    return results

class PropRefError(Exception):
    pass

class IllFormedPropRefError(PropRefError):
    def __init__(self, ref, used_in_prop):
        Exception.__init__(self, "Invalid property reference '%s' in definition of property %s" %
                           (ref, used_in_prop))

class UndefinedPropRefError(PropRefError):
    def __init__(self, ref, used_in_prop):
        Exception.__init__(self, "Property definition %s refers to undefined property %s" %
                           (used_in_prop, ref))

class PropertyReference(object):
    def __init__(self, qprop, elements, used_in_prop, exp_element_len):
        self.qprop = qprop
        self.elements = elements
        self.used_in_prop = used_in_prop
        if len(elements) != exp_element_len:
            raise IllFormedPropRefError(qprop, used_in_prop)

        
class ConfigPropertyReference(PropertyReference):
    def __init__(self, qprop, elements, used_in_prop):
        PropertyReference.__init__(self, qprop, elements, used_in_prop, 2)

    def validate(self, resource):
        if (not resource.config_port.properties.has_key(self.elements[1])):
            raise UndefinedPropRefError(self.qprop, self.used_in_prop)

class InputPropertyReference(PropertyReference):
    def __init__(self, qprop, elements, used_in_prop):
        PropertyReference.__init__(self, qprop, elements, used_in_prop, 3)

    def validate(self, resource):
        if (not resource.input_ports.has_key(self.elements[1])) or \
           (not resource.input_ports[self.elements[1]].properties.has_key(self.elements[2])):
            raise UndefinedPropRefError(self.qprop, self.used_in_prop)

class OutputPropertyReference(PropertyReference):
    def __init__(self, qprop, elements, used_in_prop):
        PropertyReference.__init__(self, qprop, elements, used_in_prop, 3)

    def validate(self, resource):
        if (not resource.output_ports.has_key(self.elements[1])) or \
           (not resource.output_ports[self.elements[1]].properties.has_key(self.elements[2])):
            raise UndefinedPropRefError(self.qprop, self.used_in_prop)


def create_property_reference(qprop, used_in_prop):
    elements = qprop.split(".")
    if elements[0]=="config_port":
        return ConfigPropertyReference(qprop, elements, used_in_prop)
    elif elements[0]=="input_ports":
        return InputPropertyReference(qprop, elements, used_in_prop)
    elif elements[0]=="output_ports":
        return OutputPropertyReference(qprop, elements, used_in_prop)
    else:
        raise IllFormedPropRefError(qprop, used_in_prop)

def _is_string(obj):
    return isinstance(obj, str) or isinstance(obj, unicode)

class PortProperty(object):
    def __init__(self, name, json, parent):
        self.name = name
        self.qualified_name = parent + "." + self.name
        self.json = json
        self.referenced_prop_values = [] # list of other properties referenced
        if isinstance(json, str) or isinstance(json, unicode):
            self.prop_type = json
        else:
            if not isinstance(json, dict) or not json.has_key("type"):
                raise ParseException("Property %s has invalid definition. Value was %s" %
                                     (self.qualified_name, json.__repr__()))
            self.prop_type = json["type"]
            if json.has_key("source"):
                self.referenced_prop_values.append(json["source"])
            if json.has_key("default") and _is_string(json["default"]):
                self.referenced_prop_values.extend(_find_prop_refs_in_template_string(json["default"]))
            if json.has_key("fixed-value") and _is_string(json["fixed-value"]):
                self.referenced_prop_values.extend(_find_prop_refs_in_template_string(json["fixed-value"]))

    def validate(self, parent_resource, vr):
        for qprop in self.referenced_prop_values:
            try:
                prop_ref = create_property_reference(qprop, self.qualified_name)
                prop_ref.validate(parent_resource)
            except PropRefError, msg:
                print "ERROR: " + msg.__str__()
                vr.add_error()
                                                   


class Port(object):
    INPUT = "input_ports"
    OUTPUT = "output_ports"
    CONFIG = "config_ports"
    def __init__(self, name, port_type, json, resource_key):
        self.name = name
        assert port_type in [Port.INPUT, Port.OUTPUT, Port.CONFIG]
        self.port_type = port_type
        if self.port_type == Port.CONFIG:
            self.qualified_name = resource_key + ".config_port"
        else:
            self.qualified_name = resource_key + "." + self.port_type + "." + self.name
        self.properties = {}
        for prop_name in json.keys():
            self.properties[prop_name] = PortProperty(prop_name, json[prop_name], self.qualified_name)

    def validate(self, parent_resource, vr):
        for prop_def in self.properties.values():
            prop_def.validate(parent_resource, vr)
            

class Resource(object):
    def __init__(self, json_dict):
        self.json_dict = json_dict
        assert json_dict.has_key(u"key"), "Resource definition '%s' missing key" % json_dict
        self.key = json_dict[u"key"]
        self.key_as_string = self.key.__repr__()
        if json_dict.has_key(u"inside"):
            inside = json_dict[u"inside"]
            assert not inside.has_key(ALL_OF_CONSTRAINT)
            self.inside_constraint = create_constraint(inside, self)
        else:
            self.inside_constraint = None
        if json_dict.has_key(u"environment"):
            self.env_constraint = create_constraint(json_dict[u"environment"], self)
        else:
            self.env_constraint = None
        if json_dict.has_key(u"peers"):
            self.peer_constraint = create_constraint(json_dict[u"peers"], self)
        else:
            self.peer_constraint = None
        if json_dict.has_key(u"config_port"):
            self.config_port = Port("config_port", Port.CONFIG, json_dict[u"config_port"],
                                    self.key_as_string)
        else:
            self.config_port = Port("config_port", Port.CONFIG, {}, self.key_as_string)
        self.input_ports = {}
        if json_dict.has_key(u"input_ports"):
            for port_name in json_dict[u"input_ports"].keys():
                self.input_ports[port_name] = Port(port_name, Port.INPUT,
                                                   json_dict[u"input_ports"][port_name],
                                                   self.key_as_string)
        self.output_ports = {}
        if json_dict.has_key(u"output_ports"):
            for port_name in json_dict[u"output_ports"].keys():
                self.output_ports[port_name] = Port(port_name, Port.OUTPUT,
                                                    json_dict[u"output_ports"][port_name],
                                                    self.key_as_string)

    def __str__(self):
        return self.key_as_string

    def __repr__(self):
        return self.json_dict.__repr__()

    def write_to_graph_file(self, file, res_by_name):
        label = key_to_string(self.key)
        node = key_to_node_name(self.key)
        file.write("  %s [shape=box, label=\"%s\", style=\"filled\", fillcolor=\"tan\"];\n" % (node, label))
        if self.inside_constraint:
            self.inside_constraint.write_link_to_graph_file(file, node, res_by_name, "solid")
        if self.env_constraint:
            self.env_constraint.write_link_to_graph_file(file, node, res_by_name, "dotted")
        if self.peer_constraint:
            self.peer_constraint.write_link_to_graph_file(file, node, res_by_name, "dashed")
            
    def validate(self, res_map, res_by_name, vr):
        if self.inside_constraint:
            self.inside_constraint.validate(res_map, res_by_name, vr)
        if self.env_constraint:
            self.env_constraint.validate(res_map, res_by_name, vr)
        if self.peer_constraint:
            self.peer_constraint.validate(res_map, res_by_name, vr)

        self.config_port.validate(self, vr)
        for port in self.input_ports.values():
            port.validate(self, vr)
        for port in self.output_ports.values():
            port.validate(self, vr)        


def _add_to_map_of_sets(map, key, entry):
    if map.has_key(key):
        map[key].add(entry)
    else:
        map[key] = set([entry])


def prune_resources(res_map, res_by_name, resource_keys):
    """Prune out all resources not reachable by the specified resource_key list
    """
    # our sets are sets of keys, represented as repr strings
    keep_set = set()
    work_set = set()
    for key in resource_keys:
        key_repr = key.__repr__()
        assert res_map.has_key(key_repr), "Resource '%s' not found" % key_repr
        keep_set.add(key_repr)
        work_set.add(key_repr)
    while len(work_set)>0:
        pick_key = work_set.pop()
        debug("chose resource %s" % pick_key)
        assert res_map.has_key(pick_key), "Invalid reference to resource '%s'" % pick_key
        res = res_map[pick_key]
        matching = set()
        if res.inside_constraint:
            matching = matching.union(res.inside_constraint.find_all_matching(res_by_name))
        if res.env_constraint:
            matching = matching.union(res.env_constraint.find_all_matching(res_by_name))
        if res.peer_constraint:
            matching = matching.union(res.peer_constraint.find_all_matching(res_by_name))
        new = matching.difference(keep_set)
        keep_set = keep_set.union(new)
        work_set = work_set.union(new)
    new_map = {}
    new_by_name_map = {}
    for key_as_string in keep_set:
        res = res_map[key_as_string]
        new_map[key_as_string] = res
        _add_to_map_of_sets(new_by_name_map, res.key[u"name"], res)
    return (new_map, new_by_name_map)


class ResourceGraph(object):
    """A resource graph contains two maps: 1) a map of all resources by key (in
    serialized json form), and 2) a map of resource sets by the name component of
    the key. The second map is used when looking up constraints.
    """
    def __init__(self, res_map, res_by_name):
        self.res_map = res_map
        self.res_by_name = res_by_name

    def filter(self, filter_keys):
        (new_map, new_by_name) = prune_resources(self.res_map, self.res_by_name,
                                                 filter_keys)
        return ResourceGraph(new_map, new_by_name)

    def len(self):
        return len(self.res_map.keys())

    def validate(self):
        """Validate the graph, returning a pair of the number of errors and
        warnings
        """
        print "Checking %d resources" % self.len()
        vr = ValidationResults()
        for res_key in self.res_map.keys():
            if DEBUG:
                print "Validating %s" % res_key
            self.res_map[res_key].validate(self.res_map, self.res_by_name, vr)
        return (vr.errors, vr.warnings)

    def write_to_file(self, filename):
        keys = self.res_map.keys()
        keys.sort()
        json_list = [(self.res_map[key]).json_dict for key in keys]
        with open(filename, "wb") as f:
            json.dump({RESOURCE_DEF_VERSION_PROP: RESOURCE_DEF_VERSION,
                       RESOURCE_DEFINITIONS_PROP: json_list}, f, indent=2)
            

def create_resource_graph(resource_json):
    """Create resource objects and return a resource graph. The input can be either
    the resource file (a map with a property containing the resource list) or
    just the resource list.
    """
    if isinstance(resource_json, list):
        resource_json_list = resource_json
    else:
        resource_json_list = resource_json[RESOURCE_DEFINITIONS_PROP]
    res_map = {}
    res_by_name = {}
    for res_json in resource_json_list:
        res = Resource(res_json)
        res_map[res.key_as_string] = res
        _add_to_map_of_sets(res_by_name, res.key[u"name"], res)
    return ResourceGraph(res_map, res_by_name)
                              

def create_opt_parser():
    """Returns (options, args) pair
    """
    usage = "%prog [options] resource_def_file"
    parser = OptionParser(usage=usage)
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                      default=False,
                      help="Print debug information")
    parser.add_option("-r", "--resource", dest="resource", default=None,
                      help="If specified, prune nodes unreachable from resource")
    parser.add_option("-w", "--write-res-file", dest="write_res_file",
                      default=None,
                      help="If specified, write resources to the requested file")
    return parser

def parse_resource_keys_option(keys_opt_val, parser):
    if keys_opt_val==None:
        return None
    try:
        resource_key_input = json.loads(keys_opt_val)
        if type(resource_key_input)==list:
            resource_keys = resource_key_input
        else:
            resource_keys = [resource_key_input,]
        for resource_key in resource_keys:
            if not resource_key.has_key(u"name"):
                parser.error("Resource key missing 'name' property")
            elif not resource_key.has_key(u"version"):
                parser.error("Resource key missing 'version' property")
        return resource_keys
    except Exception, e:
        parser.error("Unable to parse resource key '%s' as json: %s" %
                     (keys_opt_val, e))


def main(argv):
    parser = create_opt_parser()
    (options, args) = parser.parse_args(argv)
    if len(args) != 1:
        print "Expecting resource definition filename"
        parser.print_help()
        return -1
    filename = os.path.abspath(os.path.expanduser(args[0]))
    if not os.path.exists(filename):
        parser.error("Input file %s does not exist" % filename)
    global DEBUG
    if options.verbose:
        DEBUG = True
    resource_keys = parse_resource_keys_option(options.resource, parser)
    if options.write_res_file:
        output_file = os.path.abspath(os.path.expanduser(options.write_res_file))
        if output_file == filename:
            parser.error("Cannot overwrite input file")
    else:
        output_file = None

    with open(filename, "rb") as f:
        rg = create_resource_graph(json.load(f))

    if resource_keys:
        rg = rg.filter(resource_keys)
    if output_file:
        rg.write_to_file(output_file)
        print "Wrote resources to %s" % output_file
        
    (errors, warnings) = rg.validate()
    if errors==0 and warnings==0:
        print "Validation of resource definition file %s ok" % filename
        return 0
    else:
        print "Validation of resource definition file %s found %d errors, %d warnings" \
              % (filename, errors, warnings)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

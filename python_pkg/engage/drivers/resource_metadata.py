#
# Resource Metadata
#
import json
import sys
    
from engage.extensions import installed_extensions

import logging
logger = logging.getLogger(__name__)

class ResourceParseError(Exception):
    pass

class TypeError(Exception):
    """Exception thrown when building configuration objects if a property
    does not match its expected type or is missing."""
    pass


def _default_init_val(arg, default):
    """Needed because default reference values for formals are shared"""
    if arg==None: return default
    else: return arg

def _serialized_json(obj):
    return json.dumps(obj, sort_keys=True, indent=1)


_type_err_msg = \
  "Configuration property '%s' has wrong type: was %s, expecting %s"

def _check_type(prop_val, type_obj, qualified_name):
    if isinstance(type_obj, dict):
        if not isinstance(prop_val, dict):
            raise TypeError, _type_err_msg % \
                (qualified_name, prop_val.__class__.__name__, "dict")
    elif isinstance(type_obj, list):
        if not isinstance(prop_val, list):
            raise TypeError, _type_err_msg % \
                (qualified_name, prop_val.__class__.__name__, "list")
    else:
        # Need to relax the type check a bit for unicode, due to weirdness
        # of python 2.7 json parser
        if not isinstance(prop_val, type_obj) and (not (type_obj==unicode and isinstance(prop_val, str))):
            raise TypeError, _type_err_msg % \
                (qualified_name, prop_val.__class__.__name__,
                 type_obj.__name__)


def _make_cfgobj_list(values, item_type, _parent_prop_name):
    result = []
    for i in range(len(values)):
        qualified_name = "%s[%d]" % (_parent_prop_name, i)
        if item_type!=None:
            _check_type(values[i], item_type, qualified_name)
        if isinstance(values[i], dict):
            result.append(Config(values[i], item_type, qualified_name))
        elif isinstance(values[i], list):
            if isinstance(item_type, list):
                result.append(_make_cfg_list(values[i], item_type[0],
                                             qualified_name))
            else:
                result.append(_make_cfg_list(values[i], None,
                                             qualified_name))
        else:
            result.append(values[i])
    return result


def _back_to_json(value):
    if isinstance(value, Config):
        return value._to_json()
    elif isinstance(value, list):
        return [_back_to_json(item) for item in value]
    else:
        return value

class Config:
    """Configuration objects are used to create a more strongly-typed
    respresentation of a resource's configuration data. Resource managers
    use the get_configuration() method on ResourceMD to extract the
    configuration data they need from the resource instance. These objects
    can also be created directly, for testing purposes.

    >>> c = Config({"a":5, "b":"c"})
    >>> print c
    {
     "a": 5, 
     "b": "c"
    }
    >>> print c.a
    5
    >>> print Config({"a":5, "b":"c"}, types={"a":int, "b":str})
    {
     "a": 5, 
     "b": "c"
    }
    >>> try:
    ...     print Config({"a":"notanint", "b":"c"}, types={"a":int, "b":str})
    ... except TypeError, msg:
    ...     print msg
    Configuration property 'a' has wrong type: was str, expecting int
    >>> print Config({"scalar":True, "map":{"a":5, "b":6}, "list":[1,2,4]})
    {
     "list": [
      1, 
      2, 
      4
     ], 
     "map": {
      "a": 5, 
      "b": 6
     }, 
     "scalar": true
    }
    >>> print Config({"scalar":True, "map":{"a":5, "b":6}, "list":[1,2,4]},
    ...              types={"scalar":bool, "map":{"a":int, "b":int},
    ...                     "list":[int]})
    {
     "list": [
      1, 
      2, 
      4
     ], 
     "map": {
      "a": 5, 
      "b": 6
     }, 
     "scalar": true
    }
    >>> try:
    ...     print  Config({"scalar":True,
    ...                    "map":{"a":5, "b":6}, "list":[1,2,"bad value"]},
    ...                    types={"scalar":bool, "map":{"a":int, "b":int},
    ...                           "list":[int]})
    ... except TypeError, msg:
    ...     print msg
    Configuration property 'list[2]' has wrong type: was str, expecting int
    """
    def __init__(self, props_in, types=None, _parent_prop_name=None):
        """The props_in value is a dictionary of properties. It is converted
        to a Config instance which allows the dictionary properties to be
        accessed as normal object attributes (foo.bar instead of foo["bar"]).

        types is an optional dictionary mapping the expected properties to
        their expected types. The values in the types dictionary are
        interpreted as follows:
         - A dictionary value is interpreted as the type of a nested Config
           instance
         - A list value is interpreted as a list of nested Config instances.
           The list should have one element representing the type of the
           elements of this list.
         - A type representing the type of a scalar property. This should be
           either str, int, float, or bool.
        """
        self.__dict__["_props"] = {}
        if types!=None:
            # if we have types, first make sure all the required properties
            # are present
            for prop_name in types:
                if not props_in.has_key(prop_name):
                    if _parent_prop_name!=None:
                        qualified_name = _parent_prop_name + "." + prop_name
                    else:
                        qualified_name = prop_name
                    raise TypeError, \
                        "Configuration property '%s' missing" % qualified_name
        for (prop_name, prop_val) in props_in.items():
            if _parent_prop_name!=None:
                qualified_name = _parent_prop_name + "." + prop_name
            else:
                qualified_name = prop_name
            if types!=None and types.has_key(prop_name):
                _check_type(prop_val, types[prop_name], qualified_name)
                if isinstance(prop_val, dict):
                    child = Config(prop_val, types[prop_name], qualified_name)
                    self._props[prop_name] = child
                elif isinstance(prop_val, list):
                    self._props[prop_name] = \
                       _make_cfgobj_list(prop_val, types[prop_name][0],
                                         qualified_name)
                else:
                    self._props[prop_name] = prop_val
            else: # no type information
                if isinstance(prop_val, dict):
                    self._props[prop_name] = Config(prop_val, None,
                                                    qualified_name)
                elif isinstance(prop_val, list):
                    self._props[prop_name] = \
                       _make_cfgobj_list(prop_val, None,
                                         qualified_name)
                else:
                    self._props[prop_name] = prop_val
                

    def _to_json(self):
        """Return an in-memory json representation of this config object.
        """
        result = {}
        for (key, value) in self._props.items():
            result[key] = _back_to_json(value)
        return result

    def _add_computed_prop(self, qualified_name, value, prop_type=None,
                           _name_prefix=None):
        """Add a computed property to the config object. The name
        may be qualified (e.g. foo.bar). If so, find the property corresponding
        to the first subname and calls _add_computed_prop on that property's
        value, with the rest of the qualified name. This only works if all
        the levels of the hierarchy exist except the last. Raises TypeError
        if this runs into problems or the type does not match.

        >>> c = Config({"a":{"b":{"c":"val"}}})
        >>> c._add_computed_prop("x", 5, int)
        >>> c._add_computed_prop("a.x", 6, int)
        >>> c._add_computed_prop("a.b.z", "hi", str)
        >>> print c.x, c.a.x, c.a.b.z
        5 6 hi
        >>>
        """
        idx = qualified_name.find(".")
        if idx>0:
            prop_name = qualified_name[0:idx]
            if _name_prefix==None:
                _new_name_prefix = prop_name
            else:
                _new_name_prefix = _name_prefix + "." + prop_name
            if not self._props.has_key(prop_name):
                raise TypeError, \
                    "Unable to add computed property: property '%s' not present in configuration object" % _new_name_prefix
            prop_val = self._props[prop_name]
            if not isinstance(prop_val, Config):
                raise TypeError, \
                    "Unable to add computed property: property '%s' has wrong type: should be dict, was %s" % (_new_name_prefix, prop_val.__class__.__name__)
            prop_val._add_computed_prop(qualified_name[(idx+1):], value,
                                        prop_type,
                                        _name_prefix=_new_name_prefix)
        else: # this is the final Config object
            if _name_prefix!=None:
                full_name = _name_prefix + "." + qualified_name
            else:
                full_name = qualified_name
            if self._props.has_key(qualified_name):
                raise TypeError, \
                    "Unable to add computed property: property '%s' already present in configuration object" % full_name
            if prop_type!=None:
                _check_type(value, prop_type, full_name)
            self._props[qualified_name] = value
            



            

    def __getattr__(self, name):
        if self._props.has_key(name): return self._props[name]
        else: raise AttributeError, "%s not an attribute" % name

    def __setattr__(self, name, value):
        raise AttributeError, \
            "Error in setting attribute '%s': Configuration objects are read-only" % name

    def __str__(self): return _serialized_json(self._to_json())


def convert_resource_key_to_driver_module_names(key, prefix="engage.drivers."):
    import engage.utils.file
    candidates = []
    for submodule in (["standard",] + installed_extensions):
        candidates.append(prefix + submodule + "." + engage.utils.file.mangle_resource_key(key) + ".driver")
        ## # also convert the resource name to all lowercase
        ## candidates.append(prefix + submodule + "." + (fileutils.mangle_resource_key(key)).lower() + ".driver")
    return candidates


class ResourceRef:
    """Object representation of a resource reference"""
    def __init__(self, id, key, port_mapping=None):
        self.id = id
        self.key = key
        self.port_mapping = _default_init_val(port_mapping, {})

    def to_json(self):
        """Returns an in-memory json representation of resource reference"""
        return {u"id":self.id, u"key":self.key,
                u"port_mapping":self.port_mapping}

    def __str__(self):
        """Returns a string-json representation"""
        return _serialized_json(self.to_json())


class ResourceMD:
    """Object representation of resource instance metadata"""
    def __init__(self, id, key, properties=None, config_port=None,
                 input_ports=None, output_ports=None,
                 inside=None, environment=None, peers=None,
                 driver_module_name=None,
                 package=None):
        self.id = id
        self.key = key
        self.properties = _default_init_val(properties, {})
        self.config_port = _default_init_val(config_port, {})
        self.input_ports = _default_init_val(input_ports, {})
        self.output_ports = _default_init_val(output_ports, {})
        self.inside = inside # default is None
        self.environment = _default_init_val(environment, [])
        self.peers = _default_init_val(peers, [])
        # For new-style packages, we can optionally specify the
        # resource manager module here. Otherwise, it will guess the
        # module name based on the resource name and version.
        self.driver_module_name = driver_module_name
        self.package = package # the new-style package, if available
        if self.driver_module_name!=None and self.package==None:
            raise Exception("%s %s : For old-style packages, you need to specify the class in the resource library!" %
                            (self.key['name'], self.key['version']))

    def to_json(self):
        """Returns an in-memory json representation of resource"""
        environment = [env.to_json() for env in self.environment]
        peers = [peer.to_json() for peer in self.peers]
        resource = {u"id": self.id, u"key": self.key,
                    u"properties":self.properties,
                    u"config_port":self.config_port,
                    u"input_ports":self.input_ports,
                    u"output_ports":self.output_ports,
                    u"environment":environment,
                    u"peers":peers}
        if self.driver_module_name:
            resource[u'driver_module_name'] = self.driver_module_name
        if self.package:
            resource[u'package'] = self.package.to_json()
        if self.inside:
            resource["inside"] = self.inside.to_json()
        return resource

    def __str__(self):
        """Return a json-string representation of the resource instance."""
        return _serialized_json(self.to_json())

    def is_installed(self):
        if self.properties.has_key(u"installed") and \
           self.properties[u"installed"]:
            return True
        else:
            return False


    def set_installed(self):
        """Set the installed property to true. This is done after
        the resource has been installed successfully."""
        self.properties[u"installed"] = True

    def get_config(self, types=None, constructor=Config, *args):
        props_in = {"config_port":self.config_port,
                    "input_ports":self.input_ports,
                    "output_ports":self.output_ports}
        return constructor(props_in, types, *args)
    
    def get_resource_manager_class(self):
        """Return the class (constructor function) for the manager class
        associated with this resource. This only works with the new-style
        packages, where the driver name is either explictly specified in
        the resource definition, or we use a key to infer a driver name.
        """
        if self.driver_module_name:
            # the easy case - we are given the class, so we can import it directly
            logger.debug("Attempting to import %s" % self.driver_module_name)
            mod = __import__(self.driver_module_name)
            components = self.driver_module_name.split('.')
            for comp in components[1:]:
                mod = getattr(mod, comp)
            return getattr(mod, 'Manager')
        else:
            # harder - using a key to infer a driver name.
            driver_module_names = convert_resource_key_to_driver_module_names(self.key)
            mod = None
            for driver_module_name in driver_module_names:
                try:
                    logger.debug("Attempting to import %s" % driver_module_name)
                    mod = __import__(driver_module_name, globals(), locals(), ['Manager',], -1)
                    break
                except ImportError, e:
                    logger.debug("Could not import %s: %s" % (driver_module_name, str(e)))
            if mod==None:
                raise Exception("Did not find driver for resource type %s %s, tried module names %s" %
                                (self.key['name'], self.key['version'], ', '.join(driver_module_names)))
            return getattr(mod, 'Manager')

def _check_port_type(port_json_repr, port_name):
    """Check that the specified port is defined correctly. The port itself
    should be a dict and the keys should all be strings.
    """
    if not isinstance(port_json_repr, dict):
        raise ResourseParseError, "Port '%s' not a map" % port_name
    for key in port_json_repr.keys():
        if (not isinstance(key, str)) and (not isinstance(key, unicode)):
            raise ResourceParseError, \
                "Port '%s' contains a non-string property name: '%s'" % \
                (port_name, key.__str__())


def _check_port_map_type(port_map_json_repr, port_map_name):
    """Check that a map of ports (e.g. input or output) is defined correctly.
    """
    if not isinstance(port_map_json_repr, dict):
        raise ResourceParseError, "Port map '%s' not a map" % port_map_name
    for key in port_map_json_repr.keys():
        if (not isinstance(key, str)) and (not isinstance(key, unicode)):
            raise ResourceParseError, \
                "Port map '%s' contains a non-string port name: '%s'" % \
                (port_map_name, key.__str__())
        _check_port_type(port_map_json_repr[key], key)


def _parse_resource_ref_from_json(json_repr):
    """Parse the json in-memory representation of a resource, returning
    a ResourceRef instance."""
    if not isinstance(json_repr, dict):
        raise ResourceParseError, "Resource reference is not a map"
    if len(json_repr.keys()) == 0:
        return None # empty directory
    if json_repr.has_key(u"id"):
        id = json_repr[u"id"]
    else:
        raise ResourceParseError, "Resource reference missing 'id' property"
    if json_repr.has_key(u"key"):
        key = json_repr[u"key"]
    else:
        raise ResourceParseError, "Resource reference missing 'key' property"
    if json_repr.has_key(u"port_mapping"):
        port_mapping = json_repr[u"port_mapping"]
        if not isinstance(port_mapping, dict):
            raise ResourceParseError, \
                "Resource reference has invalid port mapping"
    else: port_mapping = None
    return ResourceRef(id, key, port_mapping)


def parse_resource_from_json(json_repr):
    """Parse the json in-memory representation of a resource, returning a
       ResourceMD instance.
       As a doctest, we parse a resource and then dump it back to JSON.

    >>> s = u'{"environment": [], "peers": [], "inside": {"port_mapping": {"host": "host"}, "id": "machine1", "key": {"version": "10.5.6", "name": "mac-osx"}}, "key": {"version": "6.0.16", "name": "apache-tomcat"}, "input_ports": {"host": {"os_type": "mac-osx", "hostname": "jfischer.local", "os_user_name": "jfischer"}}, "config_port": {"home": "/Users/jfischer/test/tomcat", "admin_user": "admin", "manager_port": 80}, "id": "tomcat-1", "output_ports": {}, "properties": {}}'
    >>> import json
    >>> js = json.loads(s)
    >>> rmd = parse_resource_from_json(js)
    >>> print json.dumps(rmd.to_json(), indent=1)
    {
     "environment": [], 
     "peers": [], 
     "inside": {
      "port_mapping": {
       "host": "host"
      }, 
      "id": "machine1", 
      "key": {
       "version": "10.5.6", 
       "name": "mac-osx"
      }
     }, 
     "key": {
      "version": "6.0.16", 
      "name": "apache-tomcat"
     }, 
     "input_ports": {
      "host": {
       "os_type": "mac-osx", 
       "hostname": "jfischer.local", 
       "os_user_name": "jfischer"
      }
     }, 
     "config_port": {
      "home": "/Users/jfischer/test/tomcat", 
      "admin_user": "admin", 
      "manager_port": 80
     }, 
     "id": "tomcat-1", 
     "output_ports": {}, 
     "properties": {}
    }
    >>>
    """
    import engage_utils.pkgmgr
    if not json_repr.has_key(u"id"):
        raise ResourceParseError, "Resource missing 'id' property"
    id = json_repr[u"id"]
    if not json_repr.has_key(u"key"):
        raise ResourceParseError, "Resource missing 'key' property"
    key = json_repr[u"key"]
    if json_repr.has_key(u"properties"):
        properties = json_repr[u"properties"]
    else:
        properties = None
    if json_repr.has_key(u"config_port"):
        config_port = json_repr[u"config_port"]
        _check_port_type(config_port, "config_port")
    else:
        config_port = None
    if json_repr.has_key(u"input_ports"):
        input_ports = json_repr[u"input_ports"]
        _check_port_map_type(input_ports, "input_ports")
    else:
        input_ports = None
    if json_repr.has_key(u"output_ports"):
        output_ports = json_repr[u"output_ports"]
        _check_port_map_type(output_ports, "output_ports")
    else:
        output_ports = None
    if json_repr.has_key(u"inside"):
        inside = _parse_resource_ref_from_json(json_repr[u"inside"])
    else:
        inside = None
    if json_repr.has_key(u"environment"):
        environment = [_parse_resource_ref_from_json(json_ref)
                       for json_ref in json_repr[u"environment"]]
    else:
        environment = None
    if json_repr.has_key(u"peers"):
        peers = [_parse_resource_ref_from_json(json_ref)
                 for json_ref in json_repr[u"peers"]]
    else:
        peers = None
    if json_repr.has_key(u"driver_module_name"):
        driver_module_name = json_repr[u"driver_module_name"]
    else:
        driver_module_name = None
    if json_repr.has_key(u"package") and json_repr[u'package']!=None:
        # check for a new-style package
        package_json = json_repr[u"package"]
        if not package_json.has_key(u'name'):
            # Package entries must have the name and version, as they can
            # exist outside the resource. For packages inside a resource
            # definition, we let you leave the name and version out and then
            # put them in before parsing the package.
            package_json[u'name'] = key[u'name']
            package_json[u'version'] = key[u'version']
        else:
            if package_json[u'name']!=key[u'name'] or \
               package_json[u'version']!=key[u'version']:
                raise Exception("Package definition within resource %s %s has different name and/or version" %
                                (key[u'name'], key[u'version']))
        package = engage_utils.pkgmgr.Package.from_json(package_json)
    else:
        package = None # new-style packages are optional. Otherwise the package is in the library.
    
    return ResourceMD(id, key, properties, config_port, input_ports,
                      output_ports, inside, environment, peers,
                      driver_module_name, package)
    

def parse_install_soln(install_soln_filename):
    """Parse a json file containing a list of instances.
    """
    with open(install_soln_filename, "rb") as f:
        resource_list_json = json.load(f)
    return [parse_resource_from_json(resource_json) for
            resource_json in resource_list_json]


def _test():
    print "Running tests for %s ..." % sys.argv[0]
    import doctest
    results = doctest.testmod()
    if results.failed>0: sys.exit(1)


if __name__ == "__main__": _test()

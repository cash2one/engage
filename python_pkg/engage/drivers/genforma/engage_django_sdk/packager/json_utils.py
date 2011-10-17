"""
Utilities related to Json objects
"""

class RequiredPropertyMissing(Exception):
    def __init__(self, prop_name, class_name):
        Exception.__init__(self,
                           "Unable to instantiate %s, missing required property %s" %
                           (class_name, prop_name))

class JsonObject(object):
    def __init__(self, json_properties, required_properties=None, prop_val_dict=None,
                 prop_val_obj=None):
        self._json_properties = json_properties
        if required_properties:
            required = set(required_properties)
        else:
            required = set()
        ## assert prop_val_dict==None or prop_val_obj==None, \
        ##        "Specify initial properties as either a dict or an object, but not both"
        if prop_val_dict and prop_val_obj:
            has_both = True
        else:
            has_both = False
        for prop in json_properties:
            assert prop not in self.__dict__.keys(), "Cannot add property '%s' to object - already present" % prop
            assert not (has_both and prop_val_dict.has_key(prop) and
                        hasattr(prop_val_obj, prop)), \
                "Property %s has values provided in both dict and object" % prop
            if prop_val_dict and prop_val_dict.has_key(prop):
                v = prop_val_dict[prop]
            elif prop_val_obj and hasattr(prop_val_obj, prop):
                v = getattr(prop_val_obj, prop)
            else:
                v = None
                if (prop in required):
                    raise RequiredPropertyMissing(prop, self.__class__.__name__)
            self.__dict__[prop] = v

    def to_json(self):
        v = {}
        for p in self._json_properties:
            v[p] = self.__dict__[p]
        return v
            


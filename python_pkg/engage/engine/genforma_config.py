"""Parse genforma configuration file (genforma_config.json). This is the
file used by the installer to indicate the location of the other configuration files
"""

import json
import os.path

from engage.utils.path import dir_path_is_writable
from engage.utils.log_setup import setup_engage_logger
logger = setup_engage_logger(__name__)

class GenformaConfigError(Exception):
    pass

class ValidationResults(object):
    """This is the class returned by the validate() method
    of ConfigPropertyType and its subclasses. The base class
    maintains the result (True if successful, False otherwise)
    and the error_message, if any. Subclasses may add additional
    state (e.g. config data retrieved from an application archive
    validation).
    """
    def __init__(self, result, error_message=None):
        self.result = result
        assert result or ((not result) and error_message), \
               "If validation failed, must provide an error message"
        self.error_message = error_message

    def successful(self):
        return self.result

    def get_error_message(self):
        return self.error_message


class ConfigPropertyType(object):
    def __init__(self, name):
        self.name = name

    def validate(self, data, config_choice_history=None):
        raise Exception("validate not implemented for %s" % self.__class__.__name__)
    
    def get_default(self, default_base_value, config_choice_history):
        """Default values may be modified based on previous configuration choices.
        """
        return default_base_value
    
    def convert_to_json_type(self, data, config_choice_history):
        return data


class StringType(ConfigPropertyType):
    NAME = "string"
    def __init__(self):
        ConfigPropertyType.__init__(self, StringType.NAME)

    def validate(self, data, config_choice_history=None):
        assert type(data)==str or type(data)==unicode, "All raw values passed to the validator should be string, got %s instead" % type(data)
        return ValidationResults(True)


class PasswordType(ConfigPropertyType):
    NAME = "password"
    def __init__(self):
        ConfigPropertyType.__init__(self, PasswordType.NAME)

    def validate(self, data, config_choice_history=None):
        assert type(data)==str or type(data)==unicode, "passwords should be string, got %s instead" % type(data)
        return ValidationResults(True)


class IntType(ConfigPropertyType):
    NAME = "int"
    def __init__(self):
        ConfigPropertyType.__init__(self, IntType.NAME)

    def validate(self, data, config_choice_history=None):
        try:
            v = int(data)
            return ValidationResults(True)
        except:
            return ValidationResults(False, "Unable to convert '%s' to an integer" % data)

    def convert_to_json_type(self, data, config_choice_history):
        return int(data)

class YesNoType(ConfigPropertyType):
    NAME = "yes-or-no"
    def __init__(self):
        ConfigPropertyType.__init__(self, YesNoType.NAME)

    def validate(self, data, config_choice_history=None):
        lower = data.lower()
        if lower=='yes' or lower=='no':
            return ValidationResults(True)
        else:
            return ValidationResults(False, "Must be either 'yes' or 'no'")

    def convert_to_json_type(self, data, config_choice_history):
        return data.lower()

class LocalFileType(ConfigPropertyType):
    NAME = "file"
    def __init__(self):
        ConfigPropertyType.__init__(self, LocalFileType.NAME)

    def validate(self, data, config_choice_history=None):
        path = os.path.abspath(os.path.expanduser(data))
        if os.path.exists(path):
            if os.path.isdir(path):
                return ValidationResults(False, "%s is a directory, not a file" % path)
            return ValidationResults(True)
        else:
            return ValidationResults(False, "File '%s' does not exist." % path)

    def convert_to_json_type(self, data, config_choice_history):
        return os.path.abspath(os.path.expanduser(data))


class PathToBeCreatedType(ConfigPropertyType):
    """This is for a path that does not yet necessarily exist (could be
    created by the installer). We validate that it will indeed be possible to
    create the requested path.
    """
    NAME = "path-to-be-created"
    def __init__(self):
        ConfigPropertyType.__init__(self, PathToBeCreatedType.NAME)

    def validate(self, data, config_choice_history=None):
        path = os.path.abspath(os.path.expanduser(data))
        if not dir_path_is_writable(path):
            return ValidationResults(False,
                                     "Directory '%s' either cannot be created or exists and is not writeable." % path)
        else:
            return ValidationResults(True)

    def convert_to_json_type(self, data, config_choice_history):
        return os.path.abspath(os.path.expanduser(data))


class InstallSubdirType(ConfigPropertyType):
    NAME = "install-subdir"
    def __init__(self):
        ConfigPropertyType.__init__(self, LocalFileType.NAME)

    def validate(self, data, config_choice_history=None):
        if config_choice_history:
            install_path = os.path.abspath(os.path.expanduser(config_choice_history["Install directory"]))
        else:
            install_path = None
        if os.path.isabs(data): # if absolute, we need verify that this is indeed a subdirectory
            if install_path==None or data.startswith(install_path):
                return ValidationResults(True)
            else:
                return ValidationResults(False, "%s must be a subdirectory of %s" % (data, install_path))
        else: # relative paths should only be one directory down
            if os.path.normpath(data).find("/")!=(-1):
                return ValidationResults(False, "%s must be a direct subdirectory of the install directory" % data)
            else:
                return ValidationResults(True)
            
    def convert_to_json_type(self, data, config_choice_history):
        if os.path.isabs(data):
            return os.path.abspath(os.path.expanduser(data))
        else:
            install_path = os.path.abspath(os.path.expanduser(config_choice_history["Install directory"]))
            return os.path.join(install_path, data)



_config_prop_type_map = {
    StringType.NAME: StringType,
    PasswordType.NAME: PasswordType,
    IntType.NAME: IntType,
    LocalFileType.NAME: LocalFileType,
    PathToBeCreatedType.NAME: PathToBeCreatedType,
    InstallSubdirType.NAME: InstallSubdirType,
    YesNoType.NAME: YesNoType
}

def add_config_prop_type(prop_type):
    _config_prop_type_map[prop_type.NAME] = prop_type

CONFIG_PROPERTY_TYPES = _config_prop_type_map.keys()

class AppArchiveValidator(object):
    """Base type for application archives. An application archive may be
    packaged with metdata containing additional dependencies. We signal
    that we have an application archive by subclassing from this class.
    """
    def __init__(self, resource, property_name, description, archive_type, value):
        self.resource = resource
        self.property_name = property_name
        self.description = description
        self.archive_type = archive_type
        self.value = value

    def validate(self, prev_app_comps=None):
        pass
    
    def get_app_dependency_resources(self, machine_id, machine_key):
        """Returns a list of additional resource instances to be added to
        the install spec. Must run validate() before calling this method.
        """
        logger.debug('get_app_dependency_resources: base class, returns []')
        return []

    def get_app_dependency_names(self):
        """Returns a list of additional components required by the application
        archive. This is used to populate the config choice history for use
        in upgrades.
        """
        return []

    def get_additional_config_props(self, machine_id, machine_key):
        """Returns a list of the json representation of any additional
        configuration properties that need to be set by the user
        due to the dependent resources.
        """
        return []

class DjangoArchiveValidator(AppArchiveValidator):
    ARCHIVE_TYPE = "django-archive"
    def __init__(self, resource, property_name, description, value):
        AppArchiveValidator.__init__(self, resource, property_name,
                                     description,
                                     DjangoArchiveValidator.ARCHIVE_TYPE,
                                     value)
        self.django_config = None
        
    def validate(self, prev_app_comps=None):
        # TODO: convert exceptions to user error
        try:
            from engage.drivers.genforma.engage_django_sdk.packager \
                 import run_safe_validations_on_archive
            (common_dir, django_config) = \
                         run_safe_validations_on_archive(self.value)
            self.django_config = django_config
        except Exception, e:
            if prev_app_comps:
                # we are not running interactively
                raise
            else:
                logger.exception("Exception in application validation")
                return ValidationResults(False,
                           "Exception in application validation: %s" %
                           e.__repr__())
        return ValidationResults(True)

    def get_app_dependency_names(self):
        assert self.django_config
        return self.django_config.components

    def get_app_dependency_resources(self, machine_id, machine_key):
        from engage.drivers.genforma.engage_django_sdk.packager.engage_django_components \
             import get_resource_specs
        return get_resource_specs(self.django_config.components, machine_id,
                                  machine_key)

    def get_additional_config_props(self, machine_id, machine_key):
        from engage.drivers.genforma.engage_django_sdk.packager.engage_django_components \
             import get_additional_config_props
        return get_additional_config_props(self.django_config.components, machine_id,
                                           machine_key)

_app_archive_validator_map = {
    DjangoArchiveValidator.ARCHIVE_TYPE: DjangoArchiveValidator
}


class ConfigProperty(object):
    def __init__(self, resource, name, typename, description, default=None, optional=None):
        self.resource = resource
        self.name = name
        self.typename = typename
        self.description = description
        type_constructor = _config_prop_type_map[typename]
        self.type = type_constructor()
        self.default = default
        if default != None:
            assert self.type.validate(default), "default value '%s' is not valid for type %s" % (self.default, self.typename)
        if optional != None:
            self.optional = optional
        else:
            self.optional = False
        assert not (self.default!=None and self.optional),\
               "Property %s in resource %s: cannot have a configuration property that is optional and has a default value" % \
               (resource, name)


class GenformaConfig(object):
    def __init__(self, config_dir, resource_def_file_name, install_spec_options, software_library_file_name,
                 log_level, application_name,
                 application_archive):
        self.config_dir = config_dir
        self.resource_def_file_name = resource_def_file_name
        self.install_spec_options = install_spec_options
        self.software_library_file_name = software_library_file_name
        self.log_level = log_level
        self.application_name = application_name
        self.application_archive = application_archive

    def get_config_properties_for_install_spec(self, install_spec_choice_number):
        spec = self.install_spec_options[install_spec_choice_number]
        if spec.has_key(u"config_properties"):
            return [ConfigProperty(prop[u"resource"], prop[u"name"],
                                   prop[u"type"], prop[u"description"],
                                   (lambda p: p[u"default"] if p.has_key(u"default") else None)(prop),
                                   (lambda p: p[u"optional"] if p.has_key(u"optional") else None)(prop))
                    for prop in spec[u"config_properties"]]
        else:
            return []

    def has_application_archive(self):
        return self.application_archive != None

    def get_application_archive_validator(self, app_archive_path):
        constructor = _app_archive_validator_map[self.application_archive["archive_type"]]
        return constructor(self.application_archive["resource"],
                           self.application_archive["name"],
                           self.application_archive["description"],
                           app_archive_path)

    def is_password_required(self, install_spec_choice_number):
        """Returns True, False or None. None means that password_required was not set in the config file.
        This should be interpreted as True, but allow for overriding at the command line.
        """
        return (self.install_spec_options[install_spec_choice_number])[u"password_required"]
        
    def to_json(self):
        return {
            u"config_dir": self.config_dir,
            u"resource_def_file_name": self.resource_def_file_name,
            u"install_spec_options": self.install_spec_options,
            u"software_library_file_name": self.software_library_file_name,
            u"log_level": self.log_level,
            u"application_name": self.application_name,
            u"application_archive": self.application_archive
        }
    
    def __str__(self):
        return self.to_json().__str__()

    def __repr__(self):
        return self.to_json().__repr__()

def _validate_config_properties(config_props, filename):
    for config_prop in config_props:
        for key in [u"resource", u"name", u"type", u"description"]:
            if not config_prop.has_key(key):
                raise GenformaConfigError("genforma configuration file %s has invalid install config property definition: missing %s" %
                                          (filename, key))
        if not (config_prop[u"type"] in CONFIG_PROPERTY_TYPES):
            raise GenformaConfigError("genforma configuration file %s has invalid install config property definition: unkown property type %s" %
                                                  (filename, config_prop[u"type"]))


def _parse_install_spec_options(data, filename):
    if data.has_key(u"install_spec_options"):
        assert not data.has_key(u"install_spec_file_name")
        assert type(data[u"install_spec_options"])==list
        for option in data[u"install_spec_options"]:
            for key in [u"choice_name", u"file_name"]:
                if not option.has_key(key):
                    raise GenformaConfigError("genforma configuration file %s has invalid install spec option: missing %s" %
                                              (filename, key))
            if option.has_key(u"config_properties"):
                _validate_config_properties(option[u"config_properties"], filename)
            if not option.has_key(u"password_required"):
                option[u"password_required"] = None
        return data[u"install_spec_options"]
    else:
        raise GenformaConfigError("Need to specify install_spec_options in %s" %
                                  filename)
    
def parse_genforma_config(filename):
    if not os.path.exists(filename):
        raise GenformaConfigError("genForma configuration file %s does not exist" % filename)
    try:
        with open(filename, "rb") as f:
            data = json.load(f)
    except:
        logger.exception("Error in parsing genforma config file %s" % filename)
        raise
    if type(data) != dict:
        raise GenformaConfigError("genForma configuration file %s data is not a dictionary" % filename)
    required_properties = [(u"resource_def_file_name", unicode),
                           (u"software_library_file_name", unicode), (u"log_level", unicode),
                           (u"application_name", unicode)]
    for (name, proptype) in required_properties:
        if not data.has_key(name):
            raise GenformaConfigError("genForma configuration file %s missing required property %s" %
                                      (filename, name))
        if type(data[name]) != proptype:
            raise GenformaConfigError("genForma configuration file %s property %s has wrong type: type was %s, expecting %s" %
                                      (filename, name, type(data[name]), proptype))
    # validate all the install spec options
    install_spec_options = _parse_install_spec_options(data, filename)

    # parse the app archive info
    if data.has_key(u"application_archive") and data[u"application_archive"]!=None:
        application_archive = data[u"application_archive"]
        app_archive_props = [u"resource", u"name", u"description", u"archive_type"]
        for prop in app_archive_props:
            if not application_archive.has_key(prop):
                raise GenformaConfigError("Error in genForma configuration file %s: application_archive missing required subproperty %s" %
                                          (filename, prop))
        if application_archive[u"archive_type"] not in _app_archive_validator_map.keys():
            raise GenformaConfigError("Error in genForma configuration file %s: Unknown application achive type '%s'" %
                                      (filename, application_archive[u"archive_type"]))
    else:
        application_archive = None
                    
    return GenformaConfig(os.path.abspath(os.path.dirname(filename)), data[u"resource_def_file_name"],
                          install_spec_options,
                          data[u"software_library_file_name"],
                          data[u"log_level"], data[u"application_name"], application_archive)

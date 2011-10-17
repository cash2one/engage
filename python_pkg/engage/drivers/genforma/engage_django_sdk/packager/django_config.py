import json
import os.path

from errors import FileFormatError, VersionError
import utils
from json_utils import JsonObject

json_properties = [
    "product", "product_version", "django_settings_module",
    # python_path_subdirectory is the directory which should be set as the PYTHONPATH,
    # relative from the top level directory of the application archive.
    # If the PYTHONPATH should point to the parent directory of the application
    # archive, then python_path_subdirectory will be the empty string.
    "python_path_subdirectory",
    # version of the SDK
    "version",
    "installed_apps",
    "fixtures", "migration_apps", "components",
    "post_install_commands",
    "media_root_subdir", "media_url_path",
    "static_root_subdir", "static_url_path"
]

required_json_properties = [
    "product", "product_version", "django_settings_module",
    "python_path_subdirectory",
    "version"
]

class DjangoConfig(JsonObject):
    def __init__(self, properties):
        JsonObject.__init__(self, json_properties,
                            required_properties=required_json_properties,
                            prop_val_dict=properties)
        # setup defaults for list properties
        if not self.installed_apps: self.installed_apps = []
        if not self.fixtures: self.fixtures = []
        if not self.migration_apps: self.migration_apps = []
        if not self.components: self.components = []
        if not self.post_install_commands: self.post_install_commands = []


    def get_settings_module_file(self):
        """Return the path to the settings file. This is a relative path,
        from the start of the application directory. Thus, the first component
        of this path will always be the common directory of the application archive.
        """
        if self.python_path_subdirectory != "":
            return os.path.join(self.python_path_subdirectory,
                                '/'.join(self.django_settings_module.split('.'))) + ".py"
        else:
            return '/'.join(self.django_settings_module.split('.')) + ".py"

    def get_settings_file_directory(self, app_parent_dir):
        """Given the directory above the one where we are extracting the app,
        return the directory containing the settings file.
        """
        return os.path.dirname(os.path.join(app_parent_dir, self.get_settings_module_file()))

    def get_deployed_settings_module(self):
        # deployed settings module is the one we generate and use as the actual django settings module
        return utils.get_deployed_settings_module(self.django_settings_module)

    def get_python_path_directory(self, app_parent_dir):
        """This is the directory we need to add to PYTHONPATH
        """
        if self.python_path_subdirectory == "":
            return app_parent_dir
        else:
            return os.path.join(app_parent_dir, self.python_path_subdirectory)


def compatible_versions(current_version, compatible_version):
    """We check the first two components of the version. The current version
    must be equal to or greater than the compatible version in both components.
    Ill-formed version numbers result in a False return value.

    >>> compatible_versions("1.0.0", "1.0.0")
    True
    >>> compatible_versions("1.0.0", "1.0.1")
    True
    >>> compatible_versions("1.0.1", "1.0.0")
    True
    >>> compatible_versions("1.1.0", "1.0.0")
    True
    >>> compatible_versions("1.0.0", "1.1.0")
    False
    >>> compatible_versions("2.0.0", "1.0.0")
    True
    >>> compatible_versions("2.0.0", "2.1.0")
    False
    >>> compatible_versions("2.0.0", "2.0.5")
    True
    >>> compatible_versions("2.0.0", "1.9")
    True
    """
    version_list = current_version.split(".")
    compat_list = compatible_version.split(".")
    assert len(compat_list) >= 2, "Compabile version number should have at least two components"
    if len(version_list)<2 or (version_list[0]< compat_list[0]) or \
        (version_list[0]==compat_list[0] and version_list[1]<compat_list[1]):
        return False
    else:
        return True


def django_config_from_json_obj(json_obj, compatible_version):
    # First, we get the version property, which must always be there. We
    # check that first, as the presence of the other properties may depend
    # on the version, and we don't want to give a confusing error message
    # (see ticket #163).
    if not json_obj.has_key("version"):
        raise FileFormatError("django engage configuration file missing required key 'version'")
    version = json_obj["version"]
    if not compatible_versions(version, compatible_version):
        raise VersionError("Application package was built using an obsolete version of the SDK (%s). Please download the latest version and repackage your application." %
                           version)
    return DjangoConfig(json_obj)


def django_config_from_json(json_string, compatible_version):
    try:
        json_obj = json.loads(json_string)
    except ValueError, m:
        raise FileFormatError("Unable to parse django engage configuration file: %s" % m)
    return django_config_from_json_obj(json_obj, compatible_version)

def django_config_from_validation_results(django_settings_module, version, results):
    results_json = results.to_json()
    results_json["django_settings_module"] = django_settings_module
    results_json["version"] = version
    if not results_json["product"]:
        results_json["product"] = "Custom Django Application"
    if not results_json["product_version"]:
        results_json["product_version"] = ""
    return DjangoConfig(results_json)
    

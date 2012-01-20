"""
 library.py

 Copyright 2009, 2010 by genForma Corporation

 
API for parsing library metadata and accessing files. The key goal of this module
is to locate the resource manager class for a given software component and the
bits that contain the actual software for the component to be installed.

Currently, the only library type we support is a json file. In theory, we could
also store this data in a real database if it gets too big.

Entries
-------
The library contains a set of entries. Each entry is indexed by its resource key as well as a set of "match properties" (just a map of arbitrary properties). In
practice, these match properties would come from the resource instance and be used
to distinguish platform-specific versions of a
resource (e.g. binaries for a particular os and architecture).

Packages
--------
Each library entry contains a list of packages. When a library entry is matched,
the packages are probed via the is_available() in the order specified. The first
available package is then returned. There are three types of packages:
  Reference:  just a link (a name or a URL) used by another program to obtain the
              actual package.
  File:       A physical file of some type. If the file is not local, it should
              be downloaded to a directory in the local filesystem called the
              "cache". A separate downloader class is provided to do the actual
              downloads. This allows the code to download a remote file to be
              reused across multiple file formats.
  Archive:    A subclass of File for packages that are archives that need to be
              extracted during the install process. Archive packages provide an
              extract() method to do this.


Each package entry has the following properties:
 type:          one of Reference, File, or Archive
 package_class: name of the class implementing this package
 location:      used by the package to identify where the package may be found
 platforms:     if present, a list of platforms for which this is available
 
If the type is File or Archive, then the following additional properties are
present:
 filename:   name of the file when downloaded to the filesystem (not including a
             directory path). This is automatically set to the same value as
             location if no downloader is specified.
 downloader: Name of downloader class to obtain the package from the location.
             If downloader is not present, defaults to one which always requires
             the package to be in the local cache


In some cases, packages may need some extra configuration data (e.g. API keys).
To accomodate this, the resource library file may contain a top level property
called "package_properties". If present, this property's value should be a
map. The map is passed to the constructor of each package object and downloader.

Supported package classes:
GzippedTarArchive (Archive)
ZipArchive (Archive)
EasyInstallLink (Reference)
PipLink (Reference)
DummyPackage (Reference)
MacPorts (Reference)
AptGet (Reference)
"""

import sys
import json
import os
import os.path
import tarfile
import zipfile
import shutil
import urllib
import re
import copy

from engage.engine.json_metadata_utils import MetadataContainer, get_json_property, \
                                              get_opt_json_property
import engage.utils.file as fileutils
import engage.utils.path
import engage.utils.system_info as system_info
from engage.extensions import installed_extensions
from engage.utils.log_setup import setup_engine_logger
from engage.utils.user_error import UserError, InstErrInf, convert_exc_to_user_error

import gettext
_ = gettext.gettext

errors = { }

def define_error(error_code, msg):
    global errors
    error_info = InstErrInf("Library", error_code, msg)
    errors[error_info.error_code] = error_info

# error codes
LIBRARY_PARSE_ERROR = 1
DRIVER_IMPORT_ERROR = 2
ERR_MISSING_PKG_JSON_FILE = 3

define_error(LIBRARY_PARSE_ERROR,
             _("Error in parsing software library file '%(filename)s'"))
define_error(DRIVER_IMPORT_ERROR,
             _("Error in importing driver module '%(mod)s': '%(msg)s'"))
define_error(ERR_MISSING_PKG_JSON_FILE,
             _("Package listing file %(file)s for driver %(key)s is missing"))

logger = None
def get_logger():
    global logger
    if logger == None:
        logger = setup_engine_logger("Library")
    return logger


class LibraryParseError(Exception):
    pass

class PackageUnavailable(Exception):
    """Thrown by the get_package_contents() method of packages when the
    package cannot be read (e.g. due to it not being in the proper place
    in the filesystem or a network request failing."""
    pass


class PackageReadError(Exception):
    """Returned if an error occurs when attempting to read/extract a package"""
    pass


_my_platform = system_info.get_platform()

class Package(object):
    """Base class for managing the package for a software resource.
    """
    # values for type type property
    REFERENCE_TYPE = "Reference"
    FILE_TYPE = "File"
    ARCHIVE_TYPE = "Archive"
    
    def __init__(self, type, location, platforms, package_properties):
        """Subclasses are responsible for obtaining reference to package_properties"""
        assert (type == Package.REFERENCE_TYPE) or (type == Package.FILE_TYPE) or \
               (type == Package.ARCHIVE_TYPE)
        self.type = type
        self.location = location
        self.platforms = platforms

    def _is_available_on_this_platform(self):
        """Returns true if the value of the platforms property
        permits this package, false otherwise. Used by subclasses
        in implementing is_available().
        """
        if self.platforms!=None:
            if _my_platform in self.platforms:
                return True
            else: return False
        else:
            return True # if not specified, must work for all
        
    def is_available(self):
        """Returns True if the package is currently available, False
        otherwise. Subclasses must handle the platforms property if they
        intend to honor it.
        """
        raise Exception("is_available not implemented for %s" %
                        self.__class__.__name__)

    def to_json(self):
        return {u"type":self.type, u"location":self.location,
                u"package_class":self.__class__.__name__}

    def __repr__(self):
        return self.to_json().__repr__()


class Downloader(object):
    def __init__(self, location, target_filepath, package_properties):
        """Subclasses are responsible for obtaining reference to package_properties"""
        self.location = location
        self.target_filepath = target_filepath

    def is_available(self):
        return False

    def download_to_cache(self):
        """Download to the cache"""
        pass

_downloader_classes = {}

def register_downloader_class(classname, constructor):
    """Register a Downloader class. The constructor
    should take three arguments: location, target_filepath, and package_properties
    """
    _downloader_classes[classname] = constructor


import engage.utils.socktime as socktime

class HTTPDownloader(Downloader):
    def __init__(self, location, target_filepath, package_properties=None):
        if not isinstance(location, basestring):
            elapsed, url = socktime.fastest(location)
            get_logger().debug('Using fastest (%s) mirror: %s' % (elapsed, url))
            location = url
        Downloader.__init__(self, location, target_filepath, package_properties)

    def is_available(self):
        try:
            get_logger().debug("Trying to get %s" % self.location)
            f = urllib.urlopen(self.location)
            return int(f.info().getheader('content-length')) > 0
        except:
            get_logger().exception('%s is unavailable' % self.location)
            return False

    def download_to_cache(self):
        get_logger().info('downloading %s via HTTP' % self.location)
        urllib.urlretrieve(self.location, self.target_filepath)

register_downloader_class("HTTPDownloader", HTTPDownloader)

class CloudfilesDownloader(Downloader):
    def __init__(self, location, target_filepath, package_properties):
        Downloader.__init__(self, location, target_filepath, package_properties)
        self.package_properties = package_properties
        try:
            self.container_name, self.location = self.location.split('/')
        except:
            self.container_name = package_properties['default_package_container']

    def get_container(self, container_name):
        key = self.package_properties['rackspace_api_key']
        secret = self.package_properties['rackspace_secret']
        get_logger().debug('get_connection %s@rackspace' % key)
        connection = self.cloudfiles.get_connection(key, secret, servicenet=False)
        return connection[container_name]

    def is_available(self):
        try:
            self.cloudfiles = __import__('cloudfiles')
            objects = self.get_container(self.container_name).list_objects()
            return self.location in objects
        except:
            get_logger().exception('%s/%s is unavailable' % (self.container_name, self.location))
            return False

    def download_to_cache(self):
        container = self.get_container(self.container_name)
        obj = container.get_object(self.location)
        get_logger().info('downloading %s/%s from cloudfiles' % (
                self.container_name, self.location))
        with open(self.target_filepath, 'w') as f:
            for chunk in obj.stream():
                f.write(chunk)

register_downloader_class('CloudfilesDownloader', CloudfilesDownloader)

_package_classes = {}

def register_package_class(type, classname, constructor):
    """Register a package class to be instantiated for handling the specified
    type and format. Reference package constructors should take three parameters:
    type, location, and package_properties. File and archive package constructors
    should take five parameters: type, location, filepath, downloader_class,
    and package_properties."""
    _package_classes[classname] = (type, constructor)


class FilePackage(Package):
    def __init__(self, type, location, filepath, downloader_class,
                 platforms, package_properties):
        assert (type == Package.FILE_TYPE) or (type == Package.ARCHIVE_TYPE)
        Package.__init__(self, type, location, platforms, package_properties)
        self.filepath = filepath
        self.downloader = downloader_class(location, filepath, package_properties)

    def is_available(self):
        if not self._is_available_on_this_platform():
            get_logger().debug("%s not available on platform" % self.location)
            return False
        if os.path.exists(self.filepath):
            get_logger().debug("%s is available" % self.location)
            return True
        else:
            available = self.downloader.is_available()
            if available:
                get_logger().debug("%s is available" % self.location)
            else:
                if self.downloader.__class__ == Downloader:
                    get_logger().debug("%s is not available locally and no downloader was defined for it" % self.location)
                else:
                    get_logger().debug("%s not downloadable (downloader was %s)" %
                                      (self.location, self.downloader.__class__.__name__))
            return available
            
    def get_file(self):
        """Download the file if necessary and return its full path on the local filesystem."""
        if os.path.exists(self.filepath):
            return self.filepath
        else:
            self.downloader.download_to_cache()
            return self.filepath
        
    def to_json(self):
        json = Package.to_json(self)
        json[u"filename"] = os.path.basename(self.filepath)
        json[u"downloader"] = self.downloader.__class__.__name__
        return json

register_package_class(Package.FILE_TYPE, "FilePackage", FilePackage)


class ArchivePackage(FilePackage):
    """Archive packages just need to be extracted.
       Subclasses need to implement:
         self.extract(parent_dir, desired_common_dirname=None) - extract the archive to the parent directory.
           Everything should be under a common subdirectory, whose name can be optionally sepecified via
           desired_common_dirname. Always returns the name of the common subdirectory.
    """
    def __init__(self, type, location, filepath, downloader_class,
                 platforms, package_properties):
        assert type == Package.ARCHIVE_TYPE
        FilePackage.__init__(self, type, location, filepath, downloader_class,
                             platforms, package_properties)



class GenericExtractor(object):
    """This is a base class for packages which extract themselves using the extract() method. We
    provide a common implementation of extract() that deals with validation, directory renaming,
    etc.

    Subclasses must provide the following:
        self.filepath - full path to the archive file
        self.format - user-readable name of the archive format (e.g. Zip, gzipped-tar)
        self.get_file() - download the file if necessary. returns the path, which should be the same as self.filepath
        self._create_archive_object() - Return an archive object for the associated archive file
        self._get_extract_action_logmsg(extract_dir, archive_file) - return a log message string for extracting the archive

    The archive object should provide the following methods:
        archive_obj.namelist() - return a list of files in the archive
        archive_obj.extractall(path) - extract all the files in the archive to the specified location
        archive_obj.close() - close the archive object
    """
    def _validate_archive_files(self, namelist, expecting_common_subdir=False):
        """Given a list of files in an archive, validate that they are relative paths, not absolute. Also,
        determine whether this is a common directory under which all files appear. If so, this directory is
        returned. If not, None is returned. If expecting_common_subdir is True, then we raise an exception
        if the files aren't all under a common directory.
        >>> class TestExtractor(GenericExtractor):
        ...     def __init__(self):
        ...         self.filepath = 'foo.zip'
        ...         self.format = 'Zip'
        >>> def testfn(namelist, expecting_common_subdir):
        ...      try:
        ...          extractor = TestExtractor()
        ...          print extractor._validate_archive_files(namelist, expecting_common_subdir)
        ...      except PackageReadError, e:
        ...          print 'Got error: %s' % e
        >>>
        >>> list1 = ['foo', 'bar', 'baz']
        >>> testfn(list1, False)
        None
        >>> testfn(list1, True)
        Got error: Zip archive foo.zip not valid for install: contains invalid file path bar
        >>> list2 = ['dir/foo', 'dir/bar/baz', 'dir/bye', 'dir/']
        >>> testfn(list2, True)
        dir
        >>> list3 = ['dir/foo', 'dir2/bar', 'dir/bye']
        >>> testfn(list3, True)
        Got error: Zip archive foo.zip not valid for install: contains invalid file path dir2/bar
        >>> testfn(list3, False)
        None
        """
        common_dirname = None
        has_common_dir = True
        for name in namelist:
            if os.path.isabs(name):
                raise PackageReadError, \
                      "%s archive %s not valid for install: contains absolute file path %s" % (self.format, self.filepath, name)
            if has_common_dir:
                if name.find(os.sep): # contains a directory component
                    subdir = engage.utils.path.get_first_subdir_component(name)
                    if common_dirname == None:
                        common_dirname = subdir
                    elif common_dirname != subdir:
                        if expecting_common_subdir:
                            raise PackageReadError, \
                                "%s archive %s not valid for install: contains invalid file path %s" % (self.format, self.filepath, name)
                        else:
                            has_common_dir = False
                            common_dirname = None
                else:
                    has_common_dir = False
                    common_dirname = None
        return common_dirname

    def extract(self, parent_dir, desired_common_dirname=None):
        """Extract the archive into the specified parent directory. All files should go into a single subdirectory.
        This common subdirectory may optionally be specified using desired_common_dirname.

        >>> class TestArchiveObject(object):
        ...     def __init__(self, filename, namelist_val):
        ...         self.filepath = filename
        ...         self.namelist_val = namelist_val
        ...     def namelist(self):
        ...         return self.namelist_val
        ...     def extractall(self, parent_dir):
        ...         print 'Extracting to %s: %s' % (self.filepath, self.namelist_val)
        ...     def close(self):
        ...         pass
        >>> class TestExtractor(GenericExtractor):
        ...     def __init__(self, namelist):
        ...         self.filepath = "foo.zip"
        ...         self.format = "Zip"
        ...         self.namelist = namelist
        ...     def get_file(self):
        ...         return self.filepath
        ...     def _create_archive_object(self):
        ...         return TestArchiveObject(self.filepath, self.namelist)
        ...     def _get_extract_action_logmsg(self, extract_dir, archive_file):
        ...         return "zip -d %s %s" % (extract_dir, archive_file)
        >>> extractor = TestExtractor(['test/', 'test/foo.txt', 'test/bar.txt'])
        >>> extractor.extract("/Users/test_parent")
        Extracting to foo.zip: ['test/', 'test/foo.txt', 'test/bar.txt']
        'test'
        """
        # first download the file
        actual_path = self.get_file()
        assert actual_path == self.filepath

        # now, do the actual extract
        get_logger().info("Expanding archive '%s'" % os.path.basename(self.filepath))
        if desired_common_dirname == None: expecting_common_subdir = True
        else: expecting_common_subdir = False

        z = self._create_archive_object()
        common_dirname = self._validate_archive_files(z.namelist(), expecting_common_subdir)

        if common_dirname != None:
            get_logger().action(self._get_extract_action_logmsg(parent_dir, self.filepath))
            z.extractall(parent_dir)
            z.close()
            if (desired_common_dirname != None) and (common_dirname != desired_common_dirname):
                # if the actual common directory name is different from the desired one, rename the directory
                from_path = os.path.join(parent_dir, common_dirname)
                to_path = os.path.join(parent_dir, desired_common_dirname)
                get_logger().action("mv %s %s" % (from_path, to_path))
                shutil.move(from_path, to_path)
                return desired_common_dirname
            else:
                return common_dirname
        else:
            assert desired_common_dirname != None # if no common dir and one not specified, validation should have raised an error
            full_child_path = os.path.join(parent_dir, desired_common_dirname)
            if not os.path.exists(full_child_path):
                get_logger().action("mkdir %s" % full_child_path)
                os.makedirs(full_child_path)
            get_logger().action(self._get_extract_action_logmsg(full_child_path, self.filepath))
            z.extractall(full_child_path)
            z.close()
            return desired_common_dirname
        
class TarFile(object):
    def __init__(self, filename):
        self.tarobj = tarfile.open(filename)

    def namelist(self):
        return self.tarobj.getnames()

    def extractall(self, dir):
        self.tarobj.extractall(dir)

    def close(self):
        self.tarobj.close()

    
class GzippedTarFilePackage(ArchivePackage, GenericExtractor):
    """Package class where the package is stored in the local filesystem.
    """
    def __init__(self, type, location, filepath, downloader_class,
                 platforms, package_properties):
        ArchivePackage.__init__(self, type, location, filepath, downloader_class,
                                platforms, package_properties)
        self.format = "GzippedTarArchive"

    def _create_archive_object(self):
        return TarFile(self.filepath)

    def _get_extract_action_logmsg(self, extract_dir, archive_file):
        return "tar --directory %s -xvf %s" % (extract_dir, archive_file)
    

register_package_class(Package.ARCHIVE_TYPE, "GzippedTarArchive", GzippedTarFilePackage)

def _is_zip_direntry(name):
    l = len(name)
    if (l > 0) and (name[l-1] == '/'): return True
    else: return False

class ZipFile(zipfile.ZipFile):
    def __init__(self, filename):
        zipfile.ZipFile.__init__(self, filename)

    def extractall(self, parent_dir):
        """This is a workaround for a bug in Python's ZipFile.extractall() method implementation.
        It does not handle extracting subdirectories correctly, so we extract the files individually,
        creating subdirectories by hand.
        """
        for name in self.namelist():
            if _is_zip_direntry(name):
                subdir = os.path.join(parent_dir, name)
                if not os.path.exists(subdir):
                    os.makedirs(subdir)
            else:
                self.extract(name, parent_dir)


class ZipPackage(ArchivePackage, GenericExtractor):
    """Package class where the package is stored in the local filesystem.
    """
    def __init__(self, type, location, filepath, downloader_class,
                 platforms, package_properties):
        ArchivePackage.__init__(self, type, location, filepath, downloader_class,
                                platforms, package_properties)
        self.format = "ZipArchive"

    def _create_archive_object(self):
        return ZipFile(self.filepath)

    def _get_extract_action_logmsg(self, extract_dir, archive_file):
        return "zip -d %s %s" % (extract_dir, archive_file)
    

register_package_class(Package.ARCHIVE_TYPE, "ZipArchive", ZipPackage)


class PythonInstallerPackage(Package):
    """Package class for library which can be downloaded from URL"""

    def __init__(self, type, location, platforms, package_properties):
        Package.__init__(self, type, location, platforms, package_properties)

    def is_available(self):
        return self._is_available_on_this_platform()

class EasyInstallPythonPackage(PythonInstallerPackage):
    def __init__(self, type, location, platforms, package_properties):
        PythonInstallerPackage.__init__(self, type, location,
                                        platforms, package_properties)

register_package_class(Package.REFERENCE_TYPE, "EasyInstallLink", EasyInstallPythonPackage)

class PipPythonPackage(PythonInstallerPackage):
    def __init__(self, type, location, platforms, package_properties):
        PythonInstallerPackage.__init__(self, type, location,
                                        platforms, package_properties)
    def __repr__(self):
        return ('Pip package %s' % self.location)

register_package_class(Package.REFERENCE_TYPE, "PipLink", PipPythonPackage)

                     
class MacPortsPackage(Package):
    def __init__(self, type, location, platforms, package_properties):
        if platforms==None:
            platforms = ["macosx", "macosx64"]
        Package.__init__(self, type, location,
                         platforms, package_properties)

    def is_available(self):
        return self._is_available_on_this_platform()

    def __repr__(self):
        return ('MacPorts package %s' % self.location)

register_package_class(Package.REFERENCE_TYPE, "MacPorts", MacPortsPackage)

class AptGetPackage(Package):
    def __init__(self, type, location, platforms, package_properties):
        if platforms==None:
            platforms = ["linux", "linux64"]
        Package.__init__(self, type, location, platforms, package_properties)
    def is_available(self):
        return self._is_available_on_this_platform()
    def __repr__(self):
        return ('AptGet package %s' % self.location)

register_package_class(Package.REFERENCE_TYPE, "AptGet", AptGetPackage)


class DummyPackage(Package):
    """Library package for installable components which don't have any software packages.
    """
    def __init__(self, type, location, platforms, package_properties):
        Package.__init__(self, type, location, platforms, package_properties)

    def is_available(self):
        return self._is_available_on_this_platform()

register_package_class(Package.REFERENCE_TYPE, "DummyPackage", DummyPackage)


class LibraryEntry(object):
    """Entry in our resource library. Each entry can be matched to resource
    instances by its resource key and match properties. The module name is
    used to instantiate the resource manage module for this entry.
    If specified, package_list contains a list of Package instances
    for the resource. If it is not specified, then it is set to the empty
    list and has_package() returns False.
    """
    def __init__(self, key, match_properties, mgr_module_name,
                 package_list=None):
        self.key = key
        self.match_properties = match_properties
        self.mgr_module_name = mgr_module_name
        if package_list != None:
            self.package_list = package_list
        else:
            self.package_list = []


    def has_package(self):
        if self.package_list != []: return True
        else: return False

    def get_package(self):
        """Return the first available package or None if no packages in
        the list were available"""
        if len(self.package_list)==0:
            get_logger().debug("No packages found for resource %s" % self.key)
        for package in self.package_list:
            if package.is_available():
                return package
        return None

    def get_manager_class(self):
        """Return the class (constructor function) for the manager class
        associated with this resource"""
        get_logger().debug('Module name is %s' % self.mgr_module_name)
        mod = __import__(self.mgr_module_name)
        components = self.mgr_module_name.split('.')
        for comp in components[1:]:
            mod = getattr(mod, comp)
        return getattr(mod, 'Manager')

    def requires_root_access(self):
        """Returns true if the resource manager will require root access.
        """
        mgr_class = self.get_manager_class()
        if hasattr(mgr_class, "REQUIRES_ROOT_ACCESS") and \
           getattr(mgr_class, "REQUIRES_ROOT_ACCESS")==True:
            return True
        else:
            return False
        
    def to_json(self):
        """Return an in-memory json representation of this entry"""
        return {u"key":self.key, 
                u"match_properties":self.match_properties,
                u"mgr_module_name":self.mgr_module_name,
                u"packages":[pkg.to_json() for pkg in self.package_list]}

    def __str__(self):
        """Returns a string-json representation"""
        return json.dumps(self.to_json(), sort_keys=True, indent=1)


def convert_resource_key_to_driver_module_names(key, prefix="engage.drivers."):
    candidates = []
    for submodule in (["standard",] + installed_extensions):
        candidates.append(prefix + submodule + "." + fileutils.mangle_resource_key(key) + ".driver")
        ## # also convert the resource name to all lowercase
        ## candidates.append(prefix + submodule + "." + (fileutils.mangle_resource_key(key)).lower() + ".driver")
    return candidates


class Library(object):
    """The interface for a library. The storage mechanism for
    the library's metadata and content is hidden behind this interface.
    This allows us to use the filesystem, databases, and the internet in
    potential implementations.

    To retrieve an entry, the client provides the resource metadata for
    the desired entry. This is then matched to entries in the library,
    first by the key and then by a set of "match properties". These are
    properties whose values must match associated properties in the resource
    metadata's config, input or output ports. Since these ports may have
    a nested structure, match properties are respresented as strings using
    a "."-separated format. For example, "config_port.foo" references the
    "foo" property of the resources config port.
    """

    def get_entry(self, resource_md):
        """Retrieve a matching entry. If no such entry exists
        in the library, return None."""
        pass



class InMemoryLibrary(Library):
    """This is a base class for libraries which store their metadata in
    memory at runtime.
    """
    def __init__(self):
        """We instantiate the library without any entries. The add_entry
        method is used to add an entry. package_properties contains any
        additional information needed for the library or individual packages.

        We store the library in both a linked list and in a map by resource
        key. The linked list is for consistent mapping back to JSON.
        """
        self.entry_list = []
        self.entries = MetadataContainer()

    def add_entry(self, entry):
        """Add an entry (subclass of MetadataFileEntry) to the library.
        We store the entries as a list and also in a MetadataContainer.
        """
        self.entry_list.append(entry)
        self.entries.add_entry(entry)

    def get_entry(self, resource_md):
        """Return the entry with the same resource key and whose match
        properties are satisfied by this resource. If no such entry exists,
        return None."""
        entry = self.entries.get_entry(resource_md)
        if entry:
            return entry
        else:
            entry = _load_newstyle_entry(resource_md.key, "", self.cache_directory, self.package_properties)
            if entry!=None:
                self.add_entry(entry)
            return entry

    def to_json(self):
        """Convert the library metadata to an in-memory json representation"""
        return {u"entries": [entry.to_json() for entry in
                              self.entry_list]}

    def __str__(self):
        """Returns a string-json representation"""
        return json.dumps(self.to_json(), sort_keys=True, indent=1)


class FileLibrary(InMemoryLibrary):
    def __init__(self, module_search_path, library_directory, cache_directory,
                 package_properties):
        InMemoryLibrary.__init__(self)
        self._setup_module_path(module_search_path,
                                library_directory)
        self.module_search_path = module_search_path
        self.package_properties = package_properties
        self.cache_directory = cache_directory

    def _setup_module_path(self, module_search_path, library_directory):
        # build a copy of the existing path using all absolute path components
        abs_sys_path = [os.path.abspath(path) for path in sys.path]
        # now go through each directory and see if it is in search path.
        # If not, add it.
        for dir in module_search_path:
            if os.path.isabs(dir):
                abs_dirname = dir
            elif library_directory!=None:
                abs_dirname = os.path.join(library_directory, dir)
            else:
                abs_dirname = os.path.abspath(dir)
            if not os.path.isdir(abs_dirname):
                raise LibraryParseError, \
                    "Resource manager directory %s not valid" % dir
            if not (abs_dirname in abs_sys_path):
                sys.path.append(abs_dirname)
                get_logger().debug("Appended resource manager %s to module path" %
                             abs_dirname)
        # we also add ../content, relative to the directory containing the
        # the install engine code to the path, as this is where shipped
        # content goes.
        standard_content_dir = \
            os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]),
                                         "../content"))
        if not (standard_content_dir in abs_sys_path):
            sys.path.append(standard_content_dir)

    def to_json(self):
        json = InMemoryLibrary.to_json(self)
        json[u"module_search_path"] = self.module_search_path
        json[u"package_properties"] = self.package_properties
        return json

# List of the package properties that are passed directly to the package
# constructor. Anything else will be added to package_properties.
standard_package_fields = [u"type", u"location", u"package_class",
                           u"downloader", u"filename", u"platforms"]

def _merge_package_properties(package_entry_json, global_package_properties):
    """Combine the package-specific properties with package global properties.
    """
    props = copy.copy(global_package_properties)
    for key in package_entry_json:
        if key not in standard_package_fields:
            props[key] = package_entry_json[key]
    return props


def _parse_package(json_repr, err_msg, cache_directory, package_properties):
    local_package_properties = _merge_package_properties(json_repr,
                                                         package_properties)
    platforms = get_opt_json_property(u"platforms", json_repr, list,
                                      err_msg, None)
    type = get_json_property(u"type", json_repr, unicode,
                             "%s package" % err_msg)
    location = get_json_property(u"location", json_repr, unicode, err_msg)
    package_class = get_json_property(u"package_class", json_repr, unicode, err_msg)
    if not _package_classes.has_key(package_class):
        raise LibraryParseError, "%s unknown package class %s" % \
            (err_msg, package_class)
    (exp_pkg_type, constructor) = _package_classes[(package_class)]
    if type != exp_pkg_type:
        raise LibraryParseError, "%s wrong package type '%s', expecting '%s'" % \
              (err_msg, type, exp_pkg_type)
    if type == Package.REFERENCE_TYPE:
        return constructor(type, location, platforms,
                           local_package_properties)
    else:
        if not json_repr.has_key(u"downloader") or json_repr[u"downloader"] == None:
            filename = location
            downloader_class = Downloader
        else:
            downloader_name = json_repr[u"downloader"]
            if not _downloader_classes.has_key(downloader_name):
                raise LibraryParseError, "%s, invalid downloader type %s" % \
                      (err_msg, downloader_name)
            downloader_class = _downloader_classes[downloader_name]
            filename = get_json_property(u"filename", json_repr, unicode,
                                         "%s package" % err_msg)
        filepath = os.path.join(cache_directory, filename)
        return constructor(type, location, filepath, downloader_class,
                           platforms, local_package_properties)


def _parse_entry(json_repr, err_msg, cache_directory, package_properties):
    key = get_json_property(u"key", json_repr, dict, "%s entry" % err_msg)
    err_msg = "%s resource %s" % (err_msg, key)
    match_properties = get_opt_json_property(u"match_properties", json_repr,
                                              dict, err_msg, {})
    mgr_module_name = get_json_property(u"mgr_module_name", json_repr,
                                        unicode, err_msg)
    package_list_json = get_opt_json_property(u"packages", json_repr, list,
                                              err_msg, [])
    package_list = [_parse_package(package_json, err_msg,
                                   cache_directory, package_properties)
                    for package_json in package_list_json]
    return LibraryEntry(key, match_properties, mgr_module_name,
                        package_list)

def _load_newstyle_entry(key, err_msg, cache_directory, package_properties):
    """This is for library entries that are stored along with the drivers.
    """
    _mod = None
    driver_module_names = convert_resource_key_to_driver_module_names(key)
    for driver_module_name in driver_module_names:
        try:
            get_logger().debug("Attempting to import %s" % driver_module_name)
            _mod = __import__(driver_module_name, globals(), locals(), ['get_packages_filename'], -1)
            break
        except ImportError, e:
            get_logger().debug("Could not import %s: %s" % (driver_module_name, str(e)))
            #msg = "No module named %s" % driver_module_name
            #if e.__str__() == msg:
            #    continue # driver module does not exist
            #else:
            #    # driver module does exist, but there was a problem importing it
            #    get_logger().exception("Error importing %s" % driver_module_name)
            #    raise UserError(errors[DRIVER_IMPORT_ERROR],
            #                    msg_args={"mod":driver_module_name,
            #                              "msg": e.__str__()})
    if _mod == None:
        get_logger().error("Did not find library entry of resource type %s, tried module names %s" %
                           (key, driver_module_names))
        return None
    package_file = _mod.get_packages_filename()
    if not os.path.exists(package_file):
        raise UserError(ERR_MISSING_PKG_JSON_FILE,
                        msg_args={"file":package_file,
                                  "key":key.__repr__()})

    err_msg = "%s resource %s" % (err_msg, key)

    with open(package_file, "rb") as pf:
        package_list_json = json.load(pf)
        
    package_list = [_parse_package(package_json, err_msg,
                                   cache_directory, package_properties)
                    for package_json in package_list_json]
    assert len(package_list)>0
    return LibraryEntry(key, {}, driver_module_name,
                        package_list)


def preprocess_library_file(primary_library_file, extension_library_files,
                            target_library_file):
    """Combine the primary library file with extension library files, generating
    target_library_file. This is done at the json level without doing any kind
    of semantic parsing of the library files. Extension files can either be a
    dict with an "entries" member (like the master file) or just a list of entries.
    """
    with open(primary_library_file, "rb") as plf:
        library_file = json.load(plf)
    entries = library_file['entries']
    # append the entries from each extension file
    for extn_file in extension_library_files:
        if not os.path.exists(extn_file):
            continue
        get_logger().debug("Adding library entries from %s/%s to master library" %
                           (os.path.basename(os.path.dirname(extn_file)),
                            os.path.basename(extn_file)))
        with open(extn_file, "rb") as ef:
            extn_file_json = json.load(ef)
        if isinstance(extn_file_json, list):
            entries.extend(extn_file_json)
        elif isintance(extn_file_json, dict) and extn_file_json.has_key("entries"):
            entries.extend(extn_file_json["entries"])
        else:
            raise Exception("Library file %s not in correct format" % extn_file)
    with open(target_library_file, "wb") as tf:
        json.dump(library_file, tf)

 
_unit_test_library = u"""
{ "module_search_path": [],
  "cache_directory": "../sw_packages",
  "entries":[
    {"key":{"name":"foo"},
     "match_properties":{"config_port.os":"mac-osx"},
     "mgr_module_name":"service_manager",
     "packages": [
       {"type":"Archive",
        "location":"foo_mac.tgz",
        "package_class":"GzippedTarArchive" }
     ]
    },
    {"key":{"name":"foo"},
     "match_properties":{"config_port.os":"windows-xp"},
     "mgr_module_name":"service_manager",
     "packages": [
       {"type":"Archive",
        "location":"foo_windows.tgz",
         "package_class":"GzippedTarArchive" }
     ]
   }
  ]
}
"""


def parse_library(json_repr, filename=None, cache_directory_override=None):
    """Parse the in-memory JSON representation of the library metadata and
    return an instance of FileBasedLibrary. This function expects a map
    containing the following properties:
     module_search_path - path of directories to check for modules.
     package_properties - map of properties for individual package classes
     library_entries - list of entries

    As a unit test, we parse a sample library description, and then
    retrieve a package from it:
    >>> import json
    >>> json_repr = json.loads(_unit_test_library)
    >>> library = parse_library(json_repr)
    >>> print library.__str__()
    {
     "entries": [
      {
       "key": {
        "name": "foo"
       }, 
       "match_properties": {
        "config_port.os": "mac-osx"
       }, 
       "mgr_module_name": "service_manager", 
       "packages": [
        {
         "downloader": "Downloader", 
         "filename": "foo_mac.tgz", 
         "location": "foo_mac.tgz", 
         "package_class": "GzippedTarFilePackage", 
         "type": "Archive"
        }
       ]
      }, 
      {
       "key": {
        "name": "foo"
       }, 
       "match_properties": {
        "config_port.os": "windows-xp"
       }, 
       "mgr_module_name": "service_manager", 
       "packages": [
        {
         "downloader": "Downloader", 
         "filename": "foo_windows.tgz", 
         "location": "foo_windows.tgz", 
         "package_class": "GzippedTarFilePackage", 
         "type": "Archive"
        }
       ]
      }
     ], 
     "module_search_path": [], 
     "package_properties": {}
    }
    >>> from engage.drivers.resource_metadata import ResourceMD
    >>> rmd = ResourceMD(u"r1", {u"name":u"foo"},
    ...                  config_port={u"os":u"mac-osx"})
    >>> print library.get_entry(rmd)
    {
     "key": {
      "name": "foo"
     }, 
     "match_properties": {
      "config_port.os": "mac-osx"
     }, 
     "mgr_module_name": "service_manager", 
     "packages": [
      {
       "downloader": "Downloader", 
       "filename": "foo_mac.tgz", 
       "location": "foo_mac.tgz", 
       "package_class": "GzippedTarFilePackage", 
       "type": "Archive"
      }
     ]
    }
    """
    if filename!=None:
        err_msg = "Library at '%s'" % filename
        default_cache_directory = os.path.dirname(filename)
        library_file_directory = os.path.dirname(filename)
    else:
        err_msg = "Library"
        default_cache_directory = "."
        library_file_directory = "."
        
    if not isinstance(json_repr, dict):
        raise LibraryParseError, "%s not a map" % err_msg

    module_search_path = get_opt_json_property(u"module_search_path",
                                               json_repr, list,
                                               err_msg, [])
    if cache_directory_override:
        cache_directory = cache_directory_override
    else:
        cache_directory = get_opt_json_property(u"cache_directory",
                                                json_repr, unicode,
                                                err_msg, default_cache_directory)
    if not os.path.isabs(cache_directory):
        # if the cache directory is relative, we take it as relative to the
        # library file
        cache_directory = os.path.normpath(os.path.join(library_file_directory,
                                                        cache_directory))

    package_properties = get_opt_json_property(u"package_properties",
                                               json_repr, dict,
                                               err_msg, {})

    library = FileLibrary(module_search_path, library_file_directory,
                          cache_directory, package_properties)

    entries_json = get_json_property(u"entries", json_repr, list,
                                     err_msg)
    for entry_json in entries_json:
        library.add_entry(_parse_entry(entry_json, err_msg,
                                       cache_directory, package_properties))
    return library



def parse_library_files(file_layout, use_temporary_file=False):
    """Preprocess and parse all the library files, returning an instance of
    FileLibrary.
    """
    fl = file_layout
    perm_file_name = fl.get_preprocessed_library_file() \
                     if not use_temporary_file \
                     else None
    with fileutils.OptNamedTempFile(perm_file_name=perm_file_name) as of:
        preprocess_library_file(fl.get_software_library_file(),
                                fl.get_extension_library_files(),
                                of.name)
        try:
            with open(of.name, "rb") as lf:
                json_repr = json.load(lf)
            return parse_library(json_repr, of.name,
                                 cache_directory_override=fl.get_cache_directory())
        except UserError, e:
            raise # just reraise user errors
        except:
            # wrap other exceptions in user errors
            get_logger().exception("Error in parsing library file %s" % of.name)
            user_error = \
              convert_exc_to_user_error(sys.exc_info(),
                                        errors[LIBRARY_PARSE_ERROR],
                                        {"filename":of.name})
            raise user_error


def get_library_path(dirname='metadata', filename='resource_library.json'):
    from engage.engine.test_common import find_dir
    metadata_dir = find_dir(dirname)
    libpath = os.path.join(metadata_dir, filename)
    if os.path.exists(libpath):
        return libpath
    else:
        raise Exception, 'Cannot locate resource libraray in %s' % metadata_dir

def fake_package(path='nose.plugins.skip', classname='SkipTest', baseclass=Exception):
    """ Return a package with final module in path containing a class named classname
    derived from baseclass.

    see http://code.activestate.com/recipes/82234-importing-a-dynamically-generated-module/
    """
    import imp
    result = None
    prev = None
    for name in path.split('.'):
        mod = imp.new_module(name)
        if result is None:
            result = mod
        if prev is not None:
            prev.__dict__[name] = mod
        prev = mod
    prev.__dict__[classname] = type(classname, (baseclass,), {})
    return result

def test_fake_package():
    nose = fake_package('nose.plugins.skip', 'SkipTest', Exception)
    assert issubclass(nose.plugins.skip.SkipTest, Exception)

def test_parser():
    library_file = get_library_path()
    if os.path.exists(library_file):
        print "  Running parse test on real resource library file..."
        try:
            l = parse_library_from_file(library_file)
        except UserError, e:
            print "  Test failed, got parse exception:"
            print "  %s" % e.__str__()
            print "  %s" % e.developer_msg
            for c in e.context:
                print c.__str__()
            sys.exit(1)
        print "  Test successful."
    else:
        print "  Unable to find resource library file, skipping parse test."

import string
import random
import logging
import unittest

def randstr(charspace=string.ascii_lowercase+string.digits, length=6):
    return ''.join(random.sample(charspace, length))

tmp_logger = None # keeps ref to "real" get_logger function for tests below

def skip_if_no_cloudfiles():
    try:
        import cloudfiles
    except:
        nose = fake_package()
        from nose.plugins.skip import SkipTest
        raise SkipTest

def get_test_logger(name='library.testlogger'):
    """Return a basic logger; used to substitute main logger during testing"""
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(name)s %(levelname)s %(message)s')
    return logging.getLogger(name)


class TestCloudfilesDownloader(unittest.TestCase):
    def setUp(self):
        """Replace regular get_logger() with temporary logger"""
        global tmp_logger, get_logger
        tmp_logger = get_logger
        get_logger = get_test_logger

    def tearDown(self):
        """Restore regular get_logger()"""
        global tmp_logger, get_logger
        get_logger = tmp_logger

    def test_download(self):
        skip_if_no_cloudfiles()
        target = 'cloudfiles-test-' + randstr()
        lib = parse_library_from_file(get_library_path())
        lib.package_properties['default_package_container'] = 'pkg'
        dl = CloudfilesDownloader('test.py', target, lib.package_properties)
        assert dl.is_available()
        dl.download_to_cache()
        os.remove(target)

    def test_not_available(self):
        skip_if_no_cloudfiles()
        lib = parse_library_from_file(get_library_path())
        lib.package_properties['default_package_container'] = randstr()
        dl = CloudfilesDownloader('test.py', randstr(), lib.package_properties)
        assert not dl.is_available()

    def test_container_name_prefix_location(self):
        skip_if_no_cloudfiles()
        lib = parse_library_from_file(get_library_path())
        dl = CloudfilesDownloader('container/file', randstr(), lib.package_properties)
        assert dl.container_name == 'container'
        assert dl.location == 'file'

        broken_location = 'bogus/container/file'
        dl = CloudfilesDownloader(broken_location, randstr(), lib.package_properties)
        assert dl.container_name == lib.package_properties['default_package_container']
        assert dl.location == broken_location

if __name__ == "__main__":
    pass
    #test_parser()

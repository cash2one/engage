.. _drivers:

Driver Development
===================

Each driver consists of a *resource manager* (a Python class), a
*resource definition* (JSON metadata that described the resource),
and a *resource library entry*
(JSON metadata that describes where to find the resource).
Each driver has a unique *key*, consisting of a
*name* and *version* (e.g *mysql-linux 4.1*).

By default, the resource
manager is defined in the file
``python_pkg/engage/drivers/standard/name__version/driver.py``,
where *name* and *version* are derived from the associated
resource key fields. Both are modified, if necessary, to be valid
Python identifiers (e.g. "-" and "." replaced with "_").
The resource definition may go in the master resource file at
``metadata/resource_definitions.json`` or in the driver-specific file
``python_pkg/engage/drivers/standard/name__version/resources.json``.
The resource library entry may go in the master library file at
``metadata/resource_library.json`` or in the driver-specifc file
``python_pkg/engage/drivers/standard/name__version/packages.json``.

Resource Defintions
-------------------------------------------------

Resource Library Entry
--------------------------------------------------


Resource Manger Reference
-----------------------------------------------------

.. automodule:: engage.drivers.resource_manager
   :members:


Service Manager Reference
----------------------------------------------------

.. automodule:: engage.drivers.service_manager
   :members:

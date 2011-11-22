Setting Up Engage
=================
We now look at how to obtain and build Engage.

Supported Operating Systems
---------------------------
Engage has been tested on the following platforms:
 * MacOSX 10.5 and 10.6
 * Ubuntu Linux 9.10 and 10.04

*Note: Mac OSX 10.7 is currently not supported due to issues with
MacPorts on that version. Once MacPorts is stable on 10.7, we will add
Engage support.*


Requirements
------------
In order to build engage, you need to have the following software pre-installed:

 * The GNU g++ compiler
 * Python 2.6.x or 2.7.x
 * ocaml (http://caml.inria.fr/)
 * zlib development headers
 * The following Python packages:

   - virtualenv (http://pypi.python.org/pypi/virtualenv)
   - setuptools (http://pypi.python.org/pypi/setuptools)
   - pycrypto (http://pypi.python.org/pypi/pycrypto)

The following software is only required in some situations:

 * Certain application components on MacOSX require macports
   (http://www.macports.org/). Specifically, this includes any
   configuration using Apache or MySQL.

MacOSX details
~~~~~~~~~~~~~~~~~~~~~
G++ can be obtained through Apple's `XCode SDK <http://developer.apple.com/technologies/tools/>`_. 
If you are running MacOSX 10.5 (Leopard) or earlier, the version of Python included with the OS is too old, and
you will have to install a separate local copy of Python 2.6 or Python 2.7. Either way, we recommend installing
MacPorts and using the MacPorts Python package (`python27 <https://trac.macports.org/browser/trunk/dports/lang/python27/Portfile>`_).

If you use MacPorts, you can get pycrypto and ocaml setup with minimal pain by installing the associated ports: `py27-crypto <https://trac.macports.org/browser/trunk/dports/python/py27-crypto/Portfile>`_ and `ocaml <https://trac.macports.org/browser/trunk/dports/lang/ocaml/Portfile>`_, respectively.

The zlib development headers are installed with XCode. For virtualenv and setuptools, follow the instructions on
the associated websites.


Ubuntu Linux details
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Python is pre-installed on Ubuntu. You can obtain g++, ocaml, and the zlib headers  by installing the associated
``apt`` packages: `g++ <http://packages.ubuntu.com/lucid/g++>`_,
`ocaml <http://packages.ubuntu.com/lucid/ocaml>`_, and
`zlib1g-dev <http://packages.ubuntu.com/lucid/zlib1g-dev>`_.
To install pycrypto, you will need to install the Python development header files, available through the
`python2.6-dev <http://packages.ubuntu.com/lucid/python2.6-dev>`_ package (or python2.7-dev if you
have installed Python 2.7). You can then install pycrypto using Python's ``easy_install`` utility or let the
Engage ``bootstrap.py`` utility install it each time you create a new deployment home.

For virtualenv and setuptools, follow the installation  instructions on their respective websites.


Building Engage
---------------
From the top level directory of the engage source distribution, type
``make all``. This will build the configuration engine (written in OCaml and
C++) and download some required packages from the internet.

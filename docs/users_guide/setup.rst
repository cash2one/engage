Setting Up Engage
=================
We now look at how to obtain and build Engage.

Supported Operating Systems
---------------------------
Engage has been tested on the following platforms:
 * MacOSX 10.5 and 10.6
 * Ubuntu Linux 9.10 and 10.04

Requirements
------------
In order to build engage, you need to have the following software pre-installed:

 * The GNU g++ compiler
 * Python 2.6.x or 2.7.x
 * ocaml (http://caml.inria.fr/)
 * The following Python packages:

   - virtualenv (http://pypi.python.org/pypi/virtualenv)
   - setuptools (http://pypi.python.org/pypi/setuptools)
   - pycrypto (http://pypi.python.org/pypi/pycrypto)

The following software is only required in some situations:

 * Certain application components on MacOSX require macports
   (http://www.macports.org/). Specifically, this includes any
   configuration using Apache or MySQL.

Building Engage
---------------
From the top level directory of the engage source distribution, type
``make all``. This will build the configuration engine (written in OCaml and
C++) and download some required packages from the internet.

.. pycca documentation master file, created by
   sphinx-quickstart on Sun Jan 18 19:38:04 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

PyCCA Documentation
===================

PyCCA provides compilers for C and x86 assembly that allow optimized routines
to be compiled and executed at runtime with no external dependencies.
PyCCA supports 32- and 64-bit intel/amd architectures on Linux, OSX, and 
Windows with python 2.7 or 3.4. 

Current status: assembly compiler is beta, C compiler is alpha.


Contents:

.. toctree::
   :maxdepth: 2
   
   asm
   cc


Motivation
----------

Python is an excellent platform for numerical computing but relies
heavily on compiled modules to provide optimized functions. For 
distributed packages, this either increases the burden on the developer
to produce compiled binaries for a variety of platforms, or increases
the burden on the end user to compile the package or its binary 
dependencies. Consequently, many Python developers avoid optimzed
code, preferring instead to advertise "pure-python" as a feature
of their packages.

The objective of pycca is to provide a pure-python approach that
allows assembly and C functions to be compiled and executed at runtime
with no external dependencies. 


Approach
--------

PyCCA allows assembler code to be compiled and executed within Python 
with no external dependencies. This works by:

1. Allocating a block of memory with execute privileges.
2. Compiling assembly instructions into machine code and writing to
   executable memory. 
3. Using the built-in ctypes package to create a python function that
   points to the compiled machine code. 





Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


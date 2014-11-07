PYCC: Pure-python C and assembler compilers
===========================================

Luke Campagnola, 2014


Motivation
----------

Python offers many options for high-performance computing,
but it is often the case that each of these significantly complicates
the task of distributing packages, either because they must be compiled
once for every target platform, or because they depend on third-party
packages that also must be compiled for every target platform. 

The objective of this package is to provide a pure-python approach that
allows the creation of very simple assembler (and eventually C) functions
for fast array computations. 


Approach
--------

The approach taken here is to support a small subset of assembler and C
constructs necessary to compile a simple function and load it directly
into the running process memory. 


Status
------

Pre-pre alpha:

* Can load executable machine code into memory pages on linux (and probably osx)
  and call this executable code via ctypes.
* Simple assembler system in progress; see examples.py.


PYCC: Pure-python C and assembly compilers
==========================================

Luke Campagnola, 2014


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

The objective of pycc is to provide a pure-python approach that
allows assembly and C functions to be compiled and executed at runtime
with no external dependencies. 


Approach
--------

Pycc allows assembler code to be compiled and executed within Python 
with no external dependencies. This works by:

1. Allocating a block of memory with execute privileges.
2. Compiling assembly instructions into machine code and writing to
   executable memory. 
3. Using the built-in ctypes package to create a python function that
   points to the compiled machine code. 


Status: beta
------------

* Can load executable machine code into memory pages
  and call this executable code via ctypes.
* Functional assembly compiler with a relatively limited set of instructions
  (see examples.py and pycc/asm/instructions.py). All instructions
  are tested to produce identical output to the GNU assembly compiler.
* C compiler in early development 
* Examples have been tested on:

  |           |            |  Linux  |   OSX   | Windows |
  |:----------|:-----------|:-------:|:-------:|:-------:|
  |  IA-32    | Python 2.7 |    X    |         |    X    |
  |           | Python 3.4 |    X    |         |         |
  | Intel-64  | Python 2.7 |    X    |    X    |         |
  |           | Python 3.4 |    X    |         |    X    |

* Unit tests pass on 64-bit and 32-bit Linux under python 2.7 and 3.4


Roadmap
-------

* Version 0.3: Basic C compiler (based on pre-parsed data structures) with 
  support for 32- and 64-bit calling conventions on Linux, OSX, and Windows.
* Version 0.4: Parser supporting a subset of C language including functions,
  control flow, and basic data types. 


Differences with GNU-AS
-----------------------

* GAS quietly ignores undefined symbols, treating them as null pointers.
  PyCC will raise an exception.
* GAS quietly truncates displacement values; PyCC will raise an exception.


Todo
----

* Documentation on how to add new instruction support based on intel reference, 
  how to add new unit tests

* Add more floating point instructions

* Add SSE, AVX instructions  (and check cpu flags)

* Support for GIL handling

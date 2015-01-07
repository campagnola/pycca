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


Status: beta
------------

* Can load executable machine code into memory pages
  and call this executable code via ctypes.
* Simple assembler system in progress; see examples.py.
* Examples have been tested on:

  |          | Linux  |   OSX   |  Windows |
  |----------|--------|---------|----------|
  |IA32      |  X     |         |     X    |
  |Intel-64  |  X     |    X    |          |


Todo
----

* Documentation on how to add new instruction support based on intel reference, 
  how to add new unit tests

* Add more floating point instructions

* Add SSE, AVX instructions  (and check cpu flags)

* Better immediate handling:

    * Allow ctypes function pointers as immediate (automatically dereference)
    * Allow basic ctypes objects
    * Something like `long(x)`, `uint(x)`

* Intermediate data structures for C-like function code, something like:

```
func('int', 'my_func', [('int', 'arg1'), ('int', 'arg2')], [
    decl('int', 'j'),
    decl('int', 'i'),
    forloop('i=0', 'i<10', 'i++', [
        assign('j', 'i+1'),
    ]),
    return('j')
])
```

* Support 32/64-bit calling conventions on win, linux, osx

* Simple C compiler



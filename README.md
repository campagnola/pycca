PYCC: Pure-python C and assembler compilers
===========================================

Luke Campagnola, 2014


Motivation
----------

Python is an excellent platform for numerical computing but relies
heavily on compiled modules to provide optimized functions. For 
distributed packages, this either increases the burden on the developer
to produce compiled binaries for a variety of platforms, or increases
the burden on the end user to compile the package (or its binary 
dependencies) for their own system.

The objective of pycc is to provide a pure-python approach that
allows simple assembler (and eventually C) functions to be compiled
and executed at runtime with no external dependencies.


Approach
--------

Pycc allows assembler code to be compiled and
executed within Python with no external dependencies. This works by:

1. Allocating a block of memory with execute privileges.
2. Compiling assembler primitives into machine code and writing to
   executable memory. 
3. Using the built-in ctypes package to create a python function that
   points to the compiled machine code. 


Status: beta
------------

* Can load executable machine code into memory pages
  and call this executable code via ctypes.
* Functional assembly compiler with a relatively limited set of inctructions
  (see examples.py and pycc/asm/instructions.py). All instructions
  are tested to produce identical output to the GNU assembly compiler.
* Examples have been tested on:

  |           |            |  Linux  |   OSX   | Windows |
  |:----------|:-----------|:-------:|:-------:|:-------:|
  |  IA-32    | Python 2.7 |    X    |         |    X    |
  |           | Python 3.4 |         |         |         |
  | Intel-64  | Python 2.7 |    X    |    X    |         |
  |           | Python 3.4 |    X    |         |    X    |

* Unit tests pass on 64-bit Linux under python 2.7 and 3.4


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



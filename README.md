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

Alpha:

* Can load executable machine code into memory pages on linux (and probably osx)
  and call this executable code via ctypes.
* Simple assembler system in progress; see examples.py.


Todo
----

* Clean up ASM system
   * Instruction class: interprets arg types, constructs prefix +opcode +modrm +sib +disp +imm.
     Most instructions should make use of this.
   * Instruction docstrings: description on first line; maybe remove other information?
   * Documentation on how to add new instruction support based on intel reference, 
     how to add new unit tests

* Support for r8-r15

* Add more floating point instructions

* Add SSE, AVX instructions

* Better 32-bit arch support

* Python 3 support

* Intermediate data structures for C-like function code, something like:

```
func('int', 'my_func', [('int', 'arg1'), ('int', 'arg2')], [
    decl('int', 'j'),
    decl('int', 'i'),
    for('i=0', 'i<10', 'i++', [
        assign('j', 'i+1'),
    ]),
    return('j')
])
```

* Support 32/64-bit calling conventions on win, linux, osx

* Simple C compiler



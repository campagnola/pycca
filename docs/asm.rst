PyCCA Assembler
===============


The core of pycca is an x86 assembly compiler that allows the creation and 
execution of machine code for IA-32 and Intel-64 architectures. The output
of pycca's assembler is tested to generate identical output to the GNU 
assembler for all supported instructions.


Assembly language
-----------------

PyCCA's assembler uses a syntax and instruction mnemonics very similar to the 
intel / NASM assembly syntax. Instructions consist of a mnemonic (instruction 
name) followed by whitespace and a number of comma-separated operands::
    
    label:         # Comments follow a hash
       push ebp
       sub esp, 32
       mov eax, dword ptr [edx + ecx*8 + 12]
       jmp label

Note: Many assembler examples found on the internet use the AT&T syntax, which
prefixes register names with '%' and reverses the order of operands (the intel
syntax puts the destination operand first; AT&T puts the source operand first).

Operands may be one of four types:
    
* The name of a register (see :ref:`all registers <registers>`).
* An "immediate" integer data value. These may be signed or unsigned and are
  evaluated as python expressions, so "0xFF" and "0b1101" are also accepted
  syntaxes.
* The name of a label declared elsewhere in the code (these are ultimately
  compiled as immediate values pointing to the address of the label 
  declaration).
* A pointer to data in memory. Pointers provide both a memory address and 
  the size of data they point to.
  
In x86, memory addresses are specified as the sum of a base register, a scaled
offset register, and an integer displacement::
    
    address = base + offset*scale + displacement

Where ``scale`` may be 1, 2, 4, or 8, and addresses may contain any combination 
of these three elements. Memory operands are written with square brackets 
surrounding the address expression. For example:

================================ ==============================================
Memory operand                   Description               
================================ ==============================================
[rax]                            Pointer to address stored in register rax
[eax + ebx*2]                    Address calculated as eax + ebx*2
[0x1000]                         Pointer to address 0x1000
[rax + rbx + 8]                  Address calculated as rax + rbx + 8
word ptr [rbp - 0x10]            Pointer to 2 byte data beginning at rbp - 0x10
qword ptr [eax]                  pointer to 8 byte data beginning at eax
================================ ==============================================

On 64 bit architectures, it is only valid to use 64 or 32 bit registers for 
memory addresses. On 32 bit architectures, it is only valid to use 32 or 16 bit
registers for memory addresses. Note: the allowed expression forms for 16 bit 
addresses are very limited and are not covered here.


Building assembly from Python objects
-------------------------------------

It is also possible to write assembly code as a list of Instruction instances.
This has the advantage of avoiding the parsing stage and facilitating
dynamically-generated assembly code::
    
    from pycca.asm import *
    
    code = [
        label('start'),
        push(ebp),
        mov(ebp, esp),
        push(dword([ebp+12])),
        push(dword([ebp+8])),
        mov(eax, func_ptr),
        call(eax),
        mov(esp, ebp),
        pop(ebp),
        ret(ret_byts),
        jmp('start'),
    ]

Thanks to similarities in the NASM and Python syntaxes, there are only minor 
differences in this approach: 
    
* Instructions are classes and thus require parentheses to instantiate
* Use pointer size functions like ``dword(address)`` instead of ``dword ptr``.
* Labels are also objects and they are referenced by their string name
  (see ``label`` and ``jmp`` lines above).


Compiling Python functions from assembly
----------------------------------------

Executing this code is only a matter of compiling it into a ctypes function and
providing the return and argument types::
    
    func = mkfunction(code)
    func.restype = ctypes.c_double
    func.argtypes = (ctypes.c_double,)
    
    result = func(3.1415)

For more examples of building and calling functions, accessing array data, and
more, see `asm_examples.py <https://github.com/lcampagn/pycca/blob/master/asm_examples.py>`_. 
For lists of supported :ref:`instructions <instructions>` and 
:ref:`registers <registers>`, see the :ref:`asm_api_ref`. 



Differences with GNU-AS
-----------------------

PyCCA's assembly is closely modeled after the intel assembler syntax and is
tested to produce identical output to the GNU assembler using the
".intel-mnemonic" directive. There are a few differences, however:

* GAS quietly ignores undefined symbols, treating them as null pointers;
  pycca will raise an exception.
* GAS quietly truncates displacement values; pycca will raise an exception if
  the displacement is too large to be encoded.


Adding support for new instructions
-----------------------------------

Although pycca currently supports only a small subset of the x86 instruction
set, it is relatively simple to add support for new instructions by 
transcribing the instruction encoding from the `intel reference (see volume 2) 
<http://www.intel.com/content/www/us/en/processors/architectures-software-developer-manuals.html>`.
Github pull requests adding new instruction support are encuraged, but should
be accompanied by adequate documentation and unit tests.

To add new instructions:
    
* Look through ``pycca/asm/instructions.py`` for examples of already implemented
  instructions. 
* Create a new subclass of Instruction and set the ``name`` class attribute to
  the instruction mnemonic.
* The class docstrings are generally copied from the first paragraph or two
  from the instruction description in the Intel reference, with minor 
  modifications.
* The ``modes`` attribute should be set to an OrderedDict containing data
  found in the instruction encoding table
  
    * Keys must be tuples describing the operand types (r32, r/m64, imm8, etc.)
      accepted for each encoding.
    * Values must be a sequence of 4 items: [instruction encoding, operand
      encoding, 64-bit support, and 32-bit support]. These values are usually
      copied verbatim from the reference manual (but note that the manual
      is often inconsistent or contains errors; when in doubt refer to the 
      already implemented instructions for examples).
      
* The ``operand_enc`` attribute must be a dict containing information found in
  the operand encoding table for that instruction in the Intel reference. Keys
  are the same strings as found in ``modes[][1]``, and each value is a list
  of encoding strings for each operand. These strings are usually copied 
  verbatim from the reference, but again this representation is not always
  consistent (in fact some instructions lack an operand encoding table
  altogether). 
* Add a new test function to ``pycca/asm/test_asm.py``, using other instructions
  as examples. Each mode in the ``modes`` attribute should be tested at least 
  once.
* For debugging, make use of tools in ``pycca.asm.util``, especially the 
  ``compare``, ``as_code``, and ``phexbin`` functions.

Note that advanced CPU extensions such as SSE2 and AVX are not yet supported.



.. _asm_api_ref:

Assembly API Reference
======================


Building executable code
------------------------

.. autofunction:: pycca.asm.mkfunction

.. autoclass:: pycca.asm.CodePage
    :members:

For more examples of building and calling functions, accessing array data, and
more, see `asm_examples.py <https://github.com/lcampagn/pycca/blob/master/asm_examples.py>`_. 

.. _registers:

Supported registers
-------------------

All registers may be accessed as attributes of the ``pycca.asm`` or 
``pycca.asm.register`` modules.

General purpose registers:

+-------+---------------+--------------------------------+
|arch   |   32 / 64     |       64 only                  |
+-------+----+----+-----+-----+------+------+------+-----+
|size   |8   |16  |32   |64   |8     |16    |32    |64   |
+-------+----+----+-----+-----+------+------+------+-----+
|       |al  |ax  |eax  |rax  |r8b   |r8w   |r8d   |r8   |
+-------+----+----+-----+-----+------+------+------+-----+
|       |cl  |cx  |ecx  |rcx  |r9b   |r9w   |r9d   |r9   |
+-------+----+----+-----+-----+------+------+------+-----+
|       |dl  |dx  |edx  |rdx  |r10b  |r10w  |r10d  |r10  |
+-------+----+----+-----+-----+------+------+------+-----+
|       |bl  |bx  |ebx  |rbx  |r11b  |r11w  |r11d  |r11  |
+-------+----+----+-----+-----+------+------+------+-----+
|       |ah  |sp  |esp  |rsp  |r12b  |r12w  |r12d  |r12  |
+-------+----+----+-----+-----+------+------+------+-----+
|       |ch  |bp  |ebp  |rbp  |r13b  |r13w  |r13d  |r13  |
+-------+----+----+-----+-----+------+------+------+-----+
|       |dh  |si  |esi  |rsi  |r14b  |r14w  |r14d  |r14  |
+-------+----+----+-----+-----+------+------+------+-----+
|       |bh  |di  |edi  |rdi  |r15b  |r15w  |r15d  |r15  |
+-------+----+----+-----+-----+------+------+------+-----+


Floating-point registers:

+-------+-----------------+
|arch   |     32 / 64     |
+-------+-----+-----+-----+
|size   |80   |64   |128  |
+-------+-----+-----+-----+
|       |st(0)|mm0  |xmm0 |
+-------+-----+-----+-----+
|       |st(1)|mm1  |xmm1 |
+-------+-----+-----+-----+
|       |st(2)|mm2  |xmm2 |
+-------+-----+-----+-----+
|       |st(3)|mm3  |xmm3 |
+-------+-----+-----+-----+
|       |st(4)|mm4  |xmm4 |
+-------+-----+-----+-----+
|       |st(5)|mm5  |xmm5 |
+-------+-----+-----+-----+
|       |st(6)|mm6  |xmm6 |
+-------+-----+-----+-----+
|       |st(7)|mm7  |xmm7 |
+-------+-----+-----+-----+


.. automodule:: pycca.asm.register
    :members:


.. _instructions:

Supported instructions
----------------------

All instructions currently supported by pycca are listed below. Most 
instructions accept a variety of operand types which are listed in a table
for each instruction:

============ =========================
Operand code Operand type
============ =========================
r            general purpose register
r/m          register or memory
imm          immediate value
st(i)        x87 ST register
xmmI         xmm register
============ =========================

Operand codes are followed by one or more values indicating the allowed size(s)
for the operand. For example, the ``push`` instruction gives the following 
table:

=============== ====== ====== ======================================
src             32-bit 64-bit description
=============== ====== ====== ======================================
r/m8             X      X     Push src onto stack
r/m16            X      X     
r/m32            X
r/m64                   X
imm8/32          X      X
=============== ====== ====== ======================================

This table indicates that ``push`` accepts one operand ``src`` that may be 
a general purpose register, a memory address, or an immediate value. The 
allowed operand sizes depend on the target architecture (for this instruction,
64 bit memory/register operands are not allowed on 32 bit architectures and
vice-versa).


.. automodule:: pycca.asm.instructions
    :members:


The Instruction class
--------------------------

.. autoclass:: pycca.asm.Instruction
    :members:


Debugging tools
---------------

.. autofunction:: pycca.asm.util.compare

.. autofunction:: pycca.asm.util.as_code

.. autofunction:: pycca.asm.util.phexbin


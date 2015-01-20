PyCA Assembler
==============


The core of pyca is an x86 assembly compiler that allows the creation and 
execution of machine code for IA-32 and Intel-64 architectures. The output
of pyca's assembler is tested to generate identical output to the GNU 
assembler for all supported instructions.


Assembly Language
-----------------

Pyca's assembler uses a syntax and instruction mnemonics very similar to the 
intel assembly syntax. Instructions consist of a mnemonic (instruction name) 
followed by whitespace and a number of comma-separated operands::
    
    push ebp
    sub esp, 32
    mov eax, dword ptr [edx + ecx*8 + 12]

Many assembler examples found on the internet use the ATT syntax, which
prefixes register names with '%' and reverses the order of operands (the intel
syntax puts the destination operand first; ATT puts the source operand first). 

It is also possible to write assembly code as a list of Instruction instances.
This has the advantage of avoiding the parsing stage and facilitating
dynamically-generated assembly code::
    
    from pyca.asm import *
    
    code = [
        push(ebp),
        mov(ebp, esp),
        push(dword([ebp+12])),
        push(dword([ebp+8])),
        mov(eax, func_ptr),
        call(eax),
        mov(esp, ebp),
        pop(ebp),
        ret(ret_byts),
    ]

Executing this code is only a matter of compiling it into a ctypes function and
providing the return and argument types::
    
    func = mkfunction(code)
    func.restype = ctypes.c_double
    func.argtypes = (ctypes.c_double,)
    
    result = func(3.1415)

For more examples of building and calling functions, accessing array data, and
more, see `asm_examples.py <https://github.com/lcampagn/pyca/blob/master/asm_examples.py>`_. 
For lists of supported :ref:`instructions <instructions>` and 
:ref:`registers <registers>`, see the :ref:`asm_api_ref`. 


Differences with GNU-AS
-----------------------

Pyca's assembly is closely modeled after the intel assembler syntax and is
tested to produce identical output to the GNU assembler using the
".intel-mnemonic" directive. There are a few differences, however:

* GAS quietly ignores undefined symbols, treating them as null pointers;
  pyca will raise an exception.
* GAS quietly truncates displacement values; pyca will raise an exception if
  the displacement is too large to be encoded.


Adding support for new instructions
-----------------------------------

Although pyca currently supports only a small subset of the x86 instruction
set, it is relatively simple to add support for new instructions by 
transcribing the instruction encoding from the `intel reference (see volume 2) 
<http://www.intel.com/content/www/us/en/processors/architectures-software-developer-manuals.html>`.
Github pull requests adding new instruction support are encuraged, but should
be accompanied by adequate documentation and unit tests.

To add new instructions:
    
* Look through ``pyca/asm/instructions.py`` for examples of already implemented
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
* Add a new test function to ``pyca/asm/test_asm.py``, using other instructions
  as examples. Each mode in the ``modes`` attribute should be tested at least 
  once.
* For debugging, make use of tools in ``pyca.asm.util``, especially the 
  ``compare``, ``as_code``, and ``phexbin`` functions.

Note that advanced CPU extensions such as SSE2 and AVX are not yet supported.


.. _asm_api_ref:

Assembly API Reference
======================


Building executable code
------------------------

.. autofunction:: pyca.asm.mkfunction

.. autoclass:: pyca.asm.CodePage
    :members:

For more examples of building and calling functions, accessing array data, and
more, see `asm_examples.py <https://github.com/lcampagn/pyca/blob/master/asm_examples.py>`_. 

.. _registers:

Supported registers
-------------------

All registers may be accessed as attributes of the ``pyca.asm`` or 
``pyca.asm.register`` modules.

+-------+---------------+--------------------------------+-----------------+
|arch   |   32 / 64     |       64 only                  |     32/64       |
+-------+----+----+-----+-----+------+------+------+-----+-----+-----+-----+
|size   |8   |16  |32   |64   |8     |16    |32    |64   |80   |64   |128  |
+-------+----+----+-----+-----+------+------+------+-----+-----+-----+-----+
|       |al  |ax  |eax  |rax  |r8b   |r8w   |r8d   |r8   |st(0)|mm0  |xmm0 |
+-------+----+----+-----+-----+------+------+------+-----+-----+-----+-----+
|       |cl  |cx  |ecx  |rcx  |r9b   |r9w   |r9d   |r9   |st(0)|mm1  |xmm1 |
+-------+----+----+-----+-----+------+------+------+-----+-----+-----+-----+
|       |dl  |dx  |edx  |rdx  |r10b  |r10w  |r10d  |r10  |st(0)|mm2  |xmm2 |
+-------+----+----+-----+-----+------+------+------+-----+-----+-----+-----+
|       |bl  |bx  |ebx  |rbx  |r11b  |r11w  |r11d  |r11  |st(0)|mm3  |xmm3 |
+-------+----+----+-----+-----+------+------+------+-----+-----+-----+-----+
|       |ah  |sp  |esp  |rsp  |r12b  |r12w  |r12d  |r12  |st(0)|mm4  |xmm4 |
+-------+----+----+-----+-----+------+------+------+-----+-----+-----+-----+
|       |ch  |bp  |ebp  |rbp  |r13b  |r13w  |r13d  |r13  |st(0)|mm5  |xmm5 |
+-------+----+----+-----+-----+------+------+------+-----+-----+-----+-----+
|       |dh  |si  |esi  |rsi  |r14b  |r14w  |r14d  |r14  |st(0)|mm6  |xmm6 |
+-------+----+----+-----+-----+------+------+------+-----+-----+-----+-----+
|       |bh  |di  |edi  |rdi  |r15b  |r15w  |r15d  |r15  |st(0)|mm7  |xmm7 |
+-------+----+----+-----+-----+------+------+------+-----+-----+-----+-----+

.. automodule:: pyca.asm.register
    :members:


.. _instructions:

Supported instructions
----------------------

.. automodule:: pyca.asm.instructions
    :members:


The Instruction class
--------------------------

.. autoclass:: pyca.asm.Instruction
    :members:


Debugging tools
---------------

.. autofunction:: pyca.asm.util.compare

.. autofunction:: pyca.asm.util.as_code

.. autofunction:: pyca.asm.util.phexbin


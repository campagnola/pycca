# -'- coding: utf-8 -'-
"""
  Overview of ia-32 and intel-64 instructions
---------------------------------------------------


 [  Prefixes  ][  Opcode  ][  ModR/M  ][  SIB  ][  Disp  ][  Immediate  ]


 All fields except opcode are optional. Each opcode determines the set of
 allowed fields.

 Prefixes:  up to 4 prefixes, 1 byte each, in any order
 Opcode:    1-3 byte code specifying instruction
 ModR/M:    1 byte specifying source registers for memory addresses
            and sometimes holding opcode extensions as well
 SIB:       1 byte further specifying
 Disp:      1, 2, or 4-byte memory address displacement value added to 
            ModR/M address
 Immediate: 1, 2, or 4-byte operand data embedded within instruction



  References
---------------

Self-modifying programs
https://gist.github.com/dcoles/4071130
http://www.unix.com/man-page/freebsd/2/mprotect/
http://stackoverflow.com/questions/3125756/allocate-executable-ram-in-c-on-linux

Assembly
http://www.cs.virginia.edu/~evans/cs216/guides/x86.html

Machine code
http://www.codeproject.com/Articles/662301/x-Instruction-Encoding-Revealed-Bit-Twiddling-fo
http://wiki.osdev.org/X86-64_Instruction_Encoding
http://www.c-jump.com/CIS77/CPU/x86/lecture.html
http://ref.x86asm.net/coder32.html
http://ref.x86asm.net/coder64.html

Official, obtuse reference:
http://www.intel.com/content/www/us/en/processors/architectures-software-developer-manuals.html
"""

import sys

if sys.maxsize > 2**32:
    ARCH = 64
else:
    ARCH = 32

from .instructions import *
from .register import *
from .pointer import byte, word, dword, qword
from .codepage import CodePage, mkfunction
from .instruction import label
from .util import *

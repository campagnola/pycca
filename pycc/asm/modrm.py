# -'- coding: utf-8 -'-

import sys

from .register import Register
from .pointer import Pointer, mod_reg_rm
from .util import long


class ModRmSib(object):
    """Container for mod_reg_rm + sib + displacement string and related
    information.
    
    The .code property is the compiled byte code
    The .argtypes property is a description of the input types:
        'rr' => both inputs are Registers
        'rm' => a is Register, b is Pointer
        'mr' => a is Pointer, b is Register
        'xr' => a is opcode extension, b is register 
        'xp' => a is opcode extension, b is Pointer 
    The .rex property gives the REX byte required to encode the instruction
    """
    def __init__(self, a, b):
        self.a = a
        self.b = b
        
        self.argtypes = ''
        for op in (a, b):
            if isinstance(op, Register):
                self.argtypes += 'r'
            elif isinstance(op, (int, long)) and op < 8:
                self.argtypes += 'x'
            elif isinstance(op, Pointer):
                self.argtypes += 'm'
            else:
                raise Exception("Arguments must be Register, Pointer, or "
                                "opcode extension.")
        
        self.rex = 0
        if self.argtypes in ('rr', 'xr'):
            rex_byt, self.code = mod_reg_rm('dir', a, b)
            if self.argtypes != 'xr' and a.rex:
                self.rex |= rex.r
            if b.rex: 
                self.rex |= rex.b
        elif self.argtypes == 'mr':
            rex_byt, self.code = a.modrm_sib(b)
            self.rex |= rex_byt
        elif self.argtypes in ('rm', 'xm'):
            rex_byt, self.code = b.modrm_sib(a)
            self.rex |= rex_byt
        else:
            raise TypeError('Invalid argument types: %s, %s' % (type(a), type(b)))

        assert isinstance(self.code, bytes)

# -'- coding: utf-8 -'-
import sys

if sys.maxsize > 2**32:
    ARCH = 64
else:
    ARCH = 32



#   Instruction Prefixes
#----------------------------------------

class Rex(object):
    pass

rex = Rex()
rex.w = 0b01001000  # 64-bit operands
rex.r = 0b01000100  # Extension of ModR/M reg field to 4 bits
rex.x = 0b01000010  # Extension of SIB index field to 4 bits
rex.b = 0b01000001  # Extension of ModR/M r/m field, SIB base field, or 
                    # opcode reg field

#  Note 1: REX prefix always immediately precedes the first opcode byte (or
#  opcode escape byte). All other prefixes come before REX.

#  Note 2: rex.r, rex.x, rex.b actually _become_ the 4th bit for the fields
#  they extend; the original fields themselves still occupy 3 bits within their
#  original byte. This is often notated as eg 1.111, where the first digit 
#  indicates the extension bit provided by rex.



#     ModR/M byte
#-----------------------------------------

mod_vals = {
    'ind':   0b00000000, # Fetch contents of address specified in R/M section register
    'ind8':  0b01000000, # Same as 'ind' with 8-bit displacement following mod/rm byte
    'ind32': 0b10000000, # Same as 'ind' with 32-bit displacement following mod/rm byte
    'dir':   0b11000000, # Direct addressing; use register directly. 
}
def mod_reg_rm(mod, reg, rm):
    """Generate a mod_reg_r/m byte. This byte is used to specify a variety of
    different modes for computing a memory location by combining register
    values with an optional displacement value, or by adding an extra SIB byte.
    
    Returns (rex, mod_reg_rm)
    
    The Mod-Reg-R/M byte consists of three fields:
    
        mod  reg  r/m
         76  543  210  
     
    The reg field is used either to indicate a particular register as an 
    operand, or to hold opcode extensions. 
    
    The mod and r/m fields together specify a variety of different address 
    calculation modes:
    
        mod   r/m    address
        ---   ---    --------
        00    000    [eax]
              001    [ecx]
              010    [edx]
              011    [ebx]
              100    + SIB byte
              101    + disp32 
              110    [esi]
              111    [edi]
        01    000    [eax] + disp8
              001    [ecx] + disp8
              010    [edx] + disp8
              011    [ebx] + disp8
              100    + SIB byte + disp8
              101    + disp32 
              110    [esi] + disp8
              111    [edi] + disp8
        10    000    [eax] + disp32
              001    [ecx] + disp32
              010    [edx] + disp32
              011    [ebx] + disp32
              100    + SIB byte + disp32
              101    + disp32
              110    [esi] + disp32
              111    [edi] + disp32
        11    000    [eax]
              001    [ecx]
              010    [edx]
              011    [ebx]
              100    [esp]
              101    [ebp] 
              110    [esi]
              111    [edi]
    
    "+ SIB byte" indicates that a SIB byte follows the MODR/M byte
    "+ disp8"    indicates that an 8-bit displacement value follows the MODR/M
                 byte (or SIB if present)
    "+ disp32"   indicates that a 32-bit displacement value follows the MODR/M
                 byte (or SIB if present)
    """
    rex_byt = 0
    if rm == 'sib':
        rm = 0b100  # Indicates SIB byte usage when used as R/M field in ModR/M
    elif rm == 'disp':
        rm = 0b101  # Indicates displacement value without register offset when used
                    # as R/M field in ModR/M
    if isinstance(reg, Register):
        if reg.rex:
            rex_byt |= rex.r
        reg = reg.val
    if isinstance(rm, Register):
        if rm.rex:
            rex_byt |= rex.b
        rm = rm.val
    return rex_byt, chr(mod_vals[mod] | reg << 3 | rm)



#     SIB byte
#-----------------------------------------

def mk_sib(byts, offset, base):
    """Generate SIB byte
    
    Return (rex, sib)
    
    byts : 0, 1, 2, or 3
    offset : Register or None
    base : register or 'disp'
    
    Address is computed as [base] + [offset] * 2^byts
    When base is [ebp], add disp32.
    When offset is [esp], no offset is applied.
    """
    rex_byt = 0
    
    if offset is None:
        offset = rsp
    else:
        if offset.rex:
            rex_byt |= rex.x
    
    if base == 'disp':
        base = rbp
    else:
        if base.rex:
            rex_byt |= rex.b
    
    return rex_byt, chr(byts << 6 | offset.val << 3 | base.val)


#
#   Overview of memory addressing modes
#
#   By combining the REX prefix, opcode, ModR/M, and SIB bytes, we can specify 
#   four different general forms for calculating a memory address:
#
#   1.   [  REX   ][  Opcode  ]
#         0100W00B         reg
#
#         => Opcode specifies register in last 3 bits; REX extends the register
#            to become B.reg.
#
#   2.   [  REX   ][  Opcode  ][    ModR/M    ]
#         0100WR0B              11 + reg + r/m
#
#         => mod is 11, so data is pulled directly from reg and r/m. REX.R and 
#            REX.B extend the reg and r/m fields, respectively.
#                                 
#   2.   [  REX   ][  Opcode  ][    ModR/M    ]
#         0100WR0B              mo + reg + r/m
#         
#         => mod != 11 and r/m != 100, so there is no SIB byte and the memory
#            address is calculated from mod, B.r/m, and a possible 
#            displacement.
#         
#   3.   [  REX   ][  Opcode  ][    ModR/M    ][   SIB   ]
#         0100WRXB              mo + reg + 100
#                                 
#         => mod != 11 and r/m == 100, so memory address is calculated using 
#            SIB with REX.X extending the SIB base field and REX.R, REX.B 
#            extending reg and r/m, respectively.
#

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
    The .argbits property is a tuple (a.bits, b.bits)
    The .bits property gives the maximum bit depth of any register
    The .rex property gives the REX byte required to encode the instruction
    """
    def __init__(self, a, b):
        self.a = a = interpret(a)
        self.b = b = interpret(b)
        
        self.argtypes = ''
        for op in (a, b):
            if isinstance(op, Register):
                self.argtypes += 'r'
            elif isinstance(op, int) and op < 8:
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

        if hasattr(a, 'bits'):
            self.argbits = (a.bits, b.bits)
            self.bits = max(self.argbits)
        else:
            self.argbits = (None, b.bits)
            self.bits = b.bits

        assert isinstance(self.code, str)
    

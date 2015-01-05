# -'- coding: utf-8 -'-

import struct

from .register import *
from . import ARCH

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


def interpret(arg):
    """General function for interpreting instruction arguments.
    
    This converts list arguments to Pointer, allowing syntax like::
    
        mov(rax, [0x1000])  # 0x1000 is a memory address
        mov(rax, 0x1000)    # 0x1000 is an immediate value
    """
    if isinstance(arg, list):
        assert len(arg) == 1
        arg = arg[0]
        if isinstance(arg, Register):
            return Pointer(reg1=arg)
        elif isinstance(arg, int):
            return Pointer(disp=arg)
        elif isinstance(arg, Pointer):
            return arg
        else:
            raise TypeError("List arguments may only contain a single int, "
                            "Register, or Pointer.")
    else:
        return arg


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


def pack_int(x, int8=False, int16=True, int32=True, int64=True):
    """Pack a signed integer into the smallest format possible.
    """
    modes = ['bhiq'[i] for i,m in enumerate([int8, int16, int32, int64]) if m]
    for mode in modes:
        try:
            return struct.pack(mode, x)
        except struct.error:
            if mode == modes[-1]:
                raise
            # otherwise, try the next mode

def pack_uint(x, uint8=False, uint16=True, uint32=True, uint64=True):
    """Pack an unsigned integer into the smallest format possible.
    """
    modes = ['BHIQ'[i] for i,m in enumerate([uint8, uint16, uint32, uint64]) if m]
    for mode in modes:
        try:
            return struct.pack(mode, x)
        except struct.error:
            if mode == modes[-1]:
                raise
            # otherwise, try the next mode


class Pointer(object):
    """Representation of an effective memory address calculated as a 
    combination of values::
    
        ebp-0x10   # 16 bytes lower than base pointer
        0x1000 + 8*eax + ebx
    """
    def __init__(self, reg1=None, scale=None, reg2=None, disp=None):
        self.reg1 = reg1
        self.scale = scale
        self.reg2 = reg2
        self.disp = disp
        self._bits = None
    
    def copy(self):
        return Pointer(self.reg1, self.scale, self.reg2, self.disp)

    #@property
    #def addrsize(self):
        #"""Maximum number of bits for encoded address size.
        #"""
        #regs = []
        #if self.reg1 is not None:
            #regs.append(self.reg1.bits)
        #if self.reg2 is not None:
            #regs.append(self.reg2.bits)
        #if self.disp is not None:
            #if len(regs) == 0:
                
                #return ARCH
            #regs.append(32)
        #return max(regs)
    @property
    def prefix(self):
        """Return prefix string required when encoding this address.
        
        The value returned will be either '' or '\x67'
        """
        regs = []
        if self.reg1 is not None:
            regs.append(self.reg1.bits)
        if self.reg2 is not None:
            regs.append(self.reg2.bits)
        if len(regs) == 0:
            return ''
        if max(regs) == ARCH//2:
            return '\x67'
        return ''
        
    @property
    def bits(self):
        """The size of the data referenced by this pointer.
        """
        if self._bits is None:
            return ARCH
        else:
            return self._bits
        
    @bits.setter
    def bits(self, b):
        self._bits = b

    def __add__(self, x):
        y = self.copy()
        if isinstance(x, Register):
            if y.reg1 is None:
                y.reg1 = x
            elif y.reg2 is None:
                y.reg2 = x
            else:
                raise TypeError("Pointer cannot incorporate more than"
                                " two registers.")
        elif isinstance(x, int):
            if y.disp is None:
                y.disp = x
            else:
                y.disp += x
        elif isinstance(x, Pointer):
            if x.disp is not None:
                y = y + x.disp
            if x.reg2 is not None:
                y = y + x.reg2
            if x.reg1 is not None and x.scale is None:
                y = y + x.reg1
            elif x.reg1 is not None and x.scale is not None:
                if y.scale is not None:
                    raise TypeError("Pointer can only hold one scaled"
                                    " register.")
                if y.reg1 is not None:
                    if y.reg2 is not None:
                        raise TypeError("Pointer cannot incorporate more than"
                                        " two registers.")
                    # move reg1 => reg2 to make room for a new reg1*scale
                    y.reg2 = y.reg1
                y.reg1 = x.reg1
                y.scale = x.scale
            
        return y

    def __radd__(self, x):
        return self + x

    def __repr__(self):
        return "Pointer(%s)" % str(self)

    def __str__(self):
        parts = []
        if self.disp is not None:
            parts.append('0x%x' % self.disp)
        if self.reg1 is not None:
            if self.scale is not None:
                parts.append("%d*%s" % (self.scale, self.reg1.name))
            else:
                parts.append(self.reg1.name)
        if self.reg2 is not None:
            parts.append(self.reg2.name)
        ptr = '[' + ' + '.join(parts) + ']'
        if self._bits is None:
            return ptr
        else:
            pfx = {8: 'byte', 16: 'word', 32: 'dword', 64: 'qword'}[self._bits]
            return pfx + ' ptr ' + ptr

    def modrm_sib(self, reg=None):
        """Generate a string consisting of mod_reg_r/m byte, optional SIB byte,
        and optional displacement bytes.
        
        The *reg* argument is placed into the modrm.reg field.
        
        Return tuple (rex, code).
        
        Note: this method implements many special cases required to match 
        GNU output:
        * Using ebp/rbp/r13 as r/m or as sib base causes addition of an 8-bit
          displacement (0)
        * For [reg1+esp], esp is always moved to base
        * Special encoding for [*sp]
        * Special encoding for [disp]
        """
        # check address size is supported
        for r in (self.reg1, self.reg2):
            if r is not None and r.bits < ARCH//2:
                raise TypeError("Invalid register for pointer: %s" % r.name)

        # do some simple displacement parsing
        if self.disp in (None, 0):
            disp = ''
            mod = 'ind'
        else:
            disp = pack_int(self.disp, int8=True, int16=False, int32=True, int64=False)
            mod = {1: 'ind8', 4: 'ind32'}[len(disp)]

        if self.scale in (None, 0):
            # No scale means we are free to change the order of registers
            regs = [x for x in (self.reg1, self.reg2) if x is not None]
            
            if len(regs) == 0:
                # displacement only
                if self.disp in (None, 0):
                    raise TypeError("Cannot encode empty pointer.")
                disp = struct.pack('i', self.disp)
                mrex, modrm = mod_reg_rm('ind', reg, 'sib')
                srex, sib = mk_sib(0, None, 'disp')
                return mrex|srex, modrm + sib + disp
            elif len(regs) == 1:
                # one register; put this wherever is most convenient.
                if regs[0].val == 4:
                    # can't put this in r/m; use sib instead.
                    mrex, modrm = mod_reg_rm(mod, reg, 'sib')
                    srex, sib = mk_sib(0, rsp, regs[0])
                    return mrex|srex, modrm + sib + disp
                elif regs[0].val == 5 and disp == '':
                    mrex, modrm = mod_reg_rm('ind8', reg, regs[0])
                    return mrex, modrm + '\x00'
                else:
                    # Put single register in r/m, add disp if needed.
                    mrex, modrm = mod_reg_rm(mod, reg, regs[0])
                    return mrex, modrm + disp
            else:
                # two registers; swap places if necessary.
                if regs[0] in (esp, rsp): # seems to be unnecessary for r12d
                    if regs[1] in (esp, rsp):
                        raise TypeError("Cannot encode registers in SIB: %s+%s" 
                                        % (regs[0].name, regs[1].name))
                    # don't put *sp registers in offset
                    regs.reverse()
                elif regs[1].val == 5 and disp == '':
                    # if *bp is in base, we need to add 8bit disp
                    mod = 'ind8'
                    disp = '\x00'
                    
                mrex, modrm = mod_reg_rm(mod, reg, 'sib')
                srex, sib = mk_sib(0, regs[0], regs[1])
                return mrex|srex, modrm + sib + disp
                
        else:
            # Must have SIB; cannot change register order
            byts = {None:0, 1:0, 2:1, 4:2, 8:3}[self.scale]
            offset = self.reg1
            base = self.reg2
            
            # sanity checks
            if offset is None:
                raise TypeError("Cannot have SIB scale without offset register.")
            if offset.val == 4:
                raise TypeError("Cannot encode register %s as SIB offset." % offset.name)
            #if base is not None and base.val == 5:
                #raise TypeError("Cannot encode register %s as SIB base." % base.name)

            if base is not None and base.val == 5 and disp == '':
                mod = 'ind8'
                disp = '\x00'
            
            if base is None:
                base = rbp
                mod = 'ind'
                disp = disp + '\0' * (4-len(disp))
            
            mrex, modrm = mod_reg_rm(mod, reg, 'sib')
            srex, sib = mk_sib(byts, offset, base)
            return mrex|srex, modrm + sib + disp
                
        

def qword(ptr):
    if not isinstance(ptr, Pointer):
        if not isinstance(ptr, list):
            ptr = [ptr]
        ptr = interpret(ptr)
    ptr.bits = 64
    return ptr

def dword(ptr):
    if not isinstance(ptr, Pointer):
        if not isinstance(ptr, list):
            ptr = [ptr]
        ptr = interpret(ptr)
    ptr.bits = 32
    return ptr
        
def word(ptr):
    if not isinstance(ptr, Pointer):
        if not isinstance(ptr, list):
            ptr = [ptr]
        ptr = interpret(ptr)
    ptr.bits = 16
    return ptr
        
def byte(ptr):
    if not isinstance(ptr, Pointer):
        if not isinstance(ptr, list):
            ptr = [ptr]
        ptr = interpret(ptr)
    ptr.bits = 8
    return ptr

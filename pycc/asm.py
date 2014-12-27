# -'- coding: utf-8 -'-
"""

Self-modifying programs
https://gist.github.com/dcoles/4071130
http://www.unix.com/man-page/freebsd/2/mprotect/
http://stackoverflow.com/questions/3125756/allocate-executable-ram-in-c-on-linux


Assembly

http://www.cs.virginia.edu/~evans/cs216/guides/x86.html



Machine code

Great tutorial:
http://www.codeproject.com/Articles/662301/x-Instruction-Encoding-Revealed-Bit-Twiddling-fo

http://wiki.osdev.org/X86-64_Instruction_Encoding
http://www.c-jump.com/CIS77/CPU/x86/lecture.html

Comprehensive machine code references:
http://ref.x86asm.net/coder32.html
http://ref.x86asm.net/coder64.html

Official, obtuse reference:
http://www.intel.com/content/www/us/en/processors/architectures-software-developer-manuals.html

"""


from __future__ import division
import ctypes
import sys
import os
import errno
import mmap
import re
import struct
import subprocess
import tempfile
import math
import collections

if sys.maxsize > 2**32:
    ARCH = 64
else:
    ARCH = 32


#   Overview of ia-32 and intel-64 instructions
#---------------------------------------------------

#
#  [  Prefixes  ][  Opcode  ][  ModR/M  ][  SIB  ][  Disp  ][  Immediate  ]
#
# 
#  All fields except opcode are optional. Each opcode determines the set of
#  allowed fields.
#
#  Prefixes:  up to 4 prefixes, 1 byte each, in any order
#  Opcode:    1-3 byte code specifying instruction
#  ModR/M:    1 byte specifying source registers for memory addresses
#             and sometimes holding opcode extensions as well
#  SIB:       1 byte further specifying
#  Disp:      1, 2, or 4-byte memory address displacement value added to 
#             ModR/M address
#  Immediate: 1, 2, or 4-byte operand data embedded within instruction
#



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
            self.code = mod_reg_rm('dir', a, b)
            if self.argtypes != 'xr' and a.rex:
                self.rex |= rex.r
            if b.rex: 
                self.rex |= rex.b
        elif self.argtypes == 'mr':
            rex, self.code = a.modrm_sib(b)
            self.rex |= rex
        elif self.argtypes in ('rm', 'xm'):
            rex, self.code = b.modrm_sib(a)
            self.rex |= rex
        else:
            raise TypeError('Invalid argument types: %s, %s' % (type(a), type(b)))

        if hasattr(a, 'bits'):
            self.argbits = (a.bits, b.bits)
            self.bits = max(self.argbits)
        else:
            self.argbits = (None, b.bits)
            self.bits = b.bits

        
    
    



#   Register definitions
#----------------------------------------

class Register(object):
    """General purpose register.
    """
    def __init__(self, val, name, bits):
        self._val = val
        self._name = name
        self._bits = bits

    @property
    def name(self):
        """Register name
        """
        return self._name

    @property
    def bits(self):
        """Register size in bits
        """
        return self._bits

    @property
    def val(self):
        """3-bit integer code for this register.
        """
        return self._val & 0b111
    
    @property
    def rex(self):
        """Bool indicating value of 4th bit of register code
        """
        return self._val & 0b1000 > 0
        
    def __add__(self, x):
        if isinstance(x, Register):
            return Pointer(reg1=x, reg2=self)
        elif isinstance(x, Pointer):
            return x.__add__(self)
        elif isinstance(x, int):
            return Pointer(reg1=self, disp=x)
        else:
            raise TypeError("Cannot add type %s to Register." % type(x))

    def __radd__(self, x):
        return self + x

    def __sub__(self, x):
        if isinstance(x, int):
            return Pointer(reg1=self, disp=-x)
        else:
            raise TypeError("Cannot subtract type %s from Register." % type(x))

    def __mul__(self, x):
        if isinstance(x, int):
            if x not in [1, 2, 4, 8]:
                raise ValueError("Register can only be multiplied by 1, 2, 4, or 8.")
            return Pointer(reg1=self, scale=x)
        else:
            raise TypeError("Cannot multiply Register by type %s." % type(x))
        
    def __rmul__(self, x):
        return self * x

    def __repr__(self):
        return "Register(0x%x, %s, %d)" % (self._val, self._name, self._bits)
        

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
        self._bits = ARCH
    
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
        return '[' + ' + '.join(parts) + ']'


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


# note: see codeproject link for more comprehensive set of x86-64 registers
al = Register(0b000, 'al', 8)  # 8-bit registers (low-byte)
cl = Register(0b001, 'cl', 8)  # r8(/r)
dl = Register(0b010, 'dl', 8)
bl = Register(0b011, 'bl', 8)
ah = Register(0b100, 'ah', 8)  # (high-byte)
ch = Register(0b101, 'ch', 8)
dh = Register(0b110, 'dh', 8)
bh = Register(0b111, 'bh', 8)

ax = Register(0b000, 'ax', 16)  # 16-bit registers
cx = Register(0b001, 'cx', 16)  # r16(/r)
dx = Register(0b010, 'dx', 16)
bx = Register(0b011, 'bx', 16)
sp = Register(0b100, 'sp', 16)
bp = Register(0b101, 'bp', 16)
si = Register(0b110, 'si', 16)
di = Register(0b111, 'di', 16)

eax = Register(0b000, 'eax', 32)  # 32-bit registers   Accumulator (i/o, math, irq, ...)
ecx = Register(0b001, 'ecx', 32)  # r32(/r)            Counter (loop counter and shifts) 
edx = Register(0b010, 'edx', 32)  #                    Data (i/o, math, irq, ...)
ebx = Register(0b011, 'ebx', 32)  #                    Base (base memory addresses)
esp = Register(0b100, 'esp', 32)  #                    Stack pointer
ebp = Register(0b101, 'ebp', 32)  #                    Stack base pointer
esi = Register(0b110, 'esi', 32)  #                    Source index
edi = Register(0b111, 'edi', 32)  #                    Destination index

rax = Register(0b000, 'rax', 64)  # 64-bit registers
rcx = Register(0b001, 'rcx', 64)  # r64(/r)
rdx = Register(0b010, 'rdx', 64)
rbx = Register(0b011, 'rbx', 64)
rsp = Register(0b100, 'rsp', 64)
rbp = Register(0b101, 'rbp', 64)
rsi = Register(0b110, 'rsi', 64)
rdi = Register(0b111, 'rdi', 64)

r8b  = Register(0b1000, 'r8b',  8)  # 64-bit registers, lower byte
r9b  = Register(0b1001, 'r9b',  8)
r10b = Register(0b1010, 'r10b', 8)
r11b = Register(0b1011, 'r11b', 8)
r12b = Register(0b1100, 'r12b', 8)
r13b = Register(0b1101, 'r13b', 8)
r14b = Register(0b1110, 'r14b', 8)
r15b = Register(0b1111, 'r15b', 8)

r8w  = Register(0b1000, 'r8w',  16)  # 64-bit registers, lower word
r9w  = Register(0b1001, 'r9w',  16)
r10w = Register(0b1010, 'r10w', 16)
r11w = Register(0b1011, 'r11w', 16)
r12w = Register(0b1100, 'r12w', 16)
r13w = Register(0b1101, 'r13w', 16)
r14w = Register(0b1110, 'r14w', 16)
r15w = Register(0b1111, 'r15w', 16)

r8d  = Register(0b1000, 'r8d',  32)  # 64-bit registers, lower doubleword
r9d  = Register(0b1001, 'r9d',  32)
r10d = Register(0b1010, 'r10d', 32)
r11d = Register(0b1011, 'r11d', 32)
r12d = Register(0b1100, 'r12d', 32)
r13d = Register(0b1101, 'r13d', 32)
r14d = Register(0b1110, 'r14d', 32)
r15d = Register(0b1111, 'r15d', 32)

r8  = Register(0b1000, 'r8',  64)
r9  = Register(0b1001, 'r9',  64)
r10 = Register(0b1010, 'r10', 64)
r11 = Register(0b1011, 'r11', 64)
r12 = Register(0b1100, 'r12', 64)
r13 = Register(0b1101, 'r13', 64)
r14 = Register(0b1110, 'r14', 64)
r15 = Register(0b1111, 'r15', 64)

mm0 = Register(0b000, 'mm0', 64)  # mm(/r)
mm1 = Register(0b001, 'mm1', 64)
mm2 = Register(0b010, 'mm2', 64)
mm3 = Register(0b011, 'mm3', 64)
mm4 = Register(0b100, 'mm4', 64)
mm5 = Register(0b101, 'mm5', 64)
mm6 = Register(0b110, 'mm6', 64)
mm7 = Register(0b111, 'mm7', 64)

xmm0 = Register(0b000, 'xmm0', 128)  # xmm(/r)
xmm1 = Register(0b001, 'xmm1', 128)
xmm2 = Register(0b010, 'xmm2', 128)
xmm3 = Register(0b011, 'xmm3', 128)
xmm4 = Register(0b100, 'xmm4', 128)
xmm5 = Register(0b101, 'xmm5', 128)
xmm6 = Register(0b110, 'xmm6', 128)
xmm7 = Register(0b111, 'xmm7', 128)


# Lists of registers used as arguments in standard calling conventions
if ARCH == 32:
    # 32-bit stdcall and cdecl push all arguments onto stack
    argi = []
    argf = []
elif ARCH == 64:
    if sys.platform == 'win32':
        argi = [rcx, rdx, r8, r9]
        argf = [xmm0, xmm1, xmm2, xmm3]
    else:
        argi = [rdi, rsi, rdx, rcx, r8, r9]
        argf = [xmm0, xmm1, xmm2, xmm3, xmm4, xmm5, xmm6, xmm7]
        


#   Misc. utilities required by instructions
#------------------------------------------------


class Code(object):
    """
    Represents partially compiled machine code with a table of unresolved
    expression replacements.
    
    Code instances can be compiled to a complete machine code string once all
    expression values can be determined.
    """
    def __init__(self, code):
        self.code = code
        self.replacements = {}
        
    def replace(self, index, expr, packing):
        """
        Add a new replacement starting at *index*. 
        
        When this Code is compiled, the value of *expr* will be evaluated,
        packed with *packing* and written into the code at *index*. The expression
        is evaluated using the program's symbols as local variables.
        """
        self.replacements[index] = (expr, packing)
        
    def __len__(self):
        return len(self.code)
    
    def compile(self, symbols):
        code = self.code
        for i,repl in self.replacements.items():
            expr, packing = repl
            val = eval(expr, symbols)
            val = struct.pack(packing, val)
            code = code[:i] + val + code[i+len(val):]
        return code


def label(name):
    """
    Create a label referencing a location in the code.
    
    The name of this label may be used by other assembler calls that require
    a code pointer.
    """
    return Label(name)

class Label(object):
    def __init__(self, name):
        self.name = name
        
    def __len__(self):
        return 0
        
    def compile(self, symbols):
        return ''



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


def get_instruction_mode(sig, modes):
    """For a given signature of operand types, return an appropriate 
    instruction mode.
    """
    orig_sig = sig
    if sig in modes:
        return sig
    
    #if sig[:2] == ('r', 'r'):
        #sig = ('r', 'r/m') + sig[2:]
        #if sig in modes:
            #return sig
    
    #if sig[-1].startswith('imm'):
        #size = int(sig[-1][3:])
        #while size < 64:
            #size *= 2
            #sig = sig[:-1] + ('imm%d' % size,)
            #if sig in modes:
                #return sig
    #sig = orig_sig
    
    # Check each instruction mode one at a time to see whether it is compatible
    # with supplied arguments.
    for mode in modes:
        print "check:", sig, mode
        if len(mode) != len(sig):
            continue
        usemode = True
        for i in range(len(mode)):
            sbits = sig[i].lstrip('ir/m')
            stype = sig[i][:-len(sbits)]
            mbits = mode[i].lstrip('ir/m')
            mtype = mode[i][:-len(mbits)]
            mbits = int(mbits)
            sbits = int(sbits)
            
            if mtype == 'r':
                if stype != 'r' or mbits != sbits:
                    usemode = False
                    break
            elif mtype == 'r/m':
                if stype not in ('r', 'r/m') or mbits != sbits:
                    usemode = False
                    break
            elif mtype == 'imm':
                if stype != 'imm' or mbits < sbits:
                    usemode = False
                    break
            else:
                raise Exception("operand type %s" % mtype)
        
        if usemode:
            return mode
    
    
    raise TypeError('Argument types not accepted for this instruction: %s' 
                    % str(orig_sig))


def instruction(modes, operand_enc, *args):
    """Generic function for encoding an instruction given information from
    the intel reference and the operands.
    """
    # Determine signature of arguments provided
    sig = []
    clean_args = []
    for arg in args:
        if isinstance(arg, list):
            arg = interpret(arg)
            
        if isinstance(arg, Register):
            sig.append('r%d' % arg.bits)
        elif isinstance(arg, Pointer):
            sig.append('r/m%d' % arg.bits)
        elif isinstance(arg, int):
            arg = pack_int(arg, int8=True)
            sig.append('imm%d' % (8*len(arg)))
        elif isinstance(arg, str):
            sig.append('imm%d' % len(arg))
        else:
            raise TypeError("Invalid argument type %s." % type(arg))
        clean_args.append(arg)
    sig = tuple(sig)

    # Match this to an appropriate function signature
    use_sig = get_instruction_mode(sig, modes)
    mode = modes[use_sig]
    
    # Make sure this signature is supported for this architecture
    if ARCH == 64 and mode[2] is False:
        raise TypeError('Argument types not accepted in 64-bit mode: %s' 
                        % sig)
    if ARCH == 32 and mode[3] is False:
        raise TypeError('Argument types not accepted in 32-bit mode: %s' 
                        % sig)

    # Start encoding instruction
    # extract encoding for opcode
    prefixes = []
    rex_byt = 0
    
    # parse opcode string (todo: these should be pre-parsed)
    op_parts = mode[0].split(' ')
    rexw = False
    if op_parts[:2] == ['REX.W', '+']:
        op_parts = op_parts[2:]
        rexw = True
    
    opcode_s = op_parts[0]
    if '+' in opcode_s:
        opcode_s = opcode_s.partition('+')[0]
        reg_in_opcode = True
    else:
        reg_in_opcode = False
    
    # assemble initial opcode
    opcode = ''
    for i in range(0, len(opcode_s), 2):
        opcode += chr(int(opcode_s[i:i+2], 16))
    
    # check for opcode extension
    opcode_ext = None
    if len(op_parts) > 1:
        if op_parts[1] == '/r':
            pass  # handled by operand encoding
        elif op_parts[1][0] == '/':
            opcode_ext = int(op_parts[1][1])

    # initialize modrm and imm 
    reg = opcode_ext
    rm = None
    imm = None
    
    # encode operands
    for i,arg in enumerate(clean_args):
        # look up encoding for this operand
        enc = operand_enc[mode[1]][i]
        if enc == 'opcode +rd (r)':
            opcode = opcode[:-1] + chr(ord(opcode[-1]) | arg.val)
            if arg.rex:
                rex_byt = rex_byt | rex.b
            if arg.bits == 16:
                prefixes.append('\x66')
        elif enc.startswith('ModRM:r/m'):
            rm = arg
            if arg.bits == 16:
                prefixes.append('\x66')
            if isinstance(arg, Pointer):
                addrpfx = arg.prefix
                if addrpfx != '':
                    prefixes.append(addrpfx)  # adds 0x67 prefix if needed
        elif enc.startswith('ModRM:reg'):
            reg = arg
        elif enc.startswith('imm'):
            immsize = int(use_sig[i][3:])
            opsize = 8 * len(arg)
            assert opsize <= immsize
            imm = arg + '\0'*((immsize-opsize)//8)
        else:
            raise RuntimeError("Invalid operand encoding: %s" % enc)
        
    operands = []
    if reg is not None:
        modrm = ModRmSib(reg, rm)
        operands.append(modrm.code[1])
        rex_byt |= modrm.rex
        
    if imm is not None:
        operands.append(imm)
    
    if rexw:
        rex_byt |= rex.w
    
    if rex_byt == 0:
        rex_byt = ''
    else:
        rex_byt = chr(rex_byt)
    
    return ''.join(prefixes) + rex_byt + opcode + ''.join(operands)

    

#   Procedure management instructions
#----------------------------------------


def push(*args):
    """Push register, memory, or immediate onto the stack.
    
    Opcode: 50+rd
    Push value stored in reg onto the stack.
    """
    modes = {
        ('r/m16',): ['ff /6', 'm', True, True],
        ('r/m32',): ['ff /6', 'm', False, True],
        ('r/m64',): ['ff /6', 'm', True, False],
        ('r16',): ['50+rw', 'o', True, True],
        ('r32',): ['50+rd', 'o', False, True],
        ('r64',): ['50+rd', 'o', True, False],
        ('imm8',): ['6a ib', 'i', True, True],
        #('imm16',): ['68 iw', 'i', True, True],  # gnu as does not use this
        ('imm32',): ['68 id', 'i', True, True],
    }
    
    operand_enc = {
        'm': ['ModRM:r/m (r)'],
        'o': ['opcode +rd (r)'],
        'i': ['imm8/16/32'],
    }
    
    return instruction(modes, operand_enc, *args)
            
    
#def push(*args):
    #"""Push register, memory, or immediate onto the stack.
    
    #Opcode: 50+rd
    #Push value stored in reg onto the stack.
    #"""
    #if isinstance(op, Register):
        ## don't support segment registers for now.
        ##shortcuts = {
            ##cs: '\x0e',
            ##ss: '\x16',
            ##ds: '\x1e',
            ##es: '\x06',
            ##fs: '\x0f\xa0',
            ##gs: '\x0f\xa8'}
        ##if op in shortcuts:
            ##return shortcuts[op]
        #if ARCH == 64 and op.bits == 32:
            #raise TypeError("Cannot push 32-bit register in 64-bit mode.")
        #elif ARCH == 32 and op.bits == 64:
            #raise TypeError("Cannot push 64-bit register in 32-bit mode.")
        #return chr(0x50 | op.val)
    #elif isinstance(op, Pointer):
        #return '\xff' + mod_reg_rm(0x6, op)
    #elif isinstance(op, int):
        #imm = pack_int(op, int8=True)
        #if len(imm) == 1:
            #return '\x6a' + imm
        #else:
            #return '\x68' + imm

def pop(reg):
    """ POP REG
    
    Opcode: 50+rd
    Push value stored in reg onto the stack.
    """
    return chr(0x58 | reg.val)

def ret(pop=0):
    """ RET
    
    Return; pop a value from the stack and branch to that address.
    Optionally, extra values may be popped from the stack after the return 
    address.
    """
    if pop > 0:
        return '\xc2' + struct.pack('<h', pop)
    else:
        return '\xc3'

def leave():
    """ LEAVE
    
    High-level procedure exit.
    Equivalent to::
    
       mov(esp, ebp)
       pop(ebp)
    """
    return '\xc9'


def call(*args):
    """Saves procedure linking information on the stack and branches to the 
    called procedure specified using the target operand. 
    
    The target operand specifies the address of the first instruction in the 
    called procedure. The operand can be an immediate value, a general-purpose 
    register, or a memory location.
    """
    if len(args) != 1:
        raise TypeError("call requires exactly 1 argument")
    if isinstance(args[0], int):
        # Manually generate relative call
        return '\xe8' + struct.pack('i', args[0]-5)
    elif isinstance(args[0], str):
        # Generate relative call to label
        code = Code('\xe8' + '\x00\x00\x00\x00')
        code.replace(1, "%s - next_instr_addr" % args[0], 'i')
        return code
    else:
        # generate absolute call
        modes = {
            #('rel16',): ['e8', 'm', False, True],
            #('rel32',): ['e8', 'm', True, True],
            ('r/m16',): ['ff /2', 'm', False, True],
            ('r/m32',): ['ff /2', 'm', False, True],
            ('r/m64',): ['ff /2', 'm', True, False],
        }
        
        operand_enc = {
            'm': ['ModRM:r/m (r)'],
        }
        
        return instruction(modes, operand_enc, *args)

#def call(op):
    #"""CALL op
    
    #Push EIP onto stack and branch to address specified in *op*.
    
    #If op is a signed int (16 or 32 bits), this generates a near, relative call
    #where the displacement given in op is relative to the next instruction.
    
    #If op is a Register then this generates a near, absolute call where the 
    #absolute offset is read from the register.
    #"""
    #if isinstance(op, Register):
        #return call_abs(op)
    #elif isinstance(op, int):
        #return call_rel(op)
    #else:
        #raise TypeError("call argument must be int or Register")

#def call_abs(reg):
    #"""CALL (absolute) 
    
    #Opcode: 0xff /2
    
    #"""
    ## note: opcode extension 2 is encoded in bits 3-5 of the next byte
    ##       (this is the reg field of mod_reg_r/m)
    ##       the mod bits 00 and r/m bits 101 indicate a 32-bit displacement follows.
    #if reg.bits == 32:
        #return '\xff' + mod_reg_rm('dir', 0b010, reg)
    #else:
        #return '\xff' + mod_reg_rm('dir', 0b010, reg)
        
        
#def call_rel(addr):
    #"""CALL (relative) 
    
    #Opcode: 0xe8 cd  (cd indicates 4-byte argument follows opcode)
    
    #Note: addr is signed int relative to _next_ instruction pointer 
          #(which should be current instruction pointer + 5, since this is a
          #5 byte instruction).
    #"""
    ## Note: there is no 64-bit relative call.
    #return '\xe8' + struct.pack('i', addr-5)



#   Data moving instructions
#----------------------------------------

def mov(a, b):
    a = interpret(a)
    b = interpret(b)
    
    if isinstance(a, Register):
        if isinstance(b, Register):
            # Copy register to register
            return mov_rm_r(a, b)
        elif isinstance(b, (int, long)):
            # Copy immediate value to register
            return mov_r_imm(a, b)
        elif isinstance(b, Pointer):
            # Copy memory to register
            return mov_r_rm(a, b)
        else:
            raise TypeError("mov second argument must be Register, immediate, "
                            "or Pointer")
    elif isinstance(a, Pointer):
        if isinstance(b, Register):
            # Copy register to memory
            return mov_rm_r(a, b)
        elif isinstance(b, (int, long)):
            # Copy immediate value to memory
            raise NotImplementedError("mov imm=>addr not implemented")
        else:
            raise TypeError("mov second argument must be Register or immediate"
                            " when first argument is Pointer")
    else:
        raise TypeError("mov first argument must be Register or Pointer")

def mov_r_rm(r, rm, opcode='\x8b'):
    """ MOV R,R/M
    
    Opcode: 8b /r (uses mod_reg_r/m byte)
    Op/En: RM (REG is dest; R/M is source)
    Move from R/M to R
    """
    # Note: as with many opcodes, flipping bit 6 swaps the R->RM order
    #       yielding 0x89 (mov_rm_r)
    inst = ""
    if r.bits == 64:
        inst += rex.w
    elif r.bits != 32:
        raise NotImplementedError('register bit size %d not supported' % r.bits)
    inst += opcode
    
    if isinstance(rm, Register):
        # direct register-register copy
        inst += mod_reg_rm('dir', r, rm)
    elif isinstance(rm, Pointer):
        # memory to register copy
        inst += rm.modrm_sib(r)
        
    return inst

def mov_rm_r(rm, r):
    """ MOV R/M,R
    
    Opcode: 89 /r
    Move from R to R/M
    """
    return mov_r_rm(r, rm, opcode='\x89')

#def mov_rm32_r32(rm, r):
    #""" MOV R/M,R
    
    #Opcode: 89 /r (uses mod_reg_r/m byte)
    #Op/En: MR (R/M is dest; REG is source)
    #Move from R to R/M 
    #"""
    ## Note: as with many opcodes, flipping bit 6 swaps the R->RM order
    ##       yielding 0x8B (mov_r_rm)
    #return '\x89' + mod_reg_rm('dir', r, rm)

#def mov_rm64_r64(rm, r):
    #""" MOV R/M,R
    
    #Opcode: 89 /r (uses mod_reg_r/m byte)
    #Op/En: MR (R/M is dest; REG is source)
    #Move from R to R/M 
    #"""
    ## Note: as with many opcodes, flipping bit 6 swaps the R->RM order
    ##       yielding 0x8B (mov_r_rm)
    #return rex.w + '\x89' + mod_reg_rm('dir', r, rm)

def mov_r_imm(r, val, fmt=None):
    """ MOV REG,VAL
    
    Opcode(32): b8+r
    Opcode(64): REX.W + b8 + rd io
    Move VAL (32/64 bit immediate as unsigned int) to REG.
    """
    if r.bits == 32:
        fmt = '<I' if fmt is None else fmt
        return chr(0xb8 | r.val) + struct.pack(fmt, val)
    elif r.bits == 64:
        fmt = '<Q' if fmt is None else fmt
        return rex.w + chr(0xb8 | r.val) + struct.pack(fmt, val)
    else:
        raise NotImplementedError('register bit size %d not supported' % r.bits)

def movsd(dst, src):
    """
    MOVSD xmm1, xmm2/m64
    Opcode (mem=>xmm): f2 0f 10 /r
    
    MOVSD xmm2/m64, xmm1
    Opcode (xmm=>mem): f2 0f 11 /r
    
    Move scalar double-precision float
    """
    modrm = ModRmSib(dst, src)
    if modrm.argtypes in ('rr', 'rm'):
        assert dst.bits == 128
        return '\xf2\x0f\x10' + modrm.code
    else:
        assert src.bits == 128
        return '\xf2\x0f\x11' + modrm.code
        


#   Arithmetic instructions
#----------------------------------------


def add(dst, src):
    """Adds the destination operand (first operand) and the source operand 
    (second operand) and then stores the result in the destination operand. 
    
    The destination operand can be a register or a memory location; the source
    operand can be an immediate, a register, or a memory location. (However, 
    two memory operands cannot be used in one instruction.) When an immediate 
    value is used as an operand, it is sign-extended to the length of the 
    destination operand format.
    """
    modes = collections.OrderedDict([
        (('r/m8', 'imm8'),   ['80 /0', 'mi', True, True]),
        (('r/m16', 'imm16'), ['81 /0', 'mi', True, True]),
        (('r/m32', 'imm32'), ['81 /0', 'mi', True, True]),
        (('r/m64', 'imm32'), ['REX.W + 81 /0', 'mi', True, False]),
        
        (('r/m16', 'imm8'),  ['83 /0', 'mi', True, True]),
        (('r/m32', 'imm8'),  ['83 /0', 'mi', True, True]),
        (('r/m64', 'imm8'),  ['REX.W + 83 /0', 'mi', True, False]),        
        
        (('r/m8', 'r8'),   ['00 /r', 'mr', True, True]),
        (('r/m16', 'r16'), ['01 /r', 'mr', True, True]),
        (('r/m32', 'r32'), ['01 /r', 'mr', True, True]),
        (('r/m64', 'r64'), ['REX.W + 01 /r', 'mr', True, False]),
        
        (('r8', 'r/m8'),   ['02 /r', 'rm', True, True]),
        (('r16', 'r/m16'),   ['03 /r', 'rm', True, True]),
        (('r32', 'r/m32'),   ['03 /r', 'rm', True, True]),
        (('r64', 'r/m64'),   ['REX.W + 03 /r', 'rm', True, False]),
        
    ])
    
    operand_enc = {
        'mi': ['ModRM:r/m (r,w)', 'imm8/16/32'],
        'mr': ['ModRM:r/m (r,w)', 'ModRM:reg (r)'],
        'rm': ['ModRM:reg (r,w)', 'ModRM:r/m (r)'],
    }
    
    return instruction(modes, operand_enc, dst, src)
    


#def add(dst, src):
    #"""Perform integer addition of dst + src and store the result in dst.
    #"""
    #dst = interpret(dst)
    #src = interpret(src)
    
    #if isinstance(dst, Pointer):
        #if isinstance(src, Register):
            #return add_ptr_reg(dst, src)
        #elif isinstance(src, (int, long)):
            #return add_ptr_imm(dst, src)
        #else:
            #raise TypeError('src must be Register or int if dst is Pointer')
    #elif isinstance(dst, Register):
        #if isinstance(src, Register):
            #return add_reg_reg(dst, src)
        #elif isinstance(src, Pointer):
            #return add_reg_ptr(dst, src)
        #elif isinstance(src, (int, long)):
            #return add_reg_imm(dst, src)
        #else:
            #raise TypeError('src must be Register, Pointer, or int')
    #else:
        #raise TypeError('dst must be Register or Pointer')

#def add_reg_imm(reg, val):
    #"""ADD REG, imm32
    
    #Opcode: REX.W 0x81 /0 id
    #"""
    #return rex.w + '\x81' + mod_reg_rm('dir', 0x0, reg) + struct.pack('i', val)
    
#def add_reg_reg(reg1, reg2):
    #""" ADD r/m64 r64
    
    #Opcode: REX.W 0x01 /r
    #"""
    #return rex.w + '\x01' + mod_reg_rm('dir', reg2, reg1)

#def add_reg_ptr(reg, addr):
    #modrm = ModRmSib(reg, addr)
    #return '\x03' + modrm.code

#def add_ptr_imm(addr, val):
    #return '\x81' + addr.modrm_sib(0x0) + struct.pack('i', val)
    
#def add_ptr_reg(addr, reg):
    #modrm = ModRmSib(reg, addr)
    #return '\x01' + modrm.code

def lea(a, b):
    """ LEA r,[base+offset+disp]
    
    Load effective address.
    Opcode: 8d /r (uses mod_reg_r/m byte)
    Op/En: RM (REG is dest; R/M is source)
    """
    modrm = ModRmSib(a, b)
    assert modrm.argtypes == 'rm'
    prefix = ''
    if ARCH == 64:
        if modrm.argbits[0] == 16:
            prefix += '\x66'
        if modrm.argbits[1] == 32:
            prefix += '\x67'
        if modrm.argbits[0] == 64:
            prefix += rex.w
    else:
        raise NotImplementedError("lea only implemented for 64bit")
    return prefix + '\x8d' + modrm.code
    #return '\x8d' + mod_reg_rm('ind8', r, sib) + mk_sib(1, offset, base) + chr(disp)
    

def dec(op):
    """ DEC r/m
    
    Decrement r/m by 1
    Opcode: ff /1
    """
    modrm = ModRmSib(0x1, op)
    if modrm.bits == 64:
        return rex.w + '\xff' + modrm.code
    else:
        return '\xff' + modrm.code

def inc(op):
    """ INC r/m
    
    Increment r/m by 1
    Opcode: ff /0
    """
    modrm = ModRmSib(0x0, op)
    if modrm.bits == 64:
        return rex.w + '\xff' + modrm.code
    else:
        return '\xff' + modrm.code

def imul(a, b):
    """ IMUL reg, r/m
    
    Signed integer multiply reg * r/m and store in reg
    Opcode: 0f af /r
    """
    modrm = ModRmSib(a, b)
    if modrm.bits == 64:
        return rex.w + '\x0f\xaf' + modrm.code
    else:
        return '\x0f\xaf' + modrm.code

def idiv(op):
    """ IDIV r/m
    
    Signed integer divide *ax / r/m and store in *ax
    Opcode: f7 /7
    """
    modrm = ModRmSib(0x7, op)
    if modrm.bits == 64:
        return rex.w + '\xf7' + modrm.code
    else:
        return '\xf7' + modrm.code



#   Testing instructions
#----------------------------------------


def cmp(a, b):
    #if isinstance(b, (Register, Pointer)):
        #modrm = ModRmSib(a, b)
        #if modrm.argtypes in ('rm', 'rr'):
            #opcode = '\x3b'
        #elif modrm.argtypes == 'mr':
            #opcode = '\x39'
        #else:
            #raise NotImplementedError()
        #imm = ''
    #else:
        #modrm = ModRmSib(0x7, a)
        #opcode = '\x81'
        #imm = struct.pack('i', b)
    
    #prefix = ''
    #if modrm.bits == 64:
        #prefix += rex.w
    
    #return prefix + opcode + modrm.code + imm
    inst = Instruction(a, b)
    if inst.argtypes in ('rm', 'rr'):
        inst.opcode = '\x3b'
    elif inst.argtypes == 'mr':
        inst.opcode = '\x39'
    elif inst.argtypes in ('mi', 'ri'):
        inst.opcode = '\x81'
        inst.ext = 0x7
        inst.imm_fmt = 'i'
    return inst.code

def test(a, b):
    """Computes the bit-wise logical AND of first operand (source 1 operand) 
    and the second operand (source 2 operand) and sets the SF, ZF, and PF 
    status flags according to the result.
    """
    if isinstance(b, (Register, Pointer)):
        modrm = ModRmSib(a, b)
        opcode = '\x85'
        imm = ''
    else:
        modrm = ModRmSib(0x0, a)
        opcode = '\xf7'
        imm = struct.pack('i', b)
    
    prefix = ''
    if modrm.bits == 64:
        prefix += rex.w
    
    return prefix + opcode + modrm.code + imm
    



#   Branching instructions
#----------------------------------------

def jmp(addr):
    if isinstance(addr, Register):
        return jmp_abs(addr)
    elif isinstance(addr, (int, str)):
        return jmp_rel(addr)
    else:
        raise TypeError("jmp accepts Register (absolute), integer, or label (relative).")

def jmp_rel(addr, opcode='\xe9'):
    """JMP rel32 (relative)
    
    Opcode: 0xe9 cd 
    """
    if isinstance(addr, str):
        code = Code(opcode + '\x00\x00\x00\x00')
        code.replace(len(opcode), "%s - next_instr_addr" % addr, 'i')
        return code
    elif isinstance(addr, int):
        return opcode + struct.pack('i', addr - (len(opcode)+4))

def jmp_abs(reg):
    """JMP r/m32 (absolute)
    
    Opcode: 0xff /4
    """
    return '\xff' + mod_reg_rm('dir', 0x4, reg)

def ja(addr):
    """Jump near if above (CF=0 and ZF=0)."""
    return jmp_rel(addr, opcode='\x0f\x87')
    
def jae(addr):
    """Jump near if above or equal (CF=0)."""
    return jmp_rel(addr, opcode='\x0f\x83')
    
def jb(addr):
    """Jump near if below (CF=1)."""
    return jmp_rel(addr, opcode='\x0f\x82')

def jbe(addr):
    """Jump near if below or equal (CF=1 or ZF=1)."""
    return jmp_rel(addr, opcode='\x0f\x86')

def jc(addr):
    """Jump near if carry (CF=1)."""
    return jmp_rel(addr, opcode='\x0f\x82')

def je(addr):
    """Jump near if equal (ZF=1)."""
    return jmp_rel(addr, opcode='\x0f\x84')

def jz(addr):
    """Jump near if 0 (ZF=1)."""
    return jmp_rel(addr, opcode='\x0f\x84')

def jg(addr):
    """Jump near if greater (ZF=0 and SF=OF)."""
    return jmp_rel(addr, opcode='\x0f\x8f')

def jge(addr):
    """Jump near if greater or equal (SF=OF)."""
    return jmp_rel(addr, opcode='\x0f\x8d')

def jl(addr):
    """Jump near if less (SF≠ OF)."""
    return jmp_rel(addr, opcode='\x0f\x8c')

def jle(addr):
    """Jump near if less or equal (ZF=1 or SF≠ OF)."""
    return jmp_rel(addr, opcode='\x0f\x8e')

def jna(addr):
    """Jump near if not above (CF=1 or ZF=1)."""
    return jmp_rel(addr, opcode='\x0f\x86')

def jnae(addr):
    """Jump near if not above or equal (CF=1)."""
    return jmp_rel(addr, opcode='\x0f\x82')

def jnb(addr):
    """Jump near if not below (CF=0)."""
    return jmp_rel(addr, opcode='\x0f\x83')

def jnbe(addr):
    """Jump near if not below or equal (CF=0 and ZF=0)."""
    return jmp_rel(addr, opcode='\x0f\x87')

def jnc(addr):
    """Jump near if not carry (CF=0)."""
    return jmp_rel(addr, opcode='\x0f\x83')

def jne(addr):
    """Jump near if not equal (ZF=0)."""
    return jmp_rel(addr, opcode='\x0f\x85')

def jng(addr):
    """Jump near if not greater (ZF=1 or SF≠ OF)."""
    return jmp_rel(addr, opcode='\x0f\x8e')

def jnge(addr):
    """Jump near if not greater or equal (SF ≠ OF)."""
    return jmp_rel(addr, opcode='\x0f\x8c')

def jnl(addr):
    """Jump near if not less (SF=OF)."""
    return jmp_rel(addr, opcode='\x0f\x8d')

def jnle(addr):
    """Jump near if not less or equal (ZF=0 and SF=OF)."""
    return jmp_rel(addr, opcode='\x0f\x8f')

def jno(addr):
    """Jump near if not overflow (OF=0)."""
    return jmp_rel(addr, opcode='\x0f\x81')

def jnp(addr):
    """Jump near if not parity (PF=0)."""
    return jmp_rel(addr, opcode='\x0f\x8b')

def jns(addr):
    """Jump near if not sign (SF=0)."""
    return jmp_rel(addr, opcode='\x0f\x89')

def jnz(addr):
    """Jump near if not zero (ZF=0)."""
    return jmp_rel(addr, opcode='\x0f\x85')

def jo(addr):
    """Jump near if overflow (OF=1)."""
    return jmp_rel(addr, opcode='\x0f\x80')

def jp(addr):
    """Jump near if parity (PF=1)."""
    return jmp_rel(addr, opcode='\x0f\x8a')

def jpe(addr):
    """Jump near if parity even (PF=1)."""
    return jmp_rel(addr, opcode='\x0f\x8a')

def jpo(addr):
    """Jump near if parity odd (PF=0)."""
    return jmp_rel(addr, opcode='\x0f\x8b')

def js(addr):
    """Jump near if sign (SF=1)."""
    return jmp_rel(addr, opcode='\x0f\x88')


#   OS instructions
#----------------------------------------


def int_(code):
    """INT code
    
    Call to interrupt. Code is 1 byte.
    
    Common interrupt codes:
    0x80 = OS
    """
    return '\xcd' + chr(code)

def syscall():
    return '\x0f\x05'



def phex(code):
    if not isinstance(code, list):
        code = [code]
    for instr in code:
        for c in instr:
            print '%02x' % ord(c),
        print ''

def pbin(code):
    if not isinstance(code, list):
        code = [code]
    for instr in code:
        for c in instr:
            print format(ord(c), '08b'),
        print ''

def run_as(asm):
    """ Use gnu as and objdump to show ideal compilation of *asm*.
    
    This prepends the given code with ".intel_syntax noprefix\n" 
    """
    #asm = """
    #.section .text
    #.globl _start
    #.align 4
    #_start:
    #""" + asm + '\n'
    asm = ".intel_syntax noprefix\n" + asm + "\n"
    #print asm
    fname = tempfile.mktemp('.s')
    open(fname, 'w').write(asm)
    cmd = 'as {file} -o {file}.o && objdump -d {file}.o; rm -f {file} {file}.o'.format(file=fname)
    #print cmd
    out = subprocess.check_output(cmd, shell=True).split('\n')
    for i,line in enumerate(out):
        if "Disassembly of section .text:" in line:
            return out[i+3:]
    print "--- code: ---"
    print asm
    print "-------------"
    exc = Exception("Error running 'as' or 'objdump' (see above).")
    exc.asm = asm
    raise exc

def as_code(asm):
    """Return machine code string for *asm* using gnu as and objdump.
    """
    code = b''
    for line in run_as(asm):
        if line.strip() == '':
            continue
        m = re.match(r'\s*[a-f0-9]+:\s+(([a-f0-9][a-f0-9]\s+)+)', line)
        if m is None:
            raise Exception("Can't parse objdump output: \"%s\"" % line)
        byts = re.split(r'\s+', m.groups()[0])
        for byt in byts:
            if byt == '':
                continue
            code += bytes(chr(eval('0x'+byt)))
    return code



class CodePage(object):
    """
    Encapsulates a block of executable mapped memory to which a sequence of
    asm commands are compiled and written. 
    
    The memory page(s) may contain multiple functions; use get_function(label)
    to create functions beginning at a specific location in the code.
    """
    def __init__(self, asm):
        self.labels = {}
        self.asm = asm
        code_size = len(self)
        #pagesize = os.sysconf("SC_PAGESIZE")
        
        # Create a memory-mapped page with execute privileges
        PROT_NONE = 0
        PROT_READ = 1
        PROT_WRITE = 2
        PROT_EXEC = 4
        self.page = mmap.mmap(-1, code_size, prot=PROT_READ|PROT_WRITE|PROT_EXEC)

        # get the page address
        buf = (ctypes.c_char * code_size).from_buffer(self.page)
        self.page_addr = ctypes.addressof(buf)
        
        # Compile machine code and write to the page.
        code = self.compile(asm)
        assert len(code) <= len(self.page)
        self.page.write(code)
        
    def __len__(self):
        return sum(map(len, self.asm))

    def get_function(self, label=None):
        addr = self.page_addr
        if label is not None:
            addr += self.labels[label]
        
        # Turn this into a callable function
        f = ctypes.CFUNCTYPE(None)(addr)
        f.page = self  # Make sure page stays alive as long as function pointer!
        return f

    def compile(self, asm):
        ptr = self.page_addr
        # First locate all labels
        for cmd in asm:
            ptr += len(cmd)
            if isinstance(cmd, Label):
                self.labels[cmd.name] = ptr
                
        # now compile
        symbols = self.labels.copy()
        code = ''
        for cmd in asm:
            if isinstance(cmd, str):
                code += cmd
            else:
                # Make some special symbols available when resolving
                # expressions:
                symbols['instr_addr'] = self.page_addr + len(code)
                symbols['next_instr_addr'] = symbols['instr_addr'] + len(cmd)
                
                code += cmd.compile(symbols)
                
        return code
        
        
def mkfunction(code):
    page = CodePage(code)
    return page.get_function()

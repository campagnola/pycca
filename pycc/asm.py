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
rex.w = chr(0b01001000)  # 64-bit operands
rex.r = chr(0b01000100)  # Extension of ModR/M reg field to 4 bits
rex.x = chr(0b01000010)  # Extension of SIB index field to 4 bits
rex.b = chr(0b01000001)  # Extension of ModR/M r/m field, SIB base field, or 
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
    if rm == 'sib':
        rm = 0b100  # Indicates SIB byte usage when used as R/M field in ModR/M
    elif rm == 'disp':
        rm = 0b101  # Indicates displacement value without register offset when used
                    # as R/M field in ModR/M

    return chr(mod_vals[mod] | reg << 3 | rm)



#     SIB byte
#-----------------------------------------

def mk_sib(byts, offset, base):
    """Generate SIB byte
    
    byts : 0, 1, 2, or 3
    offset : Register
    base : register
    
    Address is computed as [base] + [offset] * 2^byts
    When base is [ebp], add disp32.
    When offset is [esp], no offset is applied.
    """
    return chr(byts << 6 | offset << 3 | base)


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
        
        if self.argtypes in ('rr', 'xr'):
            self.code = mod_reg_rm('dir', a, b)
        elif self.argtypes == 'mr':
            self.code = a.modrm_sib(b)
        elif self.argtypes in ('rm', 'xm'):
            self.code = b.modrm_sib(a)
        else:
            raise TypeError('Invalid argument types: %s, %s' % (type(a), type(b)))

        if hasattr(a, 'bits'):
            self.argbits = (a.bits, b.bits)
            self.bits = max(self.argbits)
        else:
            self.argbits = (None, b.bits)
            self.bits = b.bits


def instruction(opcode, dest=None, source=None):
    """Automatically generate complete instructions.
    
    opcode: the base opcode or a dictionary of {argtypes: opcode} pairs to 
    select from bassed on the source and dest arg types. May also be a tuple
    (opcode, extension) or a dictionary of tuples.
    """
    
    



#   Register definitions
#----------------------------------------

class Register(int):
    """A float holding information about its source.
    """
    def __new__(cls, val, name, bits):
        f = int.__new__(cls, val)
        f._name = name
        f._bits = bits
        return f

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

    def __add__(self, x):
        if isinstance(x, Register):
            return Pointer(reg1=self, reg2=x)
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
    
    def copy(self):
        return Pointer(self.reg1, self.scale, self.reg2, self.disp)
    
    @property
    def bits(self):
        """Maximum number of bits for any register / displacement
        """
        regs = []
        if self.reg1 is not None:
            regs.append(self.reg1.bits)
        if self.reg2 is not None:
            regs.append(self.reg2.bits)
        if self.disp is not None:
            regs.append(32)
        return max(regs)

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
        """
        # if we have register+disp, then no SIB is necessary
        if self.reg1 is not None and self.scale is None and self.reg2 is None:
            if self.disp is None:
                return mod_reg_rm('ind', reg, self.reg1)
            else:
                disp = struct.pack('i', self.disp)
                return mod_reg_rm('ind32', reg, self.reg1) + disp

        # special case: disp and no registers
        #if self.disp is not None and self.reg1 is None and self.reg2 is None:
            #return (mod_reg_rm('ind', reg, 'sib') + mk_sib(0, esp, ebp) + 
                    #struct.pack('i', self.disp))
            
        # for all other options, use SIB normally
        
        byts = {None:0, 1:0, 2:1, 4:2, 8:3}[self.scale]
        offset = esp if self.reg1 is None else self.reg1
        base = self.reg2
        
        if offset is esp and byts > 0:
            raise TypeError("Invalid base/index expression: esp*%d" % (2**byts))
        
        if self.disp is not None:
            mod = 'ind32'
            disp = struct.pack('i', self.disp)
            if base is None:
                mod = 'ind'   # sib suggests disp32 instead of mod
                base = ebp 
                
        elif base in (ebp, None):
            mod = 'ind'
            base = ebp
            disp = struct.pack('i', 0)
        else:
            mod = 'ind'
            disp = ''
            
        modrm_byte = mod_reg_rm(mod, reg, 'sib')
        sib_byte = mk_sib(byts, offset, base)
        return modrm_byte + sib_byte + disp
        
        
        

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


#def ptr(arg):
    #"""Create a memory pointer from arg. 
    
    #This causes arguments to many instructions to be interpreted differently.
    #For example::
    
        #mov(eax, 0x1234)       # Copy the value 0x1234 to register eax.
        #mov(eax, ptr(0x1234))  # Copy the value at memory location 0x1234 to
                               ## register eax.
        #mov(ptr(eax), ebx)     # Copy the value in ebx to the memory location
                               ## stored in eax.
    #"""
    #return Pointer(arg)

#class Pointer(object):
    #def __init__(self, arg):
        #self.arg = arg
        #if isinstance(arg, Register):
            #self.mode = 'reg'
        #elif isinstance(arg, int):
            #self.mode = 'int'
        #elif isinstance(arg, RegisterOffset):
            #self.mode = 'reg_off'
        #else:
            #raise TypeError("Can only create Pointer for int, Register, or "
                            #"RegisterOffset.")


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



#   Instruction definitions
#----------------------------------------


def push(reg):
    """ PUSH REG
    
    Opcode: 50+rd
    Push value stored in reg onto the stack.
    """
    return chr(0x50 | reg)

def pop(reg):
    """ POP REG
    
    Opcode: 50+rd
    Push value stored in reg onto the stack.
    """
    return chr(0x58 | reg)

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
        return chr(0xb8 | r) + struct.pack(fmt, val)
    elif r.bits == 64:
        fmt = '<Q' if fmt is None else fmt
        return rex.w + chr(0xb8 | r) + struct.pack(fmt, val)
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
        
        
def add(dst, src):
    """Perform integer addition of dst + src and store the result in dst.
    """
    dst = interpret(dst)
    src = interpret(src)
    
    if isinstance(dst, Pointer):
        if isinstance(src, Register):
            return add_ptr_reg(dst, src)
        elif isinstance(src, (int, long)):
            return add_ptr_imm(dst, src)
        else:
            raise TypeError('src must be Register or int if dst is Pointer')
    elif isinstance(dst, Register):
        if isinstance(src, Register):
            return add_reg_reg(dst, src)
        elif isinstance(src, Pointer):
            return add_reg_ptr(dst, src)
        elif isinstance(src, (int, long)):
            return add_reg_imm(dst, src)
        else:
            raise TypeError('src must be Register, Pointer, or int')
    else:
        raise TypeError('dst must be Register or Pointer')

def add_reg_imm(reg, val):
    """ADD REG, imm32
    
    Opcode: REX.W 0x81 /0 id
    """
    return rex.w + '\x81' + mod_reg_rm('dir', 0x0, reg) + struct.pack('i', val)
    
def add_reg_reg(reg1, reg2):
    """ ADD r/m64 r64
    
    Opcode: REX.W 0x01 /r
    """
    return rex.w + '\x01' + mod_reg_rm('dir', reg2, reg1)

def add_reg_ptr(reg, addr):
    modrm = ModRmSib(reg, addr)
    return '\x03' + modrm.code

def add_ptr_imm(addr, val):
    return '\x81' + addr.modrm_sib(0x0) + struct.pack('i', val)
    
def add_ptr_reg(addr, reg):
    modrm = ModRmSib(reg, addr)
    return '\x01' + modrm.code

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

def call(op):
    """CALL op
    
    Push EIP onto stack and branch to address specified in *op*.
    
    If op is a signed int (16 or 32 bits), this generates a near, relative call
    where the displacement given in op is relative to the next instruction.
    
    If op is a Register then this generates a near, absolute call where the 
    absolute offset is read from the register.
    """
    if isinstance(op, Register):
        return call_abs(op)
    elif isinstance(op, int):
        return call_rel(op)
    else:
        raise TypeError("call argument must be int or Register")

def call_abs(reg):
    """CALL (absolute) 
    
    Opcode: 0xff /2
    
    """
    # note: opcode extension 2 is encoded in bits 3-5 of the next byte
    #       (this is the reg field of mod_reg_r/m)
    #       the mod bits 00 and r/m bits 101 indicate a 32-bit displacement follows.
    if reg.bits == 32:
        return '\xff' + mod_reg_rm('dir', 0b010, reg)
    else:
        return '\xff' + mod_reg_rm('dir', 0b010, reg)
        
        
def call_rel(addr):
    """CALL (relative) 
    
    Opcode: 0xe8 cd  (cd indicates 4-byte argument follows opcode)
    
    Note: addr is signed int relative to _next_ instruction pointer 
          (which should be current instruction pointer + 5, since this is a
          5 byte instruction).
    """
    # Note: there is no 64-bit relative call.
    return '\xe8' + struct.pack('i', addr)

def jmp(addr):
    if isinstance(addr, Register):
        return jmp_abs(addr)
    elif isinstance(addr, (int, str)):
        return jmp_rel(addr)
    else:
        raise TypeError("jmp accepts Register (absolute), integer, or label (relative).")

def jmp_rel(addr):
    """JMP rel32 (relative)
    
    Opcode: 0xe9 cd 
    """
    if isinstance(addr, str):
        code = Code('\xe9\x00\x00\x00\x00')
        code.replace(1, "%s - next_instr_addr" % addr, 'i')
        return code
    elif isinstance(addr, int):
        return '\xe9' + struct.pack('i', addr - 5)

def jmp_abs(reg):
    """JMP r/m32 (absolute)
    
    Opcode: 0xff /4
    """
    return '\xff' + mod_reg_rm('dir', 0x4, reg)

def int_(code):
    """INT code
    
    Call to interrupt. Code is 1 byte.
    
    Common interrupt codes:
    0x80 = OS
    """
    return '\xcd' + chr(code)

def syscall():
    return '\x0f\x05'

#define OP_MOV      0x89
#define OP_POP      0x58
#define OP_ADD      0x83
#define OP_RETN     0xC2
#define OP_RET      0xC3
#define OP_JMP      0xEB
#define OP_CALL     0xE8


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
        if "<.text>:" in line:
            return out[i+1:]
    raise Exception("Error running 'as' or 'objdump' (see above).")

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

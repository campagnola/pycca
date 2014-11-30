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
    return chr(mod_vals[mod] | reg << 3 | rm)



#     SIB byte
#-----------------------------------------

sib = 0b100  # Indicates SIB byte usage when used as R/M field in ModR/M

sb_vals = {1: 0b0, 2: 0b01000000, 3: 0b10000000, 4: 0b11000000}
def mk_sib(byts, offset, base):
    """Generate SIB byte
    
    byts : 1, 2, 3, or 4
    offset : Register
    base : register
    
    Address is computed as [base] + [offset] * 2^byts
    When base is [ebp], add disp32.
    When offset is [esp], no offset is applied.
    """
    return chr(sb_vals[byts] | offset << 3 | base)


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
        return RegisterOffset(self, x)

    def __sub__(self, x):
        return RegisterOffset(self, -x)


class RegisterOffset(object):
    """Representation of an address calculated as the contents of a register
    plus an offset in bytes::
    
        ebp-0x10   # 16 bytes lower than base pointer
    """
    def __init__(self, reg, offset):
        self.reg = reg
        self.offset = offset


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

mm0 = Register(0b000, 'mm0', 16)  # mm(/r)
mm1 = Register(0b001, 'mm1', 16)
mm2 = Register(0b010, 'mm2', 16)
mm3 = Register(0b011, 'mm3', 16)
mm4 = Register(0b100, 'mm4', 16)
mm5 = Register(0b101, 'mm5', 16)
mm6 = Register(0b110, 'mm6', 16)
mm7 = Register(0b111, 'mm7', 16)

xmm0 = Register(0b000, 'xmm0', 16)  # xmm(/r)
xmm1 = Register(0b001, 'xmm1', 16)
xmm2 = Register(0b010, 'xmm2', 16)
xmm3 = Register(0b011, 'xmm3', 16)
xmm4 = Register(0b100, 'xmm4', 16)
xmm5 = Register(0b101, 'xmm5', 16)
xmm6 = Register(0b110, 'xmm6', 16)
xmm7 = Register(0b111, 'xmm7', 16)




#   Misc. utilities required by instructions
#------------------------------------------------


class Code(object):
    """
    Represents partially compiled machine code with a table of unresolved
    symbol replacements.
    
    Code instances can be compiled to a complete machine code string once all
    symbol values can be determined.
    """
    def __init__(self, code):
        self.code = code
        self.replacements = {}
        
    def replace(self, index, symbol, packing):
        """
        Add a new replacement starting at *index*. 
        
        When this Code is compiled, the value of *symbol* will be packed with
        *packing* and written into the code at *index*.
        """
        self.replacements[index] = (symbol, packing)
        
    def __len__(self):
        return len(self.code)
    
    def compile(self, symbols):
        code = self.code
        for i,repl in self.replacements.items():
            symbol, packing = repl
            val = struct.pack(packing, symbols[symbol])
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
        

def ptr(arg):
    """Create a memory pointer from arg. 
    
    This causes arguments to many instructions to be interpreted differently.
    For example::
    
        mov(eax, 0x1234)       # Copy the value 0x1234 to register eax.
        mov(eax, ptr(0x1234))  # Copy the value at memory location 0x1234 to
                               # register eax.
        mov(ptr(eax), ebx)     # Copy the value in ebx to the memory location
                               # stored in eax.
    """
    return Pointer(arg)

class Pointer(object):
    def __init__(self, arg):
        self.arg = arg
        if isinstance(arg, Register):
            self.mode = 'reg'
        elif isinstance(arg, int):
            self.mode = 'int'
        elif isinstance(arg, RegisterOffset):
            self.mode = 'reg_off'
        else:
            raise TypeError("Can only create Pointer for int, Register, or "
                            "RegisterOffset.")


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
    if isinstance(a, Register) and isinstance(b, Register):
        # Copy register to register
        if a.bits == 32:
            return mov_rm32_r32(a, b)
        elif a.bits == 64:
            return mov_rm64_r64(a, b)
        else:
            raise NotImplementedError('register bit size %d not supported' % a.bits)
    elif isinstance(a, Register) and isinstance(b, int):
        # Copy immediate value to register
        if a.bits == 32:
            return mov_r32_imm32(a, b)
        elif a.bits == 64:
            return mov_r64_imm64(a, b)
        else:
            raise NotImplementedError('register bit size %d not supported' % a.bits)
    else:
        raise TypeError("mov requires (rega,regb) or (rega,int)")

def mov_r_rm(r, rm):
    """ MOV R,R/M
    
    Opcode: 8b /r (uses mod_reg_r/m byte)
    Op/En: RM (REG is dest; R/M is source)
    Move from R/M to R
    """
    # Note: as with many opcodes, flipping bit 6 swaps the R->RM order
    #       yielding 0x89 (mov_rm_r)
    return '\x8b' + mod_reg_rm('dir', r, rm)

def mov_rm32_r32(rm, r):
    """ MOV R/M,R
    
    Opcode: 89 /r (uses mod_reg_r/m byte)
    Op/En: MR (R/M is dest; REG is source)
    Move from R to R/M 
    """
    # Note: as with many opcodes, flipping bit 6 swaps the R->RM order
    #       yielding 0x8B (mov_r_rm)
    return '\x89' + mod_reg_rm('dir', r, rm)

def mov_rm64_r64(rm, r):
    """ MOV R/M,R
    
    Opcode: 89 /r (uses mod_reg_r/m byte)
    Op/En: MR (R/M is dest; REG is source)
    Move from R to R/M 
    """
    # Note: as with many opcodes, flipping bit 6 swaps the R->RM order
    #       yielding 0x8B (mov_r_rm)
    return rex.w + '\x89' + mod_reg_rm('dir', r, rm)

def mov_r32_imm32(r, val, fmt='<I'):
    """ MOV REG,VAL
    
    Opcode: b8+r
    Move VAL (32 bit immediate as unsigned int) to REG.
    """
    return chr(0xb8 | r) + struct.pack(fmt, val)

def mov_r64_imm64(r, val, fmt='<Q'):
    """ MOV REG,VAL
    
    Opcode: REX.W + b8 + rd io
    Move VAL (64 bit immediate as unsigned int) to 64-bit REG.
    """
    return rex.w + chr(0xb8 | r) + struct.pack(fmt, val)

def lea(r, base, offset, disp):
    """ LEA r,[base+offset+disp]
    
    Opcode: 8d /r (uses mod_reg_r/m byte)
    Op/En: RM (REG is dest; R/M is source)
    Load effective address.
    """
    return '\x8d' + mod_reg_rm('ind8', r, sib) + mk_sib(1, offset, base) + chr(disp)

def ret():
    """ RET
    
    Return.
    """
    return '\xc3'

def call(op):
    """CALL op
    
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
            print format(ord(c), 'b'),
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
    def __init__(self, asm):
        self.labels = {}
        self.asm = asm
        code = self.compile(asm)
        
        #pagesize = os.sysconf("SC_PAGESIZE")
        
        # Create a memory-mapped page with execute privileges
        PROT_NONE = 0
        PROT_READ = 1
        PROT_WRITE = 2
        PROT_EXEC = 4
        self.page = mmap.mmap(-1, len(code), prot=PROT_READ|PROT_WRITE|PROT_EXEC)
        self.page.write(code)

        # get the page address
        buf = (ctypes.c_char * len(code)).from_buffer(self.page)
        self.page_addr = ctypes.addressof(buf)

    def get_function(self, label=None):
        addr = self.page_addr
        if label is not None:
            addr += self.labels[label]
        
        # Turn this into a callable function
        f = ctypes.CFUNCTYPE(None)(addr)
        f.page = self  # Make sure page stays alive as long as function pointer!
        return f

    def compile(self, asm):
        ptr = 0
        # First locate all labels
        for cmd in asm:
            ptr += len(cmd)
            if isinstance(cmd, Label):
                self.labels[cmd.name] = ptr
                
        # now compile
        code = ''
        for cmd in asm:
            if isinstance(cmd, str):
                code += cmd
            else:
                code += cmd.compile(self.labels)
                
        return code
        
        
def mkfunction(code):
    page = CodePage(code)
    return page.get_function()



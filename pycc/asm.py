"""

Self-modifying programs
https://gist.github.com/dcoles/4071130
http://www.unix.com/man-page/freebsd/2/mprotect/
http://stackoverflow.com/questions/3125756/allocate-executable-ram-in-c-on-linux


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



import ctypes
import sys
import os
import errno
import mmap
import re
import struct
import subprocess
import tempfile


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


## Register definitions

# note: see codeproject link for more comprehensive set of x86-64 registers
al = Register(0b000, 'al', 8)  # 8-bit registers (low-byte)
cl = Register(0b001, 'cl', 8)
dl = Register(0b010, 'dl', 8)
bl = Register(0b011, 'bl', 8)
ah = Register(0b100, 'ah', 8)  # (high-byte)
ch = Register(0b101, 'ch', 8)
dh = Register(0b110, 'dh', 8)
bh = Register(0b111, 'bh', 8)

ax = Register(0b000, 'ax', 16)  # 16-bit registers
cx = Register(0b001, 'cx', 16)
dx = Register(0b010, 'dx', 16)
bx = Register(0b011, 'bx', 16)
sp = Register(0b100, 'sp', 16)
bp = Register(0b101, 'bp', 16)
si = Register(0b110, 'si', 16)
di = Register(0b111, 'di', 16)

eax = Register(0b000, 'eax', 32)  # 32-bit registers   Accumulator (i/o, math, irq, ...)
ecx = Register(0b001, 'ecx', 32)  #                    Counter (loop counter and shifts) 
edx = Register(0b010, 'edx', 32)  #                    Data (i/o, math, irq, ...)
ebx = Register(0b011, 'ebx', 32)  #                    Base (base memory addresses)
esp = Register(0b100, 'esp', 32)  #                    Stack pointer
ebp = Register(0b101, 'ebp', 32)  #                    Stack base pointer
esi = Register(0b110, 'esi', 32)  #                    Source index
edi = Register(0b111, 'edi', 32)  #                    Destination index

rax = Register(0b000, 'rax', 64)  # 64-bit registers
rcx = Register(0b001, 'rcx', 64)
rdx = Register(0b010, 'rdx', 64)
rbx = Register(0b011, 'rbx', 64)
rsp = Register(0b100, 'rsp', 64)
rbp = Register(0b101, 'rbp', 64)
rsi = Register(0b110, 'rsi', 64)
rdi = Register(0b111, 'rdi', 64)

sib = 0b100  # Indicates SIB byte usage


mod_vals = {
    'ind':   0b00000000, # Fetch contents of address specified in R/M section register
    'ind8':  0b01000000, # Same as 'ind' with 8-bit displacement
    'ind32': 0b10000000, # Same as 'ind' with 32-bit displacement
    'dir':   0b11000000, # Direct addressing; use register directly. 
    }
def mod_reg_rm(mod, reg, rm):
    """Generate a mod_reg_r/m byte.
    """
    return chr(mod_vals[mod] | reg << 3 | rm)


sb_vals = {1: 0b0, 2: 0b01000000, 3: 0b10000000, 4: 0b11000000}
def mk_sib(byts, offset, base):
    """Generate SIB byte
    """
    return chr(sb_vals[byts] | offset << 3 | base)


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
        return mov_rm_r(b, a)
    elif isinstance(a, Register) and isinstance(b, int):
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
    return '\x8B' + mod_reg_rm('dir', r, rm)

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
    return chr(0x48) + chr(0xb8 | r) + struct.pack(fmt, val)

def mov_rm_r(rm, r):
    """ MOV R/M,R
    
    Opcode: 89 /r (uses mod_reg_r/m byte)
    Op/En: MR (R/M is dest; REG is source)
    Move from R to R/M 
    """
    # Note: as with many opcodes, flipping bit 6 swaps the R->RM order
    #       yielding 0x8B (mov_r_rm)
    return '\x89' + mod_reg_rm('dir', r, rm)

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

def call_abs(addr):
    """CALL (absolute) 
    
    Opcode: 0xff /2
    
    Note: addr is an address in memory that contains the address of the function
          (**func)
    """
    # note: opcode extension 2 is encoded in bits 3-5 of the next byte
    #       (this is the reg field of mod_reg_r/m)
    #       the mod bits 00 and r/m bits 101 indicate a 32-bit displacement follows.
    return '\xff' + chr(0b00010101) + struct.pack('I', addr)

def call_rel(addr):
    """CALL (relative) 
    
    Opcode: 0xe8 cd  (cd indicates 4-byte argument follows opcode)
    
    Note: addr is signed int relative to _next_ instruction pointer 
          (which should be current instruction pointer + 5, since this is a
          5 byte instruction).
    """
    return '\xe8' + struct.pack('i', addr)

def int_(code):
    """INT code
    
    Call to interrupt. Code is 1 byte.
    
    Common interrupt codes:
    0x80 = OS
    """
    return '\xcd' + chr(code)


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



def mkfunction(code):
    FUNC = ctypes.CFUNCTYPE(None)
    
    PROT_NONE = 0
    PROT_READ = 1
    PROT_WRITE = 2
    PROT_EXEC = 4
    
    # Get the system page size
    pagesize = os.sysconf("SC_PAGESIZE")
    print("Pagesize: %d"%pagesize)
    
    # Get a libc handle
    libc = ctypes.CDLL('libc.so.6', use_errno=True)

    # Create a memory-mapped page with execute privileges
    page = mmap.mmap(-1, pagesize, prot=PROT_READ|PROT_WRITE|PROT_EXEC)

    page.seek(0)
    page.write(code)

    # Turn this into a callable function
    f = FUNC(buf_addr)
    return f



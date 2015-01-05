# -'- coding: utf-8 -'-
from __future__ import division
import collections

from .instruction import Instruction, RelBranchInstruction


#   Procedure management instructions
#----------------------------------------


class push(Instruction):
    """Push register, memory, or immediate onto the stack.
    
    Opcode: 50+rd
    Push value stored in reg onto the stack.
    """
    name = 'push'

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
            
    
class pop(Instruction):
    """Loads the value from the top of the stack to the location specified with
    the destination operand (or explicit opcode) and then increments the stack 
    pointer. 
    
    The destination operand can be a general-purpose register, memory location,
    or segment register.
    """
    name = 'pop'
    
    modes = {
        ('r/m16',): ['8f /0', 'm', True, True],
        ('r/m32',): ['8f /0', 'm', False, True],
        ('r/m64',): ['8f /0', 'm', True, False],
        ('r16',): ['58+rw', 'o', True, True],
        ('r32',): ['58+rd', 'o', False, True],
        ('r64',): ['58+rd', 'o', True, False],
    }

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
        'o': ['opcode +rd (r)'],
    }
    

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


class call(RelBranchInstruction):
    """Saves procedure linking information on the stack and branches to the 
    called procedure specified using the target operand. 
    
    The target operand specifies the address of the first instruction in the 
    called procedure. The operand can be an immediate value, a general-purpose 
    register, or a memory location.
    """
    name = "call"
    
    # generate absolute call
    modes = {
        #('rel16',): ['e8', 'm', False, True],
        ('rel32',): ['e8', 'i', True, True],
        ('r/m16',): ['ff /2', 'm', False, True],
        ('r/m32',): ['ff /2', 'm', False, True],
        ('r/m64',): ['ff /2', 'm', True, False],
    }

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
        'i': ['imm32'],
    }
        

#   Data moving instructions
#----------------------------------------

class mov(Instruction):
    """Copies the second operand (source operand) to the first operand 
    (destination operand). 
    
    The source operand can be an immediate value, general-purpose register, 
    segment register, or memory location; the destination register can be a 
    general-purpose register, segment register, or memory location. Both 
    operands must be the same size, which can be a byte, a word, a doubleword,
    or a quadword.
    """
    name = 'mov'
    
    modes = collections.OrderedDict([
        (('r/m8', 'r8'),   ['88 /r', 'mr', True, True]),
        (('r/m16', 'r16'), ['89 /r', 'mr', True, True]),
        (('r/m32', 'r32'), ['89 /r', 'mr', True, True]),
        (('r/m64', 'r64'), ['REX.W + 89 /r', 'mr', True, False]),
        
        (('r8', 'r/m8'),   ['8a /r', 'rm', True, True]),
        (('r16', 'r/m16'),   ['8b /r', 'rm', True, True]),
        (('r32', 'r/m32'),   ['8b /r', 'rm', True, True]),
        (('r64', 'r/m64'),   ['REX.W + 8b /r', 'rm', True, False]),
        
        (('r8', 'imm8'),   ['b0+rb', 'oi', True, True]),
        (('r16', 'imm16'), ['b8+rw', 'oi', True, True]),
        (('r32', 'imm32'), ['b8+rd', 'oi', True, True]),
        (('r64', 'imm64'), ['REX.W + b8+rq', 'oi', True, False]),
        
        (('r/m8', 'imm8'),   ['c6 /0', 'mi', True, True]),
        (('r/m16', 'imm16'), ['c7 /0', 'mi', True, True]),
        (('r/m32', 'imm32'), ['c7 /0', 'mi', True, True]),
        (('r/m64', 'imm32'), ['REX.W + c7 /0', 'mi', True, False]),
        
    ])

    operand_enc = {
        'oi': ['opcode +rd (w)', 'imm8/16/32/64'],
        'mi': ['ModRM:r/m (w)', 'imm8/16/32'],
        'mr': ['ModRM:r/m (w)', 'ModRM:reg (r)'],
        'rm': ['ModRM:reg (w)', 'ModRM:r/m (r)'],
    }


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


class add(Instruction):
    """Adds the destination operand (first operand) and the source operand 
    (second operand) and then stores the result in the destination operand. 
    
    The destination operand can be a register or a memory location; the source
    operand can be an immediate, a register, or a memory location. (However, 
    two memory operands cannot be used in one instruction.) When an immediate 
    value is used as an operand, it is sign-extended to the length of the 
    destination operand format.
    """    
    name = 'add'
    
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


# NOTE: this is broken because lea uses a different interpretation of the 0x66
# and 0x67 prefixes.
class lea(Instruction):
    """Computes the effective address of the second operand (the source 
    operand) and stores it in the first operand (destination operand). 
    
    The source operand is a memory address (offset part) specified with one of
    the processors addressing modes; the destination operand is a general-
    purpose register.
    """
    name = "lea"

    modes = collections.OrderedDict([
        (('r16', 'm'), ['8d /r', 'rm', True, True]),
        (('r32', 'm'), ['8d /r', 'rm', True, True]),
        (('r64', 'm'), ['REX.W + 8d /r', 'rm', True, False]),
    ])

    operand_enc = {
        'rm': ['ModRM:reg (w)', 'ModRM:r/m (r)'],
    }
    
    def __init__(self, dst, src):
        Instruction.__init__(self, dst, src)


class dec(Instruction):
    """Subtracts 1 from the destination operand, while preserving the state of
    the CF flag. 
    
    The destination operand can be a register or a memory location. This
    instruction allows a loop counter to be updated without disturbing the CF
    flag. (To perform a decrement operation that updates the CF flag, use a SUB
    instruction with an immediate operand of 1.)
    """
    name = "dec"

    modes = collections.OrderedDict([
        (('r/m8',),  ['fe /1', 'm', True, True]),
        (('r/m16',), ['ff /1', 'm', True, True]),
        (('r/m32',), ['ff /1', 'm', True, True]),
        (('r/m64',), ['REX.W + ff /1', 'm', True, False]),
        
        (('r16',),  ['48+rw', 'o', False, True]),
        (('r32',),  ['48+rd', 'o', False, True]),
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r,w)'],
        'o': ['opcode +rd (r, w)'],
    }

    
class inc(Instruction):
    """Adds 1 to the destination operand, while preserving the state of the CF
    flag. 
    
    The destination operand can be a register or a memory location. This
    instruction allows a loop counter to be updated without disturbing the CF
    flag. (Use a ADD instruction with an immediate operand of 1 to perform an
    increment operation that does updates the CF flag.)
    """    
    name = "inc"

    modes = collections.OrderedDict([
        (('r/m8',),  ['fe /0', 'm', True, True]),
        (('r/m16',), ['ff /0', 'm', True, True]),
        (('r/m32',), ['ff /0', 'm', True, True]),
        (('r/m64',), ['REX.W + ff /0', 'm', True, False]),
        
        (('r16',),  ['40+rw', 'o', False, True]),
        (('r32',),  ['40+rd', 'o', False, True]),
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r,w)'],
        'o': ['opcode +rd (r, w)'],
    }


class imul(Instruction):
    """Performs a signed multiplication of two operands. This instruction has 
    three forms, depending on the number of operands.
    
    * One-operand form — This form is identical to that used by the MUL 
    instruction. Here, the source operand (in a general-purpose register or 
    memory location) is multiplied by the value in the AL, AX, EAX, or RAX 
    register (depending on the operand size) and the product (twice the size of
    the input operand) is stored in the AX, DX:AX, EDX:EAX, or RDX:RAX 
    registers, respectively.
    
    * Two-operand form — With this form the destination operand (the first 
    operand) is multiplied by the source operand (second operand). The 
    destination operand is a general-purpose register and the source operand is
    an immediate value, a general-purpose register, or a memory location. The 
    intermediate product (twice the size of the input operand) is truncated and
    stored in the destination operand location.
    
    * Three-operand form — This form requires a destination operand (the first
    operand) and two source operands (the second and the third operands). Here,
    the first source operand (which can be a general-purpose register or a 
    memory location) is multiplied by the second source operand (an immediate 
    value). The intermediate product (twice the size of the first source 
    operand) is truncated and stored in the destination operand (a 
    general-purpose register).
    """
    name = "imul"

    modes = collections.OrderedDict([
        (('r16', 'r/m16'),   ['0faf /r', 'rm', True, True]),
        (('r32', 'r/m32'),   ['0faf /r', 'rm', True, True]),
        (('r64', 'r/m64'),   ['REX.W + 0faf /r', 'rm', True, False]),
        
        (('r16', 'r/m16', 'imm8'),   ['6b /r ib', 'rmi', True, True]),
        (('r32', 'r/m32', 'imm8'),   ['6b /r ib', 'rmi', True, True]),
        (('r64', 'r/m64', 'imm8'),   ['REX.W + 6b /r ib', 'rmi', True, False]),
        
        (('r16', 'r/m16', 'imm16'),   ['69 /r iw', 'rmi', True, True]),
        (('r32', 'r/m32', 'imm32'),   ['69 /r id', 'rmi', True, True]),
        (('r64', 'r/m64', 'imm32'),   ['REX.W + 69 /r id', 'rmi', True, False]),
    ])

    operand_enc = {
        'rm': ['ModRM:reg (r,w)', 'ModRM:r/m (r)'],
        'rmi': ['ModRM:reg (r,w)', 'ModRM:r/m (r)', 'imm8/16/32'],
    }


class idiv(Instruction):
    """Divides the (signed) value in the AX, DX:AX, or EDX:EAX (dividend) by 
    the source operand (divisor) and stores the result in the AX (AH:AL), 
    DX:AX, or EDX:EAX registers. The source operand can be a general-purpose 
    register or a memory location. The action of this instruction depends on 
    the operand size (dividend/divisor).
    """
    name = "idiv"

    modes = collections.OrderedDict([
        (('r/m8',), ('f6 /7', 'm', True, True)),
        (('r/m16',), ('f7 /7', 'm', True, True)),
        (('r/m32',), ('f7 /7', 'm', True, True)),
        (('r/m64',), ('REX.W + f6 /7', 'm', True, False)),
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
    }

    

#   Testing instructions
#----------------------------------------

class cmp(Instruction):
    """Compares the first source operand with the second source operand and 
    sets the status flags in the EFLAGS register according to the results. 
    
    The comparison is performed by subtracting the second operand from the
    first operand and then setting the status flags in the same manner as the
    SUB instruction. When an immediate value is used as an operand, it is 
    sign-extended to the length of the first operand.
    """
    name = "cmp"
    
    modes = collections.OrderedDict([
        (('r/m8', 'imm8'), ('80 /7', 'mi', True, True)),
        (('r/m16', 'imm16'), ('81 /7', 'mi', True, True)),
        (('r/m32', 'imm32'), ('81 /7', 'mi', True, True)),
        (('r/m64', 'imm32'), ('REX.W + 81 /7', 'mi', True, False)),
        
        (('r/m16', 'imm8'), ('83 /7', 'mi', True, True)),
        (('r/m32', 'imm8'), ('83 /7', 'mi', True, True)),
        (('r/m64', 'imm8'), ('REX.W + 83 /7', 'mi', True, False)),
        
        (('r/m8', 'r8'), ('38 /r', 'mr', True, True)),
        (('r/m16', 'r16'), ('39 /r', 'mr', True, True)),
        (('r/m32', 'r32'), ('39 /r', 'mr', True, True)),
        (('r/m64', 'r64'), ('REX.W + 39 /r', 'mr', True, False)),
        
        (('r8', 'r/m8'), ('3a /r', 'rm', True, True)),
        (('r16', 'r/m16'), ('3b /r', 'rm', True, True)),
        (('r32', 'r/m32'), ('3b /r', 'rm', True, True)),
        (('r64', 'r/m64'), ('REX.W + 3b /r', 'rm', True, False)),
    ])

    operand_enc = {
        'rm': ['ModRM:reg (r,w)', 'ModRM:r/m (r)'],
        'mr': ['ModRM:r/m (r,w)', 'ModRM:reg (r)'],
        'mi': ['ModRM:r/m (r,w)', 'imm8/16/32'],
    }


class test(Instruction):
    name = "test"
    
    modes = collections.OrderedDict([
        (('r/m8', 'imm8'), ('f6 /0', 'mi', True, True)),
        (('r/m16', 'imm16'), ('f7 /0', 'mi', True, True)),
        (('r/m32', 'imm32'), ('f7 /0', 'mi', True, True)),
        (('r/m64', 'imm32'), ('REX.W + f7 /0', 'mi', True, False)),
        
        (('r/m8', 'r8'), ('84 /r', 'mr', True, True)),
        (('r/m16', 'r16'), ('85 /r', 'mr', True, True)),
        (('r/m32', 'r32'), ('85 /r', 'mr', True, True)),
        (('r/m64', 'r64'), ('REX.W + 85 /r', 'mr', True, False)),
    ])
    
    operand_enc = {
        'mr': ['ModRM:r/m (r,w)', 'ModRM:reg (r)'],
        'mi': ['ModRM:r/m (r,w)', 'imm8/16/32'],
    }
    



#   Branching instructions
#----------------------------------------

class jmp(RelBranchInstruction):
    name = "jmp"
    
    # generate absolute call
    modes = {
        ('rel8',): ['eb', 'i', True, True],
        ('rel16',): ['e9', 'i', False, True],
        ('rel32',): ['e9', 'i', True, True],
        
        ('r/m16',): ['ff /4', 'm', False, True],
        ('r/m32',): ['ff /4', 'm', False, True],
        ('r/m64',): ['ff /4', 'm', True, False],
    }

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
        'i': ['imm32'],
    }


def _jcc(name, opcode, doc):
    """Create a jcc instruction class.
    """
    modes = {
        ('rel8',): [opcode, 'i', True, True],
        ('rel16',): [opcode, 'i', False, True],
        ('rel32',): [opcode, 'i', True, True],
    }

    op_enc = {
        'i': ['imm32'],
    }

    return type(name, (RelBranchInstruction,), {'modes': modes, 
                                                'operand_enc': op_enc,
                                                '__doc__': doc}) 


ja   = _jcc('ja',   '0f87', """Jump near if above (CF=0 and ZF=0).""")
jae  = _jcc('jae',  '0f83', """Jump near if above or equal (CF=0).""")
jb   = _jcc('jb',   '0f82', """Jump near if below (CF=1).""")
jbe  = _jcc('jbe',  '0f86', """Jump near if below or equal (CF=1 or ZF=1).""")
jc   = _jcc('jc',   '0f82', """Jump near if carry (CF=1).""")
je   = _jcc('je',   '0f84', """Jump near if equal (ZF=1).""")
jz   = _jcc('jz',   '0f84', """Jump near if 0 (ZF=1).""")
jg   = _jcc('jg',   '0f8f', """Jump near if greater (ZF=0 and SF=OF).""")
jge  = _jcc('jge',  '0f8d', """Jump near if greater or equal (SF=OF).""")
jl   = _jcc('jl',   '0f8c', """Jump near if less (SF≠ OF).""")
jle  = _jcc('jle',  '0f8e', """Jump near if less or equal (ZF=1 or SF≠ OF).""")
jna  = _jcc('jna',  '0f86', """Jump near if not above (CF=1 or ZF=1).""")
jnae = _jcc('jnae', '0f82', """Jump near if not above or equal (CF=1).""")
jnb  = _jcc('jnb',  '0f83', """Jump near if not below (CF=0).""")
jnbe = _jcc('jnbe', '0f87', """Jump near if not below or equal (CF=0 and ZF=0).""")
jnc  = _jcc('jnc',  '0f83', """Jump near if not carry (CF=0).""")
jne  = _jcc('jne',  '0f85', """Jump near if not equal (ZF=0).""")
jng  = _jcc('jng',  '0f8e', """Jump near if not greater (ZF=1 or SF≠ OF).""")
jnge = _jcc('jnge', '0f8c', """Jump near if not greater or equal (SF ≠ OF).""")
jnl  = _jcc('jnl',  '0f8d', """Jump near if not less (SF=OF).""")
jnle = _jcc('jnle', '0f8f', """Jump near if not less or equal (ZF=0 and SF=OF).""")
jno  = _jcc('jno',  '0f81', """Jump near if not overflow (OF=0).""")
jnp  = _jcc('jnp',  '0f8b', """Jump near if not parity (PF=0).""")
jns  = _jcc('jns',  '0f89', """Jump near if not sign (SF=0).""")
jnz  = _jcc('jnz',  '0f85', """Jump near if not zero (ZF=0).""")
jo   = _jcc('jo',   '0f80', """Jump near if overflow (OF=1).""")
jp   = _jcc('jp',   '0f8a', """Jump near if parity (PF=1).""")
jpe  = _jcc('jpe',  '0f8a', """Jump near if parity even (PF=1).""")
jpo  = _jcc('jpo',  '0f8b', """Jump near if parity odd (PF=0).""")
js   = _jcc('js',   '0f88', """Jump near if sign (SF=1).""")



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


# -'- coding: utf-8 -'-

import collections, struct

from .instruction import Instruction, RelBranchInstruction


#   Procedure management instructions
#----------------------------------------


class push(Instruction):
    """Decrements the stack pointer and then stores the source operand on the 
    top of the stack.
    
    =============== ====== ====== ======================================
    src             32-bit 64-bit description
    =============== ====== ====== ======================================
    r/m8             X      X     Push src onto stack
    r/m16            X      X     
    r/m32            X
    r/m64                   X
    imm8/32          X      X
    =============== ====== ====== ======================================
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
    
    def __init__(self, src):  # set method signature
        Instruction.__init__(self, src)

    
class pop(Instruction):
    """Loads the value from the top of the stack to the location specified with
    the destination operand (or explicit opcode) and then increments the stack 
    pointer. 
    
    The destination operand can be a general-purpose register, memory location,
    or segment register.
    
    =============== ====== ====== ======================================
    dst             32-bit 64-bit description
    =============== ====== ====== ======================================
    r/m8             X      X     Pop value from stack into dst
    r/m16            X      X     
    r/m32            X
    r/m64                   X
    =============== ====== ====== ======================================
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
    
    def __init__(self, dst):  # set method signature
        Instruction.__init__(self, dst)
    

class ret(Instruction):
    """ RET
    
    Return; pop a value from the stack and branch to that address.
    Optionally, extra values may be popped from the stack after the return 
    address.
    
    =============== ====== ====== ======================================
    size            32-bit 64-bit description
    =============== ====== ====== ======================================
    (no operands)    X      X     Return without touching stack
    imm16            X      X     Pop *size* bytes from stack and return
    =============== ====== ====== ======================================
    """
    name = 'ret'
    
    modes = collections.OrderedDict([
        (('imm16',),   ['c2 iw', 'i', True, True]),
        ((), ['c3', None, True, True]),
    ])
        
    operand_enc = {
        'i': ['imm16'],
    }


class leave(Instruction):
    """ LEAVE
    
    High-level procedure exit. Accepts no operands.
    Equivalent to::
    
       mov(esp, ebp)
       pop(ebp)
    """
    name = 'leave'
    
    modes = collections.OrderedDict([
        ((), ['c9', None, True, True]),
    ])
        
    def __init__(self):  # set method signature
        Instruction.__init__(self)


class call(RelBranchInstruction):
    """Saves procedure linking information on the stack and branches to the 
    called procedure specified using the target operand. 
    
    The target operand specifies the address of the first instruction in the 
    called procedure. The operand can be an immediate value, a general-purpose 
    register, or a memory location.
    
    =============== ====== ====== =============================================
    dst             32-bit 64-bit description
    =============== ====== ====== =============================================
    rel32            X      X     Call address relative to this instruction
    r/m16            X            Call absolute address stored at r/m16/32/64
    r/m32            X
    r/m64                   X
    =============== ====== ====== =============================================
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
        
    def __init__(self, addr):  # set method signature
        RelBranchInstruction.__init__(self, addr)


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
    
    ====== ================= ====== ====== ======================================
    dst    src               32-bit 64-bit description
    ====== ================= ====== ====== ======================================
    r/m8   r/m8, imm8         X      X     Copy src value to dst
    r/m16  r/m16, imm16       X      X     
    r/m32  r/m32, imm32       X      X
    r/m64  r/m64, imm32              X
    r64    imm64                     X     
    ====== ================= ====== ====== ======================================
    """
    name = 'mov'
    
    modes = collections.OrderedDict([
        (('r/m8', 'r8'),   ['88 /r', 'mr', True, True]),
        (('r/m16', 'r16'), ['89 /r', 'mr', True, True]),
        (('r/m32', 'r32'), ['89 /r', 'mr', True, True]),
        (('r/m64', 'r64'), ['REX.W + 89 /r', 'mr', True, False]),
        
        (('r8', 'r/m8'),   ['8a /r', 'rm', True, True]),
        (('r16', 'r/m16'), ['8b /r', 'rm', True, True]),
        (('r32', 'r/m32'), ['8b /r', 'rm', True, True]),
        (('r64', 'r/m64'), ['REX.W + 8b /r', 'rm', True, False]),
        
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

    def __init__(self, dst, src):  # set method signature
        Instruction.__init__(self, dst, src)


class movsd(Instruction):
    """MOVSD moves a scalar double-precision floating-point value from the 
    source operand (second operand) to the destination operand (first operand).
    
    The source and destination operands can be XMM registers or 64-bit memory
    locations. This instruction can be used to move a double-precision 
    floating-point value to and from the low quadword of an XMM register and a
    64-bit memory location, or to move a double-precision floating-point value
    between the low quadwords of two XMM registers. The instruction cannot be
    used to transfer data between memory locations.
    
    ====== ================= ====== ====== ======================================
    dst    src               32-bit 64-bit description
    ====== ================= ====== ====== ======================================
    xmm    xmm, m64           X      X     Copy xmm or m64 to xmm
    m64    xmm                X      X     Copy xmm to m64
    ====== ================= ====== ====== ======================================
    """
    name = 'movsd'
    
    modes = collections.OrderedDict([
        (('xmm1', 'xmm2/m64'),   ['f20f10 /r', 'rm', True, True, 'sse2']),
        (('m64', 'xmm1'),   ['f20f11 /r', 'mr', True, True, 'sse2']),
    ])
    
    operand_enc = {
        'mr': ['ModRM:r/m (w)', 'ModRM:reg (r)'],
        'rm': ['ModRM:reg (w)', 'ModRM:r/m (r)'],
    }
    
    def __init__(self, dst, src):  # set method signature
        Instruction.__init__(self, dst, src)



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
    
    ====== =============== ====== ====== ======================================
    dst    src             32-bit 64-bit description
    ====== =============== ====== ====== ======================================
    r/m8   r/m8, imm8       X      X     dst += src
    r/m16  r/m16, imm8/16   X      X     
    r/m32  r/m32, imm8/32   X      X
    r/m64  r/m64, imm8/32          X
    ====== =============== ====== ====== ======================================
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

    def __init__(self, dst, src):  # set method signature
        Instruction.__init__(self, dst, src)


class sub(Instruction):
    """Subtracts the second operand (source operand) from the first operand 
    (destination operand) and stores the result in the destination operand.
    
    The destination operand can be a register or a memory location; the source 
    operand can be an immediate, register, or memory location. (However, two 
    memory operands cannot be used in one instruction.) When an immediate value
    is used as an operand, it is sign-extended to the length of the destination
    operand format.
    
    ====== =============== ====== ====== ======================================
    dst    src             32-bit 64-bit description
    ====== =============== ====== ====== ======================================
    r/m8   r/m8, imm8       X      X     dst -= src
    r/m16  r/m16, imm8/16   X      X     
    r/m32  r/m32, imm8/32   X      X     
    r/m64  r/m64, imm8/64          X
    ====== =============== ====== ====== ======================================
    """    
    name = 'sub'
    
    modes = collections.OrderedDict([
        (('r/m8', 'imm8'),   ['80 /5', 'mi', True, True]),
        (('r/m16', 'imm16'), ['81 /5', 'mi', True, True]),
        (('r/m32', 'imm32'), ['81 /5', 'mi', True, True]),
        (('r/m64', 'imm32'), ['REX.W + 81 /5', 'mi', True, False]),
        
        (('r/m16', 'imm8'),  ['83 /5', 'mi', True, True]),
        (('r/m32', 'imm8'),  ['83 /5', 'mi', True, True]),
        (('r/m64', 'imm8'),  ['REX.W + 85 /0', 'mi', True, False]),        
        
        (('r/m8', 'r8'),   ['28 /r', 'mr', True, True]),
        (('r/m16', 'r16'), ['29 /r', 'mr', True, True]),
        (('r/m32', 'r32'), ['29 /r', 'mr', True, True]),
        (('r/m64', 'r64'), ['REX.W + 29 /r', 'mr', True, False]),
        
        (('r8', 'r/m8'),   ['2a /r', 'rm', True, True]),
        (('r16', 'r/m16'),   ['2b /r', 'rm', True, True]),
        (('r32', 'r/m32'),   ['2b /r', 'rm', True, True]),
        (('r64', 'r/m64'),   ['REX.W + 2b /r', 'rm', True, False]),
    ])

    operand_enc = {
        'mi': ['ModRM:r/m (r,w)', 'imm8/16/32'],
        'mr': ['ModRM:r/m (r,w)', 'ModRM:reg (r)'],
        'rm': ['ModRM:reg (r,w)', 'ModRM:r/m (r)'],
    }

    def __init__(self, dst, src):  # set method signature
        Instruction.__init__(self, dst, src)


# NOTE: this is broken because lea uses a different interpretation of the 0x66
# and 0x67 prefixes.
class lea(Instruction):
    """Computes the effective address of the second operand (the source 
    operand) and stores it in the first operand (destination operand). 
    
    The source operand is a memory address (offset part) specified with one of
    the processors addressing modes; the destination operand is a general-
    purpose register.
    
    ========= =============== ====== ====== ======================================
    dst       src             32-bit 64-bit description
    ========= =============== ====== ====== ======================================
    r16       m               X      X      Store src address in dst.
    r32       m               X      X
    r64       m                      X
    ========= =============== ====== ====== ======================================
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
    
    ====== ====== ====== ======================================
    dst    32-bit 64-bit description
    ====== ====== ====== ======================================
    r/m8    X      X     dst -= 1
    r/m16   X      X     
    r/m32   X      X     
    r/m64          X
    ====== ====== ====== ======================================
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

    def __init__(self, dst):  # set method signature
        Instruction.__init__(self, dst)

    
class inc(Instruction):
    """Adds 1 to the destination operand, while preserving the state of the CF
    flag. 
    
    The destination operand can be a register or a memory location. This
    instruction allows a loop counter to be updated without disturbing the CF
    flag. (Use a ADD instruction with an immediate operand of 1 to perform an
    increment operation that does updates the CF flag.)
    
    ====== ====== ====== ======================================
    dst    32-bit 64-bit description
    ====== ====== ====== ======================================
    r/m8    X      X     dst += 1
    r/m16   X      X     
    r/m32   X      X     
    r/m64          X
    ====== ====== ====== ======================================
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

    def __init__(self, dst):  # set method signature
        Instruction.__init__(self, dst)


class imul(Instruction):
    """Performs a signed multiplication of two operands. This instruction has 
    three forms, depending on the number of operands.
    
    * One-operand form — **[Not currently supported by pycca]**
      This form is identical to that used by the MUL 
      instruction. Here, the source operand (in a general-purpose register or 
      memory location) is multiplied by the value in the AL, AX, EAX, or RAX 
      register (depending on the operand size) and the product (twice the size
      of the input operand) is stored in the AX, DX:AX, EDX:EAX, or RDX:RAX 
      registers, respectively.
    
    * Two-operand form — With this form the destination operand (the first 
      operand) is multiplied by the source operand (second operand). The 
      destination operand is a general-purpose register and the source operand
      is an immediate value, a general-purpose register, or a memory location. 
      The intermediate product (twice the size of the input operand) is 
      truncated and stored in the destination operand location.
      
      ====== =============== ====== ====== ======================================
      dst    src             32-bit 64-bit description
      ====== =============== ====== ====== ======================================
      r16    r/m16           X      X      dst \*= src
      r32    r/m32           X      X     
      r64    r/m64                  X
      ====== =============== ====== ====== ======================================
    
    * Three-operand form — This form requires a destination operand (the first
      operand) and two source operands (the second and the third operands).
      Here, the first source operand (which can be a general-purpose register
      or a memory location) is multiplied by the second source operand (an 
      immediate value). The intermediate product (twice the size of the first 
      source operand) is truncated and stored in the destination operand (a 
      general-purpose register).
      
      ====== ======= ======= ====== ====== ======================================
      dst    src1     src2   32-bit 64-bit description
      ====== ======= ======= ====== ====== ======================================
      r16    r/m16   imm8/16 X      X      dst = src1 \* src2
      r32    r/m32   imm8/32 X      X     
      r64    r/m64   imm8/64        X
      ====== ======= ======= ====== ====== ======================================
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
   
    ======= ====== ====== ======================================================
    src     32-bit 64-bit description
    ======= ====== ====== ======================================================
    r/m8    X      X      Divide AX by src, set AL=quotient, AH=remainder
    r/m16   X      X      Divide DX:AX by src, set AX=quotient, DX=remainder
    r/m32   X      X      Divide EDX:EAX by src, set EAX=quotient, EDX=remainder
    r/m64          X      Divide RDX:RAX by src, set RAX=quotient, RDX=remainder
    ======= ====== ====== ======================================================
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

    def __init__(self, src):  # set method signature
        Instruction.__init__(self, src)

    
class fld(Instruction):
    """Pushes the source operand onto the FPU register stack.
    
    The source 
    operand can be in single-precision, double-precision, or double 
    extended-precision floating-point format. If the source operand is in 
    single-precision or double-precision floating-point format, it is 
    automatically converted to the double extended-precision floating-point 
    format before being pushed on the stack.
    
    ======= ====== ====== ======================================================
    src     32-bit 64-bit description
    ======= ====== ====== ======================================================
    m32      X      X     Push 32 bit float at src onto FPU stack
    m64      X      X     Push 64 bit float at src onto FPU stack
    m80      X      X     Push 80 bit float at src onto FPU stack
    ST(i)    X      X     Push float at ST(i) onto FPU stack
    ======= ====== ====== ======================================================
    """
    name = 'fld'
    
    modes = collections.OrderedDict([
        (('m32fp',), ('d9 /0', 'm', True, True)),
        (('m64fp',), ('dd /0', 'm', True, True)),
        (('m80fp',), ('db /5', 'm', True, True)),
        (('ST(i)',), ('d9c0+i', 'o', True, True)),
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
        'o': ['opcode +rd (r)'],
    }

    def __init__(self, src):  # set method signature
        Instruction.__init__(self, src)


class fst(Instruction):
    """The FST instruction copies the value in the ST(0) register to the 
    destination operand, which can be a memory location or another register in
    the FPU register stack. 
    
    When storing the value in memory, the value is converted to 
    single-precision or double-precision floating-point format.
    
    ======= ====== ====== ======================================================
    dst     32-bit 64-bit description
    ======= ====== ====== ======================================================
    m32      X      X     Store ST(0) to 32 bit float at dst
    m64      X      X     Store ST(0) to 64 bit float at dst
    m80      X      X     Store ST(0) to 80 bit float at dst
    ST(i)           X     Store ST(0) to ST(i)
    ======= ====== ====== ======================================================
    """
    name = 'fst'
    
    modes = collections.OrderedDict([
        (('m32fp',), ('d9 /2', 'm', True, True)),
        (('m64fp',), ('dd /2', 'm', True, True)),
        (('m80fp',), ('db /7', 'm', True, True)),
        (('ST(i)',), ('ddd0+i', 'o', True, True)),
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
        'o': ['opcode +rd (r)'],
    }

    def __init__(self, dst):  # set method signature
        Instruction.__init__(self, dst)


class fstp(Instruction):
    """The FSTP instruction performs the same operation as the FST instruction
    and then pops the register stack. 
    
    To pop the register stack, the processor marks the ST(0) register as empty 
    and increments the stack pointer (TOP) by 1. The FSTP instruction can also 
    store values in memory in double extended-precision floating-point format.
    
    ======= ====== ====== ======================================================
    dst     32-bit 64-bit description
    ======= ====== ====== ======================================================
    m32      X      X     Pop ST(0) to 32 bit float at dst
    m64      X      X     Pop ST(0) to 64 bit float at dst
    m80      X      X     Pop ST(0) to 80 bit float at dst
    ST(i)           X     Pop ST(0) to ST(i)
    ======= ====== ====== ======================================================
    """
    name = 'fstp'
    
    modes = collections.OrderedDict([
        (('m32fp',), ('d9 /3', 'm', True, True)),
        (('m64fp',), ('dd /3', 'm', True, True)),
        (('m80fp',), ('db /7', 'm', True, True)),
        (('ST(i)',), ('ddd8+i', 'o', True, True)),
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
        'o': ['opcode +rd (r)'],
    }

    def __init__(self, dst):  # set method signature
        Instruction.__init__(self, dst)


class fild(Instruction):
    """Converts the signed-integer source operand into double 
    extended-precision floating-point format and pushes the value onto the FPU
    register stack. 
    
    The source operand can be a word, doubleword, or quadword integer. It is 
    loaded without rounding errors. The sign of the source operand is 
    preserved.
    
    ======= ====== ====== ======================================================
    src     32-bit 64-bit description
    ======= ====== ====== ======================================================
    m16      X      X     Push 16 bit int at src onto FPU stack
    m32      X      X     Push 32 bit int at src onto FPU stack
    m64      X      X     Push 64 bit int at src onto FPU stack
    ======= ====== ====== ======================================================
    """
    name = 'fild'
    
    modes = collections.OrderedDict([
        (('m16int',), ('df /0', 'm', True, True)),
        (('m32int',), ('db /0', 'm', True, True)),
        (('m64int',), ('df /5', 'm', True, True)),
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
    }
    
    def generate_code(self):
        # Don't need 66h prefix for this instruction.
        # todo: could this have been deduced from the 'm16int' sig?
        if b'\x66' in self.prefixes:
            self.prefixes.remove(b'\x66')
        Instruction.generate_code(self)

    def __init__(self, src):  # set method signature
        Instruction.__init__(self, src)


class fist(Instruction):
    """The FIST instruction converts the value in the ST(0) register to a 
    signed integer and stores the result in the destination operand. 
    
    Values can be stored in word or doubleword integer format. The destination 
    operand specifies the address where the first byte of the destination value
    is to be stored.
    
    ======= ====== ====== ======================================================
    dst     32-bit 64-bit description
    ======= ====== ====== ======================================================
    m16      X      X     Store ST(0) to 16 bit signed int at dst
    m32      X      X     Store ST(0) to 32 bit signed int at dst
    ======= ====== ====== ======================================================
    """
    name = 'fist'
    
    modes = collections.OrderedDict([
        (('m16int',), ('df /2', 'm', True, True)),
        (('m32int',), ('db /2', 'm', True, True)),
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
    }
    
    def generate_code(self):
        # Don't need 66h prefix for this instruction.
        # todo: could this have been deduced from the 'm16int' sig?
        if b'\x66' in self.prefixes:
            self.prefixes.remove(b'\x66')
        Instruction.generate_code(self)

    def __init__(self, dst):  # set method signature
        Instruction.__init__(self, dst)


class fistp(Instruction):
    """The FISTP instruction performs the same operation as the FIST 
    instruction and then pops the register stack. 
    
    To pop the register stack, the processor marks the ST(0) register as empty 
    and increments the stack pointer (TOP) by 1. The FISTP instruction also 
    stores values in quadword integer format.
    
    ======= ====== ====== ======================================================
    dst     32-bit 64-bit description
    ======= ====== ====== ======================================================
    m16      X      X     Store ST(0) to 16 bit signed int at dst
    m32      X      X     Store ST(0) to 32 bit signed int at dst
    m64      X      X     Store ST(0) to 64 bit signed int at dst
    ======= ====== ====== ======================================================
    """
    name = 'fistp'
    
    modes = collections.OrderedDict([
        (('m16int',), ('df /3', 'm', True, True)),
        (('m32int',), ('db /3', 'm', True, True)),
        (('m64int',), ('df /7', 'm', True, True)),
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
    }
    
    def generate_code(self):
        # Don't need 66h prefix for this instruction.
        # todo: could this have been deduced from the 'm16int' sig?
        if b'\x66' in self.prefixes:
            self.prefixes.remove(b'\x66')
        Instruction.generate_code(self)

    def __init__(self, src):  # set method signature
        Instruction.__init__(self, src)


class fabs(Instruction):
    """Clears the sign bit of ST(0) to create the absolute value of the 
    operand. Accepts no operands.
    """
    name = 'fabs'

    modes = collections.OrderedDict([
        ((), ('d9e1', None, True, True))
    ])

    def __init__(self):  # set method signature
        Instruction.__init__(self)


class fadd(Instruction):
    """Adds the destination and source operands and stores the sum in the 
    destination location.
    
    The destination operand is always an FPU register; the source operand can 
    be a register or a memory location. Source operands in memory can be in 
    single-precision or double-precision floating-point format.
    
    ====== ======= ====== ====== ======================================================
    dst    src     32-bit 64-bit description
    ====== ======= ====== ====== ======================================================
           m32      X      X     ST(0) += src
           m64      X      X     
    st(j)  st(i)    X      X     dst += src  (at least one operand must be st(0))
    ====== ======= ====== ====== ======================================================
    """
    name = 'fadd'

    modes = collections.OrderedDict([
        (('m32fp',), ('d8 /0', 'm', True, True)),
        (('m64fp',), ('dc /0', 'm', True, True)),
        
        (('st(0)', 'st(i)'), ('d8c0+i', '-o', True, True)),
        (('st(i)', 'st(0)'), ('dcc0+i', 'o-', True, True)),
        
        ((), ('dec1', None, True, True)),  # no-operand version is same as faddp
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
        'o-': ['opcode +rd (r)', None],
        '-o': [None, 'opcode +rd (r)'],
    }

    
class faddp(Instruction):
    """Adds the destination and source operands and stores the sum in the 
    destination location.
    
    The FADDP instructions perform the additional operation of popping the FPU
    register stack after storing the result. To pop the register stack, the 
    processor marks the ST(0) register as empty and increments the stack 
    pointer (TOP) by 1.
    
    ====== ======= ====== ====== ==============================================
    dst    src     32-bit 64-bit description
    ====== ======= ====== ====== ==============================================
    st(i)  st(0)    X      X     dst += st(0), pop st(0) from FP stack 
                    X      X     st(1) += st(0), pop st(0) from FP stack 
    ====== ======= ====== ====== ==============================================
    """
    name = 'faddp'

    modes = collections.OrderedDict([
        (('st(i)', 'st(0)'), ('dec0+i', 'o-', True, True)),
        
        ((), ('dec1', None, True, True)),
    ])

    operand_enc = {
        'o-': ['opcode +rd (r)', None],
    }
    

class fiadd(Instruction):
    """The FIADD instructions are similar to FADD, but convert an integer 
    source operand to double extended-precision floating-point format before 
    performing the addition.
    
    ======= ====== ====== ======================================================
    src     32-bit 64-bit description
    ======= ====== ====== ======================================================
    m32      X      X     ST(0) += src
    m64      X      X     
    ======= ====== ====== ======================================================
    """
    name = 'fiadd'

    modes = collections.OrderedDict([
        (('m32int',), ('da /0', 'm', True, True)),
        (('m16int',), ('de /0', 'm', True, True)),
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
    }
    
    def generate_code(self):
        # Don't need 66h prefix for this instruction.
        # todo: could this have been deduced from the 'm16int' sig?
        if b'\x66' in self.prefixes:
            self.prefixes.remove(b'\x66')
        Instruction.generate_code(self)

    def __init__(self, src):  # set method signature
        Instruction.__init__(self, src)



class fsub(Instruction):
    """Subtracts the source operand from the destination operand and stores the
    difference in the destination location. The destination operand is always 
    an FPU data register; the source operand can be a register or a memory 
    location. Source operands in memory can be in single-precision or 
    double-precision floating-point format.
    
    ====== ======= ====== ====== ================================================
    dst    src     32-bit 64-bit description
    ====== ======= ====== ====== ================================================
           m32      X      X     ST(0) -= src
           m64      X      X     
    st(j)  st(i)    X      X     dst -= src  (at least one operand must be st(0))
    ====== ======= ====== ====== ================================================
    """
    name = 'fsub'

    modes = collections.OrderedDict([
        (('m32fp',), ('d8 /4', 'm', True, True)),
        (('m64fp',), ('dc /4', 'm', True, True)),
        
        (('st(0)', 'st(i)'), ('d8e0+i', '-o', True, True)),
        (('st(i)', 'st(0)'), ('dce8+i', 'o-', True, True)),
        
        ((), ('dee9', None, True, True)),  # no-operand version is same as fsubp
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
        'o-': ['opcode +rd (r)', None],
        '-o': [None, 'opcode +rd (r)'],
    }

    
class fsubp(Instruction):
    """The FSUBP instructions are similar to FSUB but perform the additional 
    operation of popping the FPU register stack following the subtraction. To 
    pop the register stack, the processor marks the ST(0) register as empty and
    increments the stack pointer (TOP) by 1.
    
    ====== ======= ====== ====== ==============================================
    dst    src     32-bit 64-bit description
    ====== ======= ====== ====== ==============================================
    st(i)  st(0)    X      X     dst -= st(0), pop st(0) from FP stack 
                    X      X     st(1) -= st(0), pop st(0) from FP stack 
    ====== ======= ====== ====== ==============================================
    """
    name = 'fsubp'

    modes = collections.OrderedDict([
        (('st(i)', 'st(0)'), ('dee8+i', 'o-', True, True)),
        
        ((), ('dee9', None, True, True)),
    ])

    operand_enc = {
        'o-': ['opcode +rd (r)', None],
    }
    

class fisub(Instruction):
    """Subtracts the source operand from the destination operand and stores the
    difference in the destination location. The destination operand is always 
    an FPU data register; the source operand can be a register or a memory 
    location. Source operands in memory can be in word or doubleword integer 
    format.
    
    ======= ====== ====== ======================================================
    src     32-bit 64-bit description
    ======= ====== ====== ======================================================
    m32      X      X     ST(0) -= src
    m64      X      X     
    ======= ====== ====== ======================================================
    """
    name = 'fisub'

    modes = collections.OrderedDict([
        (('m32int',), ('da /4', 'm', True, True)),
        (('m16int',), ('de /4', 'm', True, True)),
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
    }
    
    def generate_code(self):
        # Don't need 66h prefix for this instruction.
        # todo: could this have been deduced from the 'm16int' sig?
        if b'\x66' in self.prefixes:
            self.prefixes.remove(b'\x66')
        Instruction.generate_code(self)

    def __init__(self, src):  # set method signature
        Instruction.__init__(self, src)



class fmul(Instruction):
    """Multiplies the destination and source operands and stores the product in
    the destination location. The destination operand is always an FPU data 
    register; the source operand can be an FPU data register or a memory 
    location. Source operands in memory can be in single-precision or 
    double-precision floating-point format.
    
    ====== ======= ====== ====== =================================================
    dst    src     32-bit 64-bit description
    ====== ======= ====== ====== =================================================
           m32      X      X     ST(0) \*= src
           m64      X      X     
    st(j)  st(i)    X      X     dst \*= src  (at least one operand must be st(0))
    ====== ======= ====== ====== =================================================
    """
    name = 'fmul'

    modes = collections.OrderedDict([
        (('m32fp',), ('d8 /1', 'm', True, True)),
        (('m64fp',), ('dc /1', 'm', True, True)),
        
        (('st(0)', 'st(i)'), ('d8c8+i', '-o', True, True)),
        (('st(i)', 'st(0)'), ('dcc8+i', 'o-', True, True)),
        
        ((), ('dec9', None, True, True)),  # no-operand version is same as fmulp
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
        'o-': ['opcode +rd (r)', None],
        '-o': [None, 'opcode +rd (r)'],
    }

    
class fmulp(Instruction):
    """The FMULP instructions are similar to FMUL but perform the additional 
    operation of popping the FPU register stack after storing the product. To 
    pop the register stack, the processor marks the ST(0) register as empty and
    increments the stack pointer (TOP) by 1.

    ====== ======= ====== ====== ==============================================
    dst    src     32-bit 64-bit description
    ====== ======= ====== ====== ==============================================
    st(i)  st(0)    X      X     dst \*= st(0), pop st(0) from FP stack 
                    X      X     st(1) \*= st(0), pop st(0) from FP stack 
    ====== ======= ====== ====== ==============================================
    """
    name = 'fmulp'

    modes = collections.OrderedDict([
        (('st(i)', 'st(0)'), ('dec8+i', 'o-', True, True)),
        
        ((), ('dec9', None, True, True)),
    ])

    operand_enc = {
        'o-': ['opcode +rd (r)', None],
    }
    

class fimul(Instruction):
    """Multiplies the destination and source operands and stores the product in
    the destination location. The destination operand is always an FPU data 
    register; the source operand can be an FPU data register or a memory 
    location. Source operands in memory can be in word or doubleword integer 
    format.
    
    ======= ====== ====== ======================================================
    src     32-bit 64-bit description
    ======= ====== ====== ======================================================
    m32      X      X     ST(0) \*= src
    m64      X      X     
    ======= ====== ====== ======================================================
    """
    name = 'fimul'

    modes = collections.OrderedDict([
        (('m32int',), ('da /1', 'm', True, True)),
        (('m16int',), ('de /1', 'm', True, True)),
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
    }
    
    def generate_code(self):
        # Don't need 66h prefix for this instruction.
        # todo: could this have been deduced from the 'm16int' sig?
        if b'\x66' in self.prefixes:
            self.prefixes.remove(b'\x66')
        Instruction.generate_code(self)

    def __init__(self, src):  # set method signature
        Instruction.__init__(self, src)


class fdiv(Instruction):
    """Divides the destination operand by the source operand and stores the 
    result in the destination location. The destination operand (dividend) is 
    always in an FPU register; the source operand (divisor) can be a register 
    or a memory location. Source operands in memory can be in single-precision
    or double-precision floating-point format.
    
    ====== ======= ====== ====== ================================================
    dst    src     32-bit 64-bit description
    ====== ======= ====== ====== ================================================
           m32      X      X     ST(0) /= src
           m64      X      X     
    st(j)  st(i)    X      X     dst /= src  (at least one operand must be st(0))
    ====== ======= ====== ====== ================================================
    """
    name = 'fdiv'

    modes = collections.OrderedDict([
        (('m32fp',), ('d8 /6', 'm', True, True)),
        (('m64fp',), ('dc /6', 'm', True, True)),
        
        (('st(0)', 'st(i)'), ('d8f0+i', '-o', True, True)),
        (('st(i)', 'st(0)'), ('dcf8+i', 'o-', True, True)),
        
        ((), ('def9', None, True, True)),  # no-operand version is same as fmulp
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
        'o-': ['opcode +rd (r)', None],
        '-o': [None, 'opcode +rd (r)'],
    }

    
class fdivp(Instruction):
    """The FDIVP instructions are similar to FDIV but perform the additional 
    operation of popping the FPU register stack after storing the result. To 
    pop the register stack, the processor marks the ST(0) register as empty and
    increments the stack pointer (TOP) by 1.

    ====== ======= ====== ====== ==============================================
    dst    src     32-bit 64-bit description
    ====== ======= ====== ====== ==============================================
    st(i)  st(0)    X      X     dst /= st(0), pop st(0) from FP stack 
                    X      X     st(1) /= st(0), pop st(0) from FP stack 
    ====== ======= ====== ====== ==============================================
    """
    name = 'fdivp'

    modes = collections.OrderedDict([
        (('st(i)', 'st(0)'), ('def8+i', 'o-', True, True)),
        
        ((), ('def9', None, True, True)),
    ])

    operand_enc = {
        'o-': ['opcode +rd (r)', None],
    }
    

class fidiv(Instruction):
    """Divides the destination operand by the source operand and stores the 
    result in the destination location. The destination operand (dividend) is 
    always in an FPU register; the source operand (divisor) can be a register 
    or a memory location. Source operands in memory can be in word or 
    doubleword integer format.
    
    ======= ====== ====== ======================================================
    src     32-bit 64-bit description
    ======= ====== ====== ======================================================
    m32      X      X     ST(0) /= src
    m64      X      X     
    ======= ====== ====== ======================================================
    """
    name = 'fidiv'

    modes = collections.OrderedDict([
        (('m32int',), ('da /6', 'm', True, True)),
        (('m16int',), ('de /6', 'm', True, True)),
    ])

    operand_enc = {
        'm': ['ModRM:r/m (r)'],
    }
    
    def generate_code(self):
        # Don't need 66h prefix for this instruction.
        # todo: could this have been deduced from the 'm16int' sig?
        if b'\x66' in self.prefixes:
            self.prefixes.remove(b'\x66')
        Instruction.generate_code(self)

    def __init__(self, src):  # set method signature
        Instruction.__init__(self, src)


class fcomi(Instruction):
    """Performs an unordered comparison of the contents of registers ST(0) and
    ST(i) and sets the status flags ZF, PF, and CF in the EFLAGS register 
    according to the results (see the table below). The sign of zero is ignored 
    for comparisons, so that -0.0 is equal to +0.0.

    ================== ==== ==== ====
    Comparison         ZF   PF   CF
    ================== ==== ==== ====
    st(0) > st(i)       0    0    0
    st(0) < st(i)       0    0    1
    st(0) = st(i)       1    0    0
    unordered           1    1    1
    ================== ==== ==== ====
    
    
    ======= ====== ====== ====== ==============================================
    src1    src2   32-bit 64-bit description
    ======= ====== ====== ====== ==============================================
    st(0)   st(i)   X      X     
    ======= ====== ====== ====== ==============================================
    """
    name = 'fcomi'

    modes = collections.OrderedDict([
        (('st(0)', 'st(i)'), ('dbf0+i', '-o', True, True)),
    ])

    operand_enc = {
        '-o': [None, 'opcode +rd (r)'],
    }

    def __init__(self, src1, src2):  # set method signature
        Instruction.__init__(self, src1, src2)


class fcomip(Instruction):
    """The FCOMIP instruction is similar to FCOMI but also pops the register 
    stack following the comparison operation. To pop the register stack, the 
    processor marks the ST(0) register as empty and increments the stack 
    pointer (TOP) by 1.
    
    ======= ====== ====== ====== ==============================================
    src1    src2   32-bit 64-bit description
    ======= ====== ====== ====== ==============================================
    st(0)   st(i)   X      X     
    ======= ====== ====== ====== ==============================================
    """
    name = 'fcomip'

    modes = collections.OrderedDict([
        (('st(0)', 'st(i)'), ('dff0+i', '-o', True, True)),
    ])

    operand_enc = {
        '-o': [None, 'opcode +rd (r)'],
    }

    def __init__(self, src1, src2):  # set method signature
        Instruction.__init__(self, src1, src2)


class fucomi(Instruction):
    """The FUCOMI instruction performs the same operation as the FCOMI 
    instruction. The only difference is that the FUCOMI instruction raises the
    invalid-arithmetic-operand exception (#IA) only when either or both 
    operands are an SNaN or are in an unsupported format; QNaNs cause the 
    condition code flags to be set to unordered, but do not cause an exception
    to be generated.
    
    ======= ====== ====== ====== ==============================================
    src1    src2   32-bit 64-bit description
    ======= ====== ====== ====== ==============================================
    st(0)   st(i)   X      X     
    ======= ====== ====== ====== ==============================================
    """
    name = 'fucomi'

    modes = collections.OrderedDict([
        (('st(0)', 'st(i)'), ('dbe8+i', '-o', True, True)),
    ])

    operand_enc = {
        '-o': [None, 'opcode +rd (r)'],
    }

    def __init__(self, src1, src2):  # set method signature
        Instruction.__init__(self, src1, src2)


class fucomip(Instruction):
    """The FUCOMIP instruction is similar to FUCOMI but also pops the register 
    stack following the comparison operation. To pop the register stack, the 
    processor marks the ST(0) register as empty and increments the stack 
    pointer (TOP) by 1.
    
    ======= ====== ====== ====== ==============================================
    src1    src2   32-bit 64-bit description
    ======= ====== ====== ====== ==============================================
    st(0)   st(i)   X      X     
    ======= ====== ====== ====== ==============================================
    """
    name = 'fucomip'

    modes = collections.OrderedDict([
        (('st(0)', 'st(i)'), ('dfe8+i', '-o', True, True)),
    ])

    operand_enc = {
        '-o': [None, 'opcode +rd (r)'],
    }

    def __init__(self, src1, src2):  # set method signature
        Instruction.__init__(self, src1, src2)


# Need:
# fchs, fucompi, fxch
# fsin, fcos, fptan, fpatan, fcom, 
# mul, or, and, andn, not, xor

# avx/sse2 instructions
# addsd, subsd, mulsd, divsd, ...
# movdq2q, movq2dq



#   Testing instructions
#----------------------------------------

class cmp(Instruction):
    """Compares the first source operand with the second source operand and 
    sets the status flags in the EFLAGS register according to the results. 
    
    The comparison is performed by subtracting the second operand from the
    first operand and then setting the status flags in the same manner as the
    SUB instruction. When an immediate value is used as an operand, it is 
    sign-extended to the length of the first operand.
    
    ====== =============== ====== ====== ======================================
    src1   src2            32-bit 64-bit description
    ====== =============== ====== ====== ======================================
    r/m8   r/m8, imm8       X      X     
    r/m16  r/m16, imm8/16   X      X     
    r/m32  r/m32, imm8/32   X      X
    r/m64  r/m64, imm8/32          X
    ====== =============== ====== ====== ======================================
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

    def __init__(self, src1, src2):  # set method signature
        Instruction.__init__(self, src1, src2)


class test(Instruction):
    """Computes the bit-wise logical AND of first operand (source 1 operand) 
    and the second operand (source 2 operand) and sets the SF, ZF, and PF 
    status flags according to the result. The result is then discarded.
    
    ====== =============== ====== ====== ======================================
    src1   src2            32-bit 64-bit description
    ====== =============== ====== ====== ======================================
    r/m8   r8, imm8         X      X     
    r/m16  r16, imm8/16     X      X     
    r/m32  r32, imm8/32     X      X
    r/m64  r64, imm8/32            X
    ====== =============== ====== ====== ======================================
    """
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
    
    def __init__(self, a, b):  # set method signature
        Instruction.__init__(self, a, b)




#   Branching instructions
#----------------------------------------

class jmp(RelBranchInstruction):
    """Transfers program control to a different point in the instruction stream
    without recording return information. The destination (target) operand 
    specifies the address of the instruction being jumped to. This operand can 
    be an immediate value, a general-purpose register, or a memory location.
    
    ====== ====== ====== ===============================================
    dst    32-bit 64-bit description
    ====== ====== ====== ===============================================
    imm8    X      X     Jump to address relative to current instruction     
    imm16   X           
    imm32   X      X
    r/m16   X            Jump to absolute address stored in r/m
    r/m32   X
    r/m64          X
    ====== ====== ====== ===============================================
    """
    name = "jmp"
    
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

    def __init__(self, addr):  # set method signature
        RelBranchInstruction.__init__(self, addr)


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

    d = " Accepts an immediate address relative to the current instruction."
    return type(name, (RelBranchInstruction,), {'modes': modes, 
                                                'operand_enc': op_enc,
                                                '__doc__': doc + d}) 


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


class int_(Instruction):
    """The INT n instruction generates a call to the interrupt or exception 
    handler specified with the destination operand. The destination operand 
    specifies a vector from 0 to 255, encoded as an 8-bit unsigned intermediate
    value. Each vector provides an index to a gate descriptor in the IDT. The 
    first 32 vectors are reserved by Intel for system use. Some of these 
    vectors are used for internally generated exceptions.
    
    ====== ====== ====== ======================================
    dst    32-bit 64-bit description
    ====== ====== ====== ======================================
    imm8    X      X     
    ====== ====== ====== ======================================
    """
    name = 'int'
    
    modes = collections.OrderedDict([
        (('imm8',), ['cd ib', 'i', True, True]),
    ])
    
    operand_enc = {
        'i': ['imm8']
    }

    def __init__(self, code):  # set method signature
        Instruction.__init__(self, code)


class syscall(Instruction):
    """SYSCALL invokes an OS system-call handler at privilege level 0. It does
    so by loading RIP from the IA32_LSTAR MSR (after saving the address of the
    instruction following SYSCALL into RCX). (The WRMSR instruction ensures 
    that the IA32_LSTAR MSR always contain a canonical address.) 
    
    SYSCALL also saves RFLAGS into R11 and then masks RFLAGS using the 
    IA32_FMASK MSR (MSR address C0000084H); specifically, the processor clears
    in RFLAGS every bit corresponding to a bit that is set in the IA32_FMASK
    MSR.
    
    Accepts no operands.
    """
    name = 'syscall'
    
    modes = collections.OrderedDict([
        ((), ['0f05', None, True, True]),
    ])

    def __init__(self):  # set method signature
        Instruction.__init__(self)


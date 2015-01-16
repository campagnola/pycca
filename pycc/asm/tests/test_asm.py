# -'- coding: utf-8 -'-

from pytest import raises
from pycc.asm import *
from pycc.asm.pointer import Pointer, rex, pack_int

    
regs = {}
for name,obj in list(globals().items()):
    if isinstance(obj, Register):
        regs.setdefault('all', []).append(obj)
        regs.setdefault(obj.bits, []).append(obj)
        if 'mm' not in obj.name:
            # general-purpose registers
            regs.setdefault('gp', []).append(obj)


def itest(instr):
    """Generic instruction test: ensure that output of our function matches
    output of GNU assembler.
    
    *args* must be instruction arguments + assembler code to compare 
    as the last argument.
    """
    try:
        code1 = instr.code
        err1 = None
    except TypeError as exc:
        err1 = exc
        
    try:
        code2 = as_code(str(instr), quiet=True)
        err2 = None
    except Exception as exc:
        err2 = exc
        
    if err1 is None and err2 is None:
        if code1 == code2:
            return
        else:
            print("\n---------\n" + str(instr))
            sys.stdout.write("py:  ")
            phexbin(code1)
            sys.stdout.write("gnu: ")
            phexbin(code2)
            raise Exception("code mismatch.")
    elif err1 is not None and err2 is not None:
        return
    elif err1 is None:
        print("\n---------\n" + str(instr))
        sys.stdout.write("py:  ")
        phexbin(code1)
        print("\n" + err2.output)
        raise err2
    elif err2 is None:
        print("\n---------\n" + str(instr))
        sys.stdout.write("gnu: ")
        phexbin(code2)
        raise err1


def addresses(base):
    """Generator yielding various effective address arrangements.
    """
    for offset in regs[base.bits]:
        if offset not in regs['gp']:
            continue
        for disp in [0, 0x1, 0x100, 0x10000]:
            yield [base + disp], '[%s + 0x%x]' % (base.name, disp)
            yield [base + offset + disp], '[%s + %s + 0x%x]' % (base.name, offset.name, disp)
            yield [base + offset*2 + disp], '[%s + %s*2 + 0x%x]' % (base.name, offset.name, disp)
            yield [offset*2 + disp], '[%s*2 + 0x%x]' % (offset.name, disp)
            yield [disp], '[0x%x]' % disp


def test_effective_address():
    # test that register/scale/offset arithmetic works
    assert str(Pointer([rax])) == '[rax]'
    assert str(rax + rbx) == '[rax + rbx]'
    assert str(8*rax + rbx) == '[8*rax + rbx]'
    assert str(rbx + 4*rcx + 0x1000) == '[0x1000 + 4*rcx + rbx]'
    assert str(Pointer([0x1000])) == '[0x1000]'
    assert str(0x1000 + rcx) == '[0x1000 + rcx]'
    assert str(0x1000 + 2*rcx) == '[0x1000 + 2*rcx]'

    # test that we can generate a variety of mod_r/m+sib+disp strings
    itest(mov(edx, dword([eax])))
    itest(mov(edx, dword([ebx + eax])))
    itest(mov(edx, dword([eax*8 + ebx])))
    itest(mov(edx, dword([ebx + 4*ecx + 0x1000])))
    itest(mov(edx, dword([0x1000])))
    itest(mov(edx, dword([0x1000 + ecx])))
    itest(mov(edx, dword([0x1000 + 2*ecx])))

    # test using rbp as the SIB base
    itest(mov(edx, dword([ebp + 4*rcx + 0x1000])))
    
    # test using esp as the SIB offset
    with raises(TypeError):
        (rbx + 4*esp + 0x1000).modrm_sib(rdx)
    with raises(TypeError):
        (4*esp + 0x1000).modrm_sib(rdx)
    
    # test rex prefix:
    assert Pointer([r8]).modrm_sib(rax)[0] == rex.b


def test_generate_asm():
    # Need to be sure that str(instr) generates accurate strings or else 
    # we may get false positive tests.
    assert str(mov(rax, rbx)) == 'mov rax, rbx'
    ptypes = [
        ('', lambda x: x),
        ('byte ptr ', byte),
        ('word ptr ', word),
        ('dword ptr ', dword),
        ('qword ptr ', qword),
    ]
    for name, fn in ptypes:
        assert str(mov(rax, fn([rbx]))) == 'mov rax, %s[rbx]' % name
        assert str(mov(rax, fn([rbx+rax]))) == 'mov rax, %s[rbx + rax]' % name
        assert str(mov(rax, fn([rax+rbx]))) == 'mov rax, %s[rax + rbx]' % name
        assert str(mov(rax, fn([rax+rbx*4]))) == 'mov rax, %s[4*rbx + rax]' % name
        assert str(mov(rax, fn([rax*4+rbx]))) == 'mov rax, %s[4*rax + rbx]' % name
        assert str(mov(rax, fn([rax*4]))) == 'mov rax, %s[4*rax]' % name
        assert str(mov(rax, fn([0x100+rbx]))) == 'mov rax, %s[0x100 + rbx]' % name
        assert str(mov(rax, fn([0x100+rbx+rax]))) == 'mov rax, %s[0x100 + rbx + rax]' % name
        assert str(mov(rax, fn([0x100+rax+rbx]))) == 'mov rax, %s[0x100 + rax + rbx]' % name
        assert str(mov(rax, fn([0x100+rax+rbx*4]))) == 'mov rax, %s[0x100 + 4*rbx + rax]' % name
        assert str(mov(rax, fn([0x100+rax*4+rbx]))) == 'mov rax, %s[0x100 + 4*rax + rbx]' % name
        assert str(mov(rax, fn([0x100+rax*4]))) == 'mov rax, %s[0x100 + 4*rax]' % name
        assert str(mov(rax, fn([0x100]))) == 'mov rax, %s[0x100]' % name
    assert str(mov(rax, 1)) == 'mov rax, 1'
    assert str(mov(rax, 100)) == 'mov rax, 100'
    assert str(mov(rax, 100000000)) == 'mov rax, 100000000'

    

def test_pack_int():
    assert pack_int(0x10) == b'\x10\x00'
    assert pack_int(0x10, int8=True) == b'\x10'
    assert pack_int(0x10, int16=False) == b'\x10\x00\x00\x00'
    assert pack_int(0x1000) == b'\x00\x10'
    assert pack_int(0x100000) == b'\x00\x00\x10\x00'
    assert pack_int(0x10000000) == b'\x00\x00\x00\x10'
    assert pack_int(0x1000000000) == b'\x00\x00\x00\x00\x10\x00\x00\x00'



# Move instructions

def test_mov():
    itest(mov(eax, 0x1234567))
    itest(mov(eax, ebx))
    itest(mov(rax, 0x1234567891))
    itest(mov(rax, rbx))
    itest(mov(qword([0x12345]), rax))
    # note: these tests fail on 32-bit because GNU prefers a shorthand encoding
    # A3/A1+disp32 but the mode used on 64-bit (89/8B) should work as well. 
    #     itest(mov(dword([0x12345]), ecx))
    #     itest(mov(eax, dword([0x12345])))
    itest(mov(dword([0x12345]), ecx))
    itest(mov(rax, qword([0x12345])))
    itest(mov(ecx, dword([0x12345])))
    itest(mov(rax, qword([rbx])))
    itest(mov(rax, qword([rcx+rbx])))
    itest(mov(rax, qword([8*rbx+rcx])))
    itest(mov(rax, qword([0x1000+8*rbx+rcx])))
    itest(mov(rax, '\xdd'*8))
    itest(mov(qword([0x12345]), '\0'*8))

def test_movsd():
    itest(movsd(xmm1, [rax+rbx*4+0x1000]))
    itest(movsd([rax+rbx*4+0x1000], xmm1))
    itest(movsd(xmm1, qword([eax+ebx*4+0x1000])))
    itest(movsd(qword([eax+ebx*4+0x1000]), xmm1))


# Procedure management instructions

def test_push():
    itest(push(rcx))
    itest(push(ecx))
    itest(push([ecx]))
    itest(push([rcx]))
    itest(push(0x10))
    itest(push(0x10000))

def test_pop():
    # Note: GNU generates an encoding for pop(rcx) on 32-bit
    # even though the intel ref says this is not encodable. 
    if ARCH == 32:
        itest(pop(ebp))
        itest(pop([ecx]))
    else:
        itest(pop(rbp))
        itest(pop([rcx]))

def test_ret():
    assert ret() == as_code('ret')
    #assert ret(4) == as_code('ret 4')

def test_call():
    # relative calls
    assert call(0x0) == as_code('call .+0x0')
    assert call(-0x1000) == as_code('call .-0x1000')
    code = call('label').code
    assert code.compile({'label': 0x0, 'next_instr_addr': 5}) == as_code('label:\ncall label')
    # absolute calls
    assert call(rax) == as_code('call rax')


# Arithmetic instructions

def test_add():
    assert add(rax, rbx) == as_code('add rax, rbx')
    assert add(rbx, 0x1000) == as_code('add rbx, 0x1000')
    assert add(dword([0x1000]), eax) == as_code('add dword ptr [0x1000], eax')
    assert add(eax, dword([0x1000])) == as_code('add eax, dword ptr [0x1000]')
    #assert add([0x1000], rax) == as_code('add qword ptr [0x1000], rax')
    #assert add(rax, [0x1000]) == as_code('add rax, qword ptr [0x1000]')
    assert add(dword([0x1000]), 0x1000) == as_code('add dword ptr [0x1000], 0x1000')
    
def test_sub():
    assert sub(rax, rbx) == as_code('sub rax, rbx')
    assert sub(rbx, 0x1000) == as_code('sub rbx, 0x1000')
    assert sub(dword([0x1000]), eax) == as_code('sub dword ptr [0x1000], eax')
    assert sub(eax, dword([0x1000])) == as_code('sub eax, dword ptr [0x1000]')
    #assert add([0x1000], rax) == as_code('add qword ptr [0x1000], rax')
    #assert add(rax, [0x1000]) == as_code('add rax, qword ptr [0x1000]')
    assert sub(dword([0x1000]), 0x1000) == as_code('sub dword ptr [0x1000], 0x1000')
    
def test_dec():
    assert dec(dword([0x1000])) == as_code('dec dword ptr [0x1000]')
    assert dec(eax) == as_code('dec eax')
    assert dec(rax) == as_code('dec rax')

def test_inc():
    assert inc(dword([0x1000])) == as_code('inc dword ptr [0x1000]')
    assert inc(eax) == as_code('inc eax')
    assert inc(rax) == as_code('inc rax')

def test_imul():
    assert imul(eax, ebp) == as_code('imul eax, ebp')
    
def test_idiv():
    assert idiv(ebp) == as_code('idiv ebp')

def test_lea():
    assert lea(rax, [rbx+rcx*2+0x100]) == as_code('lea rax, [rbx+rcx*2+0x100]')
    assert lea(rax, [ebx+ecx*2+0x100]) == as_code('lea rax, [ebx+ecx*2+0x100]')
    assert lea(eax, [rbx+rcx*2+0x100]) == as_code('lea eax, [rbx+rcx*2+0x100]')
    assert lea(eax, [ebx+ecx*2+0x100]) == as_code('lea eax, [ebx+ecx*2+0x100]')

def test_fld():
    assert fld(dword([rax])) == as_code('fld dword ptr [rax]')
    assert fld(qword([rax+rcx*8])) == as_code('fld qword ptr [rax+rcx*8]')
    assert fld(st(4)) == as_code('fld st(4)')

def test_fst():
    assert fst(dword([rax])) == as_code('fst dword ptr [rax]')
    assert fst(qword([rax+rcx*8])) == as_code('fst qword ptr [rax+rcx*8]')
    assert fst(st(4)) == as_code('fst st(4)')

def test_fstp():
    assert fstp(dword([rax])) == as_code('fstp dword ptr [rax]')
    assert fstp(qword([rax+rcx*8])) == as_code('fstp qword ptr [rax+rcx*8]')
    assert fstp(st(4)) == as_code('fstp st(4)')

def test_fild():
    assert fild(word([rax])) == as_code('fild word ptr [rax]')
    assert fild(dword([rax])) == as_code('fild dword ptr [rax]')
    assert fild(qword([rax+rcx*8])) == as_code('fild qword ptr [rax+rcx*8]')

def test_fist():
    assert fist(word([rax])) == as_code('fist word ptr [rax]')
    assert fist(dword([rax])) == as_code('fist dword ptr [rax]')

def test_fistp():
    assert fistp(word([rax])) == as_code('fistp word ptr [rax]')
    assert fistp(dword([rax])) == as_code('fistp dword ptr [rax]')
    assert fistp(qword([rax+rcx*8])) == as_code('fistp qword ptr [rax+rcx*8]')

def test_fabs():
    assert fabs() == as_code('fabs')

def test_fadd():
    assert fadd() == as_code('fadd')
    assert fadd(dword([rax])) == as_code('fadd dword ptr [rax]')
    assert fadd(qword([rax])) == as_code('fadd qword ptr [rax]')
    assert fadd(st(0), st(4)) == as_code('fadd st(0), st(4)')
    assert fadd(st(4), st(0)) == as_code('fadd st(4), st(0)')
    
def test_faddp():
    assert faddp() == as_code('faddp')
    assert faddp(st(4), st(0)) == as_code('faddp st(4), st(0)')
    
def test_fiadd():
    assert fiadd(dword([rax])) == as_code('fiadd dword ptr [rax]')
    assert fiadd(word([rax])) == as_code('fiadd word ptr [rax]')
    
    
    

# Testing instructions

def test_cmp():
    assert cmp(dword(0x1000), 0x1000) == as_code('cmp dword ptr [0x1000], 0x1000')
    assert cmp(rbx, 0x1000) == as_code('cmp rbx, 0x1000')
    assert cmp(qword(rbx+0x1000), 0x1000) == as_code('cmp qword ptr [rbx+0x1000], 0x1000')

def test_test():
    assert test(eax, eax) == as_code('test eax,eax')


# Branching instructions

def test_jmp():
    assert jmp(rax) == as_code('jmp rax')
    assert jmp(0x1000) == as_code('jmp .+0x1000')    

def test_jcc():
    all_jcc = ('a,ae,b,be,c,e,z,g,ge,l,le,na,nae,nb,nbe,nc,ne,ng,nge,nl,nle,'
               'no,np,ns,nz,o,p,pe,po,s').split(',')
    for name in all_jcc:
        name = 'j' + name
        func = globals()[name]
        assert func(0x1000) == as_code('%s .+0x1000' % name)


# OS instructions

def test_syscall():
    assert syscall() == as_code('syscall')

def test_int():
    assert int_(0x80) == as_code('int 0x80')



# Extensive address encoding test
def test_push():
    for reg in regs['gp']:
        # can we push a register?
        itest(push, reg, 'push %s' % reg.name)
        
        # can we push immediate values?
        itest(push, reg, 'push %s' % reg.name)        
        
        # can we push from memory? 
        for py,asm in addresses(reg):
            itest(push, py, 'push '+asm)

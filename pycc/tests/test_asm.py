from pytest import raises
from pycc.asm import *
    

def test_effective_address():
    # test that register/scale/offset arithmetic works
    assert repr(interpret([rax])) == '[rax]'
    assert repr(rax + rbx) == '[rax + rbx]'
    assert repr(8*rax + rbx) == '[8*rax + rbx]'
    assert repr(rbx + 4*rcx + 0x1000) == '[0x1000 + 4*rcx + rbx]'
    assert repr(interpret([0x1000])) == '[0x1000]'
    assert repr(0x1000 + rcx) == '[0x1000 + rcx]'
    assert repr(0x1000 + 2*rcx) == '[0x1000 + 2*rcx]'

    # test that we can generate a variety of mod_r/m+sib+disp strings
    assert (interpret([rax])).modrm_sib(rdx) == as_code('mov rdx, qword ptr [rax]')[2:]
    assert (rbx + rax).modrm_sib(rdx) == as_code('mov rdx, qword ptr [rax + rbx]')[2:]
    assert (8*rax + rbx).modrm_sib(rdx) == as_code('mov rdx, qword ptr [rax*8 + rbx]')[2:]
    assert (rbx + 4*rcx + 0x1000).modrm_sib(rdx) == as_code('mov rdx, qword ptr [rbx + 4*rcx + 0x1000]')[2:]
    assert (interpret([0x1000])).modrm_sib(rdx) == as_code('mov rdx, qword ptr [0x1000]')[2:]
    assert (0x1000 + rcx).modrm_sib(rdx) == as_code('mov rdx, qword ptr [0x1000 + rcx]')[2:]
    assert (0x1000 + 2*rcx).modrm_sib(rdx) == as_code('mov rdx, qword ptr [0x1000 + 2*rcx]')[2:]

    # test using rbp as the SIB base
    assert (rbp + 4*rcx + 0x1000).modrm_sib(rdx) == as_code('mov rdx, qword ptr [rbp + 4*rcx + 0x1000]')[2:]
    
    # test using esp as the SIB offset
    with raises(TypeError):
        (rbx + 4*esp + 0x1000).modrm_sib(rdx)
    with raises(TypeError):
        (4*esp + 0x1000).modrm_sib(rdx)
    

def test_pack_int():
    assert pack_int(0x10) == '\x10\x00'
    assert pack_int(0x10, int8=True) == '\x10'
    assert pack_int(0x10, int16=False) == '\x10\x00\x00\x00'
    assert pack_int(0x1000) == '\x00\x10'
    assert pack_int(0x100000) == '\x00\x00\x10\x00'
    assert pack_int(0x10000000) == '\x00\x00\x00\x10'
    assert pack_int(0x1000000000) == '\x00\x00\x00\x00\x10\x00\x00\x00'



# Move instructions

def test_mov():
    assert mov(eax, 0x1234567) == as_code('mov eax,0x1234567')
    assert mov(eax, ebx) == as_code('mov eax,ebx')
    assert mov(rax, 0x1234567891) == as_code('mov rax,0x1234567891')
    assert mov(rax, rbx) == as_code('mov rax,rbx')
    assert mov([0x12345], rax) == as_code('mov qword ptr [0x12345], rax')
    assert mov([0x12345], eax) == as_code('mov dword ptr [0x12345], eax')
    assert mov(rax, [0x12345]) == as_code('mov rax, qword ptr [0x12345]')
    assert mov(eax, [0x12345]) == as_code('mov eax, dword ptr [0x12345]')
    assert mov(rax, [rbx]) == as_code('mov rax, qword ptr [rbx]')
    assert mov(rax, [rcx+rbx]) == as_code('mov rax, qword ptr [rbx+rcx]')
    assert mov(rax, [8*rbx+rcx]) == as_code('mov rax, qword ptr [8*rbx+rcx]')
    assert mov(rax, [0x1000+8*rbx+rcx]) == as_code('mov rax, qword ptr 0x1000[8*rbx+rcx]')
    
def test_movsd():
    assert movsd(xmm1, [rax+rbx*4+0x1000]) == as_code('movsd xmm1, qword ptr [rax+rbx*4+0x1000]')
    assert movsd([rax+rbx*4+0x1000], xmm1) == as_code('movsd qword ptr [rax+rbx*4+0x1000], xmm1')


# Procedure management instructions

def test_push():
    assert push(rbp) == as_code('pushq rbp')
    #assert push(rax) == as_code('push rax')

def test_pop():
    assert pop(rbp) == as_code('popq rbp')
    #assert pop(rax) == as_code('pop rax')

def test_ret():
    assert ret() == as_code('ret')
    #assert ret(4) == as_code('ret 4')

def test_call():
    assert call(0x1000) == '\xe8\x00\x10\x00\x00'  # how to specify these in
    assert call(-0x1000) == '\xe8\x00\xf0\xff\xff' # assembler??
    assert call(rax) == as_code('call rax')
    assert call(rbx) == as_code('call rbx')


# Arithmetic instructions

def test_add():
    assert add(rax, rbx) == as_code('add rax, rbx')
    assert add(rbx, 0x1000) == as_code('add rbx, 0x1000')
    assert add([0x1000], eax) == as_code('add dword ptr [0x1000], eax')
    assert add(eax, [0x1000]) == as_code('add eax, dword ptr [0x1000]')
    #assert add([0x1000], rax) == as_code('add qword ptr [0x1000], rax')
    #assert add(rax, [0x1000]) == as_code('add rax, qword ptr [0x1000]')
    assert add([0x1000], 0x1000) == as_code('add dword ptr [0x1000], 0x1000')
    
def test_dec():
    assert dec([0x1000]) == as_code('dec dword ptr [0x1000]')
    assert dec(eax) == as_code('dec eax')
    assert dec(rax) == as_code('dec rax')

def test_inc():
    assert inc([0x1000]) == as_code('inc dword ptr [0x1000]')
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


# Testing instructions

def test_cmp():
    assert cmp([0x1000], 0) == as_code('cmp dword ptr [0x1000], 0')

def test_test():
    assert test(eax, eax) == as_code('test eax,eax')


# Branching instructions

def test_jmp():
    assert jmp(rax) == as_code('jmp rax')
    assert jmp(0x1000) == as_code('jmp .+0x1000')    

def test_je():
    assert je([0x1000]) == as_code('je 0x1000')

def test_jne():
    assert jne([0x1000]) == as_code('jne 0x1000')


# OS instructions

def test_syscall():
    assert syscall() == as_code('syscall')

def test_int():
    assert int_(0x80) == as_code('int 0x80')


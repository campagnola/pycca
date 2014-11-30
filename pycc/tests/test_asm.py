from pycc.asm import *

def test_pack_int():
    assert pack_int(0x10) == '\x10\x00'
    assert pack_int(0x10, int8=True) == '\x10'
    assert pack_int(0x10, int16=False) == '\x10\x00\x00\x00'
    assert pack_int(0x1000) == '\x00\x10'
    assert pack_int(0x100000) == '\x00\x00\x10\x00'
    assert pack_int(0x10000000) == '\x00\x00\x00\x10'
    assert pack_int(0x1000000000) == '\x00\x00\x00\x00\x10\x00\x00\x00'

def test_mov():
    assert mov(eax, 0x1234567) == as_code('mov eax,0x1234567')
    assert mov(eax, ebx) == as_code('mov eax,ebx')
    assert mov(rax, 0x1234567891) == as_code('mov rax,0x1234567891')
    assert mov(rax, rbx) == as_code('mov rax,rbx')
    #assert mov(ptr(0x12345), rax) == as_code('mov dword ptr [0x12345], rax')
    #assert mov(ptr(0x12345), eax) == as_code('mov dword ptr [0x12345], eax')
    #assert mov(rax, ptr(0x12345)) == as_code('mov rax, dword ptr [0x12345]')
    #assert mov(eax, ptr(0x12345)) == as_code('mov eax, dword ptr [0x12345]')
    
def test_int():
    assert int_(0x80) == as_code('int 0x80')

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

def test_add():
    assert add(ptr(0x1000), eax) == as_code('add dword ptr [0x1000], eax')
    
def test_cmp():
    assert cmp(ptr(0x1000), 0) == as_code('cmp dword ptr [0x1000], 0')
    
def test_dec():
    assert dec(ptr(0x1000)) == as_code('dec dword ptr [0x1000]')
    assert dec(eax) == as_code('dec eax')

def test_je():
    assert je(ptr(0x1000)) == as_code('je 0x1000')

def test_jne():
    assert jne(ptr(0x1000)) == as_code('jne 0x1000')

def test_test():
    assert test(eax, eax) == as_code('test eax,eax')

def test_syscall():
    assert syscall() == as_code('syscall')

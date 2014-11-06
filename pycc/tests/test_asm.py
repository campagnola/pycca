from pycc.asm import *

def test_mov():
    assert mov(eax, 0x1234567) == as_code('mov eax,0x1234567')
    assert mov(eax, ebx) == as_code('mov eax,ebx')
    assert mov(rax, 0x1234567891) == as_code('mov rax,0x1234567891')
    assert mov(rax, rbx) == as_code('mov rax,rbx')

def test_int():
    assert int_(0x80) == as_code('int 0x80')

def test_push():
    assert push(eax) == as_code('push eax')
    assert push(rax) == as_code('push rax')

def test_pop():
    assert pop(eax) == as_code('pop eax')
    assert pop(rax) == as_code('pop rax')



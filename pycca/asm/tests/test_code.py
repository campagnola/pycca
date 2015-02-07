from pycca.asm.code import *


def test_code():
    c1 = Code(b'\0' * 8)
    c1.replace(2, 'x + 8', 'i')
    
    assert c1.compile({'x': 10}) == b'\0\0' + struct.pack('i', 18) + b'\0\0'
    
    c2 = c1 + b'\1\2'
    assert c2.compile({'x': -11}) == b'\0\0' + struct.pack('i', -3) + b'\0\0\1\2'

    c3 = b'\3\4' + c1 + b'\1\2'
    assert c3.compile({'x': 0}) == b'\3\4\0\0' + struct.pack('i', 8) + b'\0\0\1\2'

    assert (c1 + c2).compile({'x': 0}) == (b'\0\0' + struct.pack('i', 8) + b'\0\0') * 2 + b'\1\2'
    
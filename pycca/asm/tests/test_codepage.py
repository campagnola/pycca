import ctypes
from pycca.asm import *


def test_labels():
    cp = CodePage([
        label('data'),
        b'\xef\xbe\xad\xde',
        b'\xce\xfa\xad\xbe',
        label('func1'),
        mov(eax, ['data']),
        ret(),
        label('func2'),
        mov(eax, [label('data')+4]),
        ret(),
    ])
    
    fn = cp.get_function('func1')
    fn.restype = ctypes.c_uint32
    assert fn() == 0xdeadbeef

    fn = cp.get_function('func2')
    fn.restype = ctypes.c_uint32
    assert fn() == 0xbeadface
    
from pycca.asm import *
import ctypes


def test_func_return():
    fn = mkfunction([mov(eax,0xdeadbeef), ret()])
    fn.restype = ctypes.c_uint32
    assert fn() == 0xdeadbeef

def test_func_args():
    if ARCH == 32:
        return
    else:
        fn = mkfunction([
            mov(rax, argi[0]),
            ret()
        ])
        fn.restype = ctypes.c_uint64
        fn.argtypes = [ctypes.c_uint64]
        assert fn(0xdeadbeef) == 0xdeadbeef
        assert fn(0x123) == 0x123
    
    
    
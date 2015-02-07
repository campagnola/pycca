from py.test import raises

from pycca.asm import *


def test_pointer():
    p1 = Pointer([0x123])
    p2 = Pointer([rax])
    p3 = Pointer([rbx*2])
    p4 = Pointer([rax+rbx*2])
    p5 = Pointer([rax+0x123])
    p6 = Pointer([rbx*2+0x123])
    p7 = Pointer([rax+rbx*2+0x123])
    p8 = Pointer([rax+rbx])
    p9 = Pointer([rax+rbx+0x123])
    
    assert p1 == [0x123]          
    assert p2 == [rax]            
    assert p3 == rbx*2
    assert p4 == rax+rbx*2
    assert p4 == rbx*2+rax
    assert p5 == rax+0x123
    assert p5 == 0x123+rax
    assert p6 == rbx*2+0x123
    assert p6 == 0x123+rbx*2
    assert p7 == rax+rbx*2+0x123
    assert p7 == 0x123+rax+rbx*2
    assert p7 == rbx*2+0x123+rax
    assert p8 == rax+rbx
    assert p9 == rax+rbx+0x123
    assert p9 == 0x123+rax+rbx
    
    pl = Pointer(['label'])
    assert pl == label('label') + 0
    assert pl + 10 == label('label') + 10
    assert (pl + 10) + p1 == label('label') + 10 + 0x123

    with raises(TypeError):
        pl + pl
    with raises(TypeError):
        pl + p2
    with raises(TypeError):
        pl + p3
    
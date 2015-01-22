from pycca.cc import *
from pycca.asm import ARCH

def test_func_return():
    """Check that functions can return a variety of data types. 
    """
    if ARCH == 32:
        # disabled for now
        return

    c = CCode([Function('void', 'fn', [], [Return()]) ])
    assert c.fn() is None
    
    c = CCode([Function('int', 'fn', [], [Return(12)]) ])
    assert c.fn() == 12
    
    c = CCode([Function('double', 'fn', [], [Return(12.3)]) ])
    assert c.fn() == 12.3
    

def test_func_args():
    """Check that functions can accept a variety of signatures.
    """
    if ARCH == 32:
        # disabled for now
        return

    c = CCode([Function('int', 'fn', [('int', 'x')], [Return('x+2')]) ])
    assert c.fn(10) == 12
    
    c = CCode([Function('int', 'fn', [('int', 'x'), ('int', 'y')], [Return('x+y')]) ])
    assert c.fn(10, 2) == 12
    
    c = CCode([Function('double', 'fn', [('double', 'x')], [Return('x')]) ])
    assert c.fn(10.5) == 10.5
    
    c = CCode([Function('double', 'fn', [('double', 'x'), ('double', 'y')], [Return('y')]) ])
    assert c.fn(10.5, 20.3) == 20.3
    
    c = CCode([Function('double', 'fn', [('int', 'x'), ('double', 'y')], [Return('y')]) ])
    assert c.fn(10, 20.3) == 20.3
    
    
    


from pycca.cc.machinestate import MachineState
from pycca.cc.expression import Expression

def cc_expr(expr):
    e = Expression(expr)
    ms = MachineState()
    return e.compile(ms)


def test_imm():
    v = cc_expr('1')
    assert v.type == 'int'
    assert v.location == None
    assert v.init == 1
    assert v.name == None

    v = cc_expr('1.5')
    assert v.type == 'double'
    assert v.location == None
    assert v.init == 1.5
    assert v.name == None

    v = cc_expr('5 + 1.5')
    assert v.type == 'double'
    assert v.location == None
    assert v.init == 6.5
    assert v.name == None

    v = cc_expr('5 + 6')
    assert v.type == 'int'
    assert v.location == None
    assert v.init == 11
    assert v.name == None

    
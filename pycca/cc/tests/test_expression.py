from pycca.cc.machinestate import MachineState
from pycca.cc.expression import Expression
from pycca.cc.variable import Variable
from pycca import asm


def cc_expr(expr, *vars):
    e = Expression(expr)
    ms = MachineState()
    for v in vars:
        ms.add_variable(v)
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
    
    x = Variable(type='int', name='x', location=asm.rax)
    v = cc_expr('x + 3', x)
    assert v.type == 'int'
    assert v.location is not None
    assert v.init is None


def test_op_order():
    assert cc_expr('5 - 7 + 3').init == 1
    assert cc_expr('5 - (7 + 3)').init == -5
    assert cc_expr('(5 - 7) + 3').init == 1

import re
from . import instructions, register
from .pointer import Pointer
from .instruction import Label, Instruction


# Collect all registers in a single namespace for evaluating operands.
_eval_ns = {}
for name in dir(register):
    obj = getattr(register, name)
    if isinstance(obj, register.Register):
        _eval_ns[name] = obj


def parse_asm(asm):
    code = []
    ident = r'([a-zA-Z_][a-zA-Z0-9_]*)'
    instr = re.compile(r'\s*({ident}:)?({ident}\s+([^#]+))?(#.*)?'.format(ident=ident))
    
    for i,line in enumerate(asm.split('\n')):
        line = line.strip()
        if line == '':
            continue
        m = instr.match(line)
        if m is None:
            raise Exception('Parse error on assembly line %d: "%s"' % (i, line))
        _, label, _, mnem, ops, comment = m.groups()
        if label != '':
            code.append(Label(label))
            
        if mnem is None:
            continue
        
        try:
            icls = getattr(instructions, mnem)
        except AttributeError:
            raise Exception('Unsupported instruction "%s"'% mnem)
        
        ops = ops.split(',')
        args = []
        for j,op in enumerate(ops):
            op = op.strip()
            try:
                arg = eval(op, _eval_ns)
            except Exception as err:
                raise Exception('Error parsing operand %d "%s" on assembly line %d: %s' %
                                (j+1, op, i, err.message))
            args.append(arg)
        
        try:
            code.append(icls(*args))
        except Exception as err:
            raise Exception('Error creating instruction "%s %s" on assembly line %d: %s' %
                            (j+1, mnem, ops, i, err.message))
    
    return code

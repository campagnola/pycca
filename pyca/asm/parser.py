import re
from . import instructions, register, pointer
from .instruction import Label, Instruction


# Collect all registers in a single namespace for evaluating operands.
_eval_ns = {}
for name in dir(register):
    obj = getattr(register, name)
    if isinstance(obj, register.Register):
        _eval_ns[name] = obj


def parse_asm(asm):
    code = []
    eval_ns = _eval_ns.copy()
    
    # first pass: strip comments and labels
    clean = []
    for i,line in enumerate(asm.split('\n')):
        line = line.strip()
        if line == '':
            continue
        
        # strip out comments
        line, _, comment = line.partition('#')
        
        # Split line into "label: instr"
        a, part, b = line.partition(':')
        if part == '':
            line = a
        else:
            # create label if needed
            m = re.match(r'\s*([a-zA-Z_][a-zA-Z0-9_]*)', a)
            if m is None:
                raise Exception('Expected label name before ":" on assembly line %d: "%s"' % (i, line))
            label = m.groups()[0]
            clean.append(Label(label))
            line = b
            eval_ns[label] = label
        
        line = line.strip()
        if line == '':
            continue

        clean.append((i, line))
        
    # second pass: generate instructions
    for line in clean:
        if isinstance(line, Label):
            code.append(line)
            continue
        else:
            i, line = line
        
        m = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)( .*)?', line)
        if m is None:
            raise Exception('Expected instruction mnemonic on assembly line %d: "%s"' % (i, line))
        
        mnem, ops = m.groups()
        
        # Get instruction class
        try:
            icls = getattr(instructions, mnem)
        except AttributeError:
            raise Exception('Unsupported instruction "%s"'% mnem)
        
        # Use python eval to parse operands
        args = []
        if ops is not None:
            ops = ops.split(',')
            for j,op in enumerate(ops):
                op = op.strip()
                
                # parse pointer size
                m = re.match(r'((byte|word|dword|qword)\s+ptr )?(.*)', op)
                _, ptype, op = m.groups()
                
                # eval operand
                try:
                    arg = eval(op, eval_ns)
                except Exception as err:
                    raise Exception('Error parsing operand %d "%s" on assembly line %d: %s' %
                                    (j+1, op, i, err.message))
                
                # apply pointer size if requested
                if ptype is not None:
                    arg = getattr(pointer, ptype)(arg)
                    
                args.append(arg)
        
        # Create instruction
        try:
            code.append(icls(*args))
        except Exception as err:
            raise Exception('Error creating instruction "%s %s" on assembly line %d: %s' %
                            (j+1, mnem, ops, i, err.message))
    
    return code

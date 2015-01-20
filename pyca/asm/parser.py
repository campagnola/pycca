import re
from . import instructions, register, pointer
from .instruction import Label, Instruction


# Collect all registers in a single namespace for evaluating operands.
_eval_ns = {'st': register.st}
for name in dir(register):
    obj = getattr(register, name)
    if isinstance(obj, register.Register):
        _eval_ns[name] = obj


def parse_asm(asm, namespace=None):
    """Parse assembly code and return a list of code objects that may be used
    to construct a CodePage.
    
    The *namespace* argument may a dict that defines symbols used in the 
    assembly.
    """
    code = []
    eval_ns = _eval_ns.copy()
    if namespace is not None:
        eval_ns.update(namespace)
        
    # first pass: strip comments and labels
    clean = []
    for i,line in enumerate(asm.split('\n')):
        lineno = i + 1
        line = line.strip()
        origline = line
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
                raise SyntaxError('Expected label name before ":" on assembly '
                                  'line %d: "%s"' % (lineno, origline))
            label = m.groups()[0]
            clean.append(Label(label))
            line = b
            if label in eval_ns:
                raise NameError('Duplicate symbol "%s" on assembly line %d: "%s"'
                                % (label, lineno, origline))
                
            eval_ns[label] = label
        
        line = line.strip()
        if line == '':
            continue

        clean.append((lineno, line, origline))
        
    # second pass: generate instructions
    for line in clean:
        if isinstance(line, Label):
            code.append(line)
            continue
        else:
            lineno, line, origline = line
        
        m = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)( .*)?$', line)
        if m is None:
            raise SyntaxError('Expected instruction mnemonic on assembly line %d:'
                              ' "%s"' % (lineno, origline))
        
        mnem, ops = m.groups()
        mnem = mnem.strip()
        
        # Get instruction class
        try:
            icls = getattr(instructions, mnem)
        except AttributeError:
            raise NameError('Unknown instruction "%s" on assembly line %d:' %
                            (mnem, lineno))
        
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
                    arg = eval(op, {'__builtins__': {}}, eval_ns)
                except Exception as err:
                    raise type(err)('Error parsing operand "%s" on assembly line'
                                    ' %d:\n    %s' % (op, lineno, str(err)))
                
                # apply pointer size if requested
                if ptype is not None:
                    arg = getattr(pointer, ptype)(arg)
                    
                args.append(arg)
        else:
            ops = ''
        
        # Create instruction
        try:
            inst = icls(*args)
            # generate an error here if there is a compile problem:
            inst.code
            code.append(inst)
        except Exception as err:
            raise type(err)('Error creating instruction "%s %s" on assembly line'
                            ' %d:\n    %s' % (mnem, ops, lineno, str(err)))
    
    return code

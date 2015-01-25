import struct, re, operator
from .variable import Variable, Constant
from .. import asm


class Expression(object):
    def __init__(self, expr):
        self.expr = expr
        
    def compile(self, state):
        """Compile this expression, adding code to the MachineState as needed.
        
        Return a Variable containing the result of the expression.
        """
        
        # First tokenize the expression string
        if isinstance(self.expr, (int, float)):
            tokens = [self.expr]
        else:
            tokens = self._tokenize(state)
        #return tokens
        
        # next group the tokens into a hierarchy of operators & operands.
        groups = self._group(tokens)
        #return groups
        
        # finally, compile the hierarchy in order and return the result
        return self._compile_subexpr(groups, state)
    
    def _compile_subexpr(self, group, state):
        """Compile a sub-expression and return a Variable containing the 
        output.
        """
        code = []
        args = group.args
        operands = []
        
        for arg in args:
            if arg is None:
                continue
            if isinstance(arg, TokGrp):
                var = self._compile_subexpr(arg, state)
                operands.append(var)
            elif isinstance(arg, Variable):
                operands.append(arg)
            else:
                raise TypeError("Invalid expression operand : %r" % arg)
        
        if group.op is None and len(operands) == 1:
            assert isinstance(operands[0], Variable)
            return operands[0]
        elif (len(operands) == 2 and isinstance(operands[0], Constant) and
              isinstance(operands[1], Constant)):
            fn = {'+': operator.add, '-': operator.sub}[group.op]
            val = fn(operands[0].init, operands[1].init)
            print operands[0].init, operands[1].init, val
            return Constant(val, group.type)
        elif group.op == '+':
            code.append(asm.add(*operands))
            location = operands[0]
        elif group.op == '-':
            code.append(asm.sub(*operands))
            location = operands[0]
        elif group.op == '*':
            code.append(asm.imul(*operands))
            location = operands[0]
        else:
            raise NotImplementedError('operand: %s' % group.op)
        
        state.add_code(code)
        return Variable(type=group.type, location=location)
    
    def _tokenize(self, state):
        # Parse expression into tokens
        tokens = []
        expr = self.expr
        while len(expr) > 0:
            expr = expr.lstrip()
            
            # Check for operators
            if expr[0] in '+-*/()':
                tokens.append(expr[0])
                expr = expr[1:]
                continue
            
            # check for identifiers
            m = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)(.*)', expr)
            if m is not None:
                tokens.append(state.get_var(m.groups()[0]))
                expr = m.groups()[1]
                continue
            
            # check for immediate values
            m = re.match(r'(-?(([0-9]+(\.[0-9]*)?)|(([0-9]*\.)?[0-9]+))(e-?[0-9]+)?)(.*)', expr)
            if m is not None:
                const = Constant(eval(m.groups()[0]))
                tokens.append(const)
                expr = m.groups()[-1]
                continue
            
        return tokens

    def _group(self, tokens):
        # parse a list of tokens into nested groups containing no more than
        # one operand per group.
        op_order =  '*/+-'
        unary_ops = '-'
        
        group = TokGrp()
        while len(tokens) > 0:
            tok = tokens.pop(0)
            #print tok
            if tok == '(':
                if group.accepts_arg:
                    newgrp = TokGrp(parent=group)
                    group.add_arg(newgrp)
                    group = newgrp
                else:
                    raise TypeError("Parse error in expression %s")
            elif tok == ')':
                if group.parent is not None:
                    group = group.parent
            elif isinstance(tok, str):
                if group.op is None:
                    group.set_op(tok)
                else:
                    # need a new group. Decide how to handle nesting:
                    
                    if op_order.index(group.op) > op_order.index(tok):
                        # insert new group inside current group
                        newgrp = TokGrp(op=tok, arg1=group.args[1], parent=group)
                        group.args[1] = newgrp
                        group = newgrp
                    else:
                        # insert current group into new group
                        newgrp = TokGrp(op=tok, arg1=group, parent=group.parent)
                        group.parent = newgrp
                        group = newgrp
            else:
                if group.accepts_arg:
                    group.add_arg(tok)
                else:
                    raise TypeError("Parse error in expression %s")
                
            root_group = group
            while True:
                parent = root_group.parent
                if parent is None:
                    break
                else:
                    root_group = parent
            #print root_group
        return root_group

            
class TokGrp(object):
    def __init__(self, parent=None, op=None, arg1=None, arg2=None, binary=True):
        self.parent = parent
        self.binary = binary
        self.op = op
        self.args = [arg1, arg2]
        
    @property
    def type(self):
        argtyps = []
        for arg in self.args:
            if isinstance(arg, (TokGrp, Variable)):
                argtyps.append(arg.type)
            elif isinstance(arg, int):
                argtyps.append('int')
            elif isinstance(arg, float):
                argtyps.append('double')
        argtyps.sort()
            
        if argtyps[0] == argtyps[1]:
            return argtyps[0]
        elif 'double' in argtyps:
            return 'double'
        else:
            raise NotImplementedError("Can't determine expression type: %s" % self.args)
        
    @property
    def accepts_arg(self):
        """Return True if the group will allow another argument to be added.
        """
        return self.args[1] is None
        
    def add_arg(self, arg):
        if self.binary and self.args[0] is None:
            self.args[0] = arg
        else:
            self.args[1] = arg

    def set_op(self, op):
        assert self.op is None
        self.op = op
        if self.args[0] is None:
            self.binary = False

    def __str__(self):
        if self.binary:
            if self.op is None and self.args[1] is None:
                return str(self.args[0])
            else:
                return '(%s %s %s)' % (self.args[0], self.op, self.args[1])
        else:
            return '(%s %s)' % (self.op, self.args[1])



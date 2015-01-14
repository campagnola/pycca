import struct, re
from .variable import Variable
from .codeobject import CodeObject, CodeContainer
from .. import asm


class Expression(CodeObject):
    def __init__(self, expr):
        CodeObject.__init__(self)
        self.expr = expr
        self.type = None
        # name introduced into scope to reference the result of this expression
        #self.name = "%s_%x" % (self.__class__.__name__, id(self))
        
    def compile(self, scope):
        if isinstance(self.expr, (int, float)):
            tokens = [self.expr]
        else:
            tokens = self._tokenize(scope)
        #return tokens
        groups = self._group(tokens)
        self.type = groups.type
        #return groups
        code, location = self._compile_subexpr(groups, scope)
        #scope[self.name] = Variable('int', self.name, reg=location)
        self.location = location
        
        return code
    
    def _compile_subexpr(self, group, scope):
        code = []
        args = group.args
        ops = []
        
        for arg in args:
            if arg is None:
                continue
            if isinstance(arg, TokGrp):
                c, loc = self._compile_subexpr(arg, scope)
                code.extend(c)
                ops.append(loc)
            elif isinstance(arg, Variable):
                ops.append(arg.location)
            else:
                ops.append(arg)
        
        if group.op is None and len(ops) == 1:
            if isinstance(ops[0], (asm.Register, asm.Pointer)):
                location = ops[0]
            elif isinstance(ops[0], int):
                code.append(asm.mov(asm.rax, ops[0]))
                location = asm.rax
            elif isinstance(ops[0], float):
                code.extend([
                    asm.mov(asm.rax, struct.pack('d', ops[0])),
                    asm.mov([asm.rsp-8], asm.rax),
                    asm.movsd(asm.xmm0, [asm.rsp-8])
                ])
                location = asm.xmm0
            else:
                raise TypeError("Unsupported expression type:", ops[0])
        elif group.op == '+':
            code.append(asm.add(*ops))
            location = ops[0]
        else:
            raise NotImplementedError('operand: %s' % group.op)
            
        return code, location
    
    def _tokenize(self, scope):
        # Parse expression into tokens
        tokens = []
        expr = self.expr
        while len(expr) > 0:
            expr = expr.lstrip()
            if expr[0] in '+-*/()':
                tokens.append(expr[0])
                expr = expr[1:]
                continue
            m = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)(.*)', expr)
            if m is not None:
                tokens.append(scope[m.groups()[0]])
                expr = m.groups()[1]
                continue
            m = re.match(r'(-?(([0-9]+(\.[0-9]*)?)|(([0-9]*\.)?[0-9]+))(e-?[0-9]+)?)(.*)', expr)
            if m is not None:
                tokens.append(eval(m.groups()[0]))
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
        # todo: decide when to do automatic type casting
        if isinstance(self.args[0], (TokGrp, Variable)):
            return self.args[0].type
        elif isinstance(self.args[0], int):
            return 'int'
        elif isinstance(self.args[0], float):
            return 'float'
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


class _SubExpr(object):
    def __init__(self, arg1, op=None, arg2=None):
        self.arg1 = arg1
        self.op = op
        self.arg2 = arg2
        
        # compile simple expression
        self.location = arg1.location
        
        self.code = []
        if op == '+':
            self.code = [asm.add(arg1.location, arg2)]
            

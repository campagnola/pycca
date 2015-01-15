# -*- coding: utf-8 -*-
import ctypes

from .variable import Variable
from .expression import Expression
from .codeobject import CodeObject, CodeContainer
from .. import asm


def decl(type, name, init=None):
    return Declaration(type, name, init)
    
class Declaration(CodeObject):
    def __init__(self, type, name, init):
        CodeObject.__init__(self)
        self.var = Variable(type, name, init)
        current_scope.declare(var)


def func(rtype, name, *args):
    return Function(rtype, name, *args)

class Function(CodeContainer):
    ctype_map = {
        'void': None,
        'int': ctypes.c_int,
        'double': ctypes.c_double,
    }
    
    def __init__(self, rtype, name, args, code):
        CodeContainer.__init__(self, code)
        self.rtype = rtype
        self.name = name
        self.args = args

    @property
    def c_restype(self):
        return self.ctype_map[self.rtype]
    
    @property
    def c_argtypes(self):
        types = []
        for argtype, argname in self.args:
            types.append(self.ctype_map[argtype])
        return types

    def compile(self, scope):
        scope[self.name] = self
        
        scope = scope.copy()
        
        # load function args into scope
        argi = [asm.rdi, asm.rsi, asm.rdx, asm.rcx, asm.r8, asm.r9]
        argf = [asm.xmm0, asm.xmm1, asm.xmm2, asm.xmm3, asm.xmm4, asm.xmm5, asm.xmm6, asm.xmm7]
        stackp = 0
        for argtype, argname in self.args:
            # todo: only works for single int arg
            if argtype == 'int':
                if len(argi) > 0:
                    loc = argi.pop(0)
                else:
                    stackp -= 4
                    loc = [asm.rbp + stackp]
            elif argtype == 'double':
                if len(argf) > 0:
                    loc = argf.pop(0)
                else:
                    stackp -= 4
                    loc = [asm.rbp + stackp]
            else:
                raise TypeError('arg type %s not supported.' % argtype)
            var = Variable(argtype, argname, reg=loc)
            scope[argname] = var
        
        code = [asm.label(self.name)]
        
        for item in self.code:
            code.extend(item.compile(scope))
            
        code.append(asm.ret())
        return code


class Assign(CodeObject):
    def __init__(self, **kwds):
        CodeObject.__init__(self)
        self.assignments = kwds
        
    def compile(self, scope):
        code = []
        for name, expr in self.assignments.items():
            expr = Expression(expr)
            code.extend(expr.compile(scope))
            scope[name].set_location(expr.location)
        return code


class Return(CodeObject):
    def __init__(self, expr=None):
        CodeObject.__init__(self)
        self.expr = expr
        
    def compile(self, scope):
        code = []
        if self.expr is not None:
            expr = Expression(self.expr)
            code.extend(expr.compile(scope))
        
            if expr.type == 'int' and expr.location is not asm.rax:
                code.append(asm.mov(asm.rax, expr.location))
            elif expr.type == 'double' and expr.location is not asm.xmm0:
                code.append(asm.movsd(asm.xmm0, expr.location))
            
        # code.append(asm.ret())  # Function handles this part.
        return code
        

    

def call(func, *args):
    return FunctionCall(func, *args)

class FunctionCall(CodeObject):
    def __init__(self, func, *args):
        CodeObject.__init__(self)
        self.func = func
        self.args = args


def forloop(init, cond, update):
    return ForLoop(init, cond, update)

def whileloop(cond):
    return WhileLoop(cond)

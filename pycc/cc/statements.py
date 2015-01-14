# -*- coding: utf-8 -*-
from .variable import Variable
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
    def __init__(self, rtype, name, args, code):
        CodeContainer.__init__(self, code)
        self.rtype = rtype
        self.name = name
        self.args = args

    def compile(self, scope):
        scope[self.name] = self
        
        scope = scope.copy()
        
        # load function args into scope
        for argtype, argname in self.args:
            # todo: only works for single int arg
            var = Variable(argtype, argname, reg=asm.rax)
            scope[argname] = var
        
        code = [asm.label(self.name)]
        
        for item in self.code:
            code.extend(item.compile(scope))
            
        code.append(asm.ret())
        return code


class Assignment(CodeObject):
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


class Expression(CodeObject):
    def __init__(self, expr):
        CodeObject.__init__(self)
        self.expr = expr
        # name introduced into scope to reference the result of this expression
        self.name = "%s_%x" % (self.__class__.__name__, id(self))
        
    def compile(self, scope):
        xloc = scope['x'].location
        code = [
            asm.add(xloc, 1),
        ]
        scope[self.name] = Variable('int', self.name, reg=xloc)
        self.location = xloc
        return code


class Return(CodeObject):
    def __init__(self, expr):
        CodeObject.__init__(self)
        self.expr = expr
        
    def compile(self, scope):
        code = []
        expr = Expression(self.expr)
        code.extend(expr.compile(scope))
        
        if expr.location is not asm.rax:
            code.append(asm.mov(asm.rax, code.location))
            
        code.append(asm.ret())
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

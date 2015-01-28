# -*- coding: utf-8 -*-
import ctypes

from .variable import Variable
from .expression import Expression
from .. import asm

class CodeObject(object):
    pass


def decl(type, name, init=None):
    return Declaration(type, name, init)
    
class Declaration(CodeObject):
    def __init__(self, type, name, init):
        CodeObject.__init__(self)
        self.var = Variable(type, name, init)

    def compile(self, state):
        state.add_variable(self.var)


def func(rtype, name, *args):
    return Function(rtype, name, *args)

class Function(CodeObject):
    ctype_map = {
        'void': None,
        'int': ctypes.c_int,
        'double': ctypes.c_double,
    }
    
    def __init__(self, rtype, name, args, code):
        CodeObject.__init__(self)
        self.code = code
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

    def compile(self, state):
        state.add_function(self)
        
        with state.enter_local():
        
            # load function args into scope
            argi = [asm.rdi, asm.rsi, asm.rdx, asm.rcx, asm.r8, asm.r9]
            argf = [asm.xmm0, asm.xmm1, asm.xmm2, asm.xmm3, asm.xmm4, asm.xmm5, asm.xmm6, asm.xmm7]
            stackp = 0
            for argtype, argname in self.args:
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
                state.add_variable(var)
            
            # Compile function contents
            state.add_code([asm.label(self.name)])
            
            # todo: prologue, epilogue
            for item in self.code:
                item.compile(state)
            
            state.add_code([asm.ret()])


class Assign(CodeObject):
    def __init__(self, **kwds):
        CodeObject.__init__(self)
        self.assignments = kwds
        
    def compile(self, state):
        code = []
        for name, expr in self.assignments.items():
            expr = Expression(expr)
            result = expr.compile(state)
            var = state.get_var(name)
            loc = result.get_location(state)
            state.set_var_location(var, loc)
            
        state.add_code(code)


class Return(CodeObject):
    def __init__(self, expr=None):
        CodeObject.__init__(self)
        self.expr = expr
    
    def compile(self, state):
        if self.expr is not None:
            expr = Expression(self.expr)
            result = expr.compile(state)
            
            fn = state.current_function()
            restype = fn.return_type
            if result.type != restype:
                raise TypeError("Function requires return type %s; got %s" % 
                                (restype, result.type))
            
            if restype == 'int':
                state.move(asm.rax, result)
            elif restype == 'double':
                state.move(asm.xmm0, result)
    

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

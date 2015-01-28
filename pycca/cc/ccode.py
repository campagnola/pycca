# -*- coding: utf-8 -*-
import ctypes
from ..asm import CodePage
from .machinestate import MachineState
from .statements import Function

class CCode(object):
    def __init__(self, code):
        self.code = code
        self.compiled = False
        self.asm = None
        self.codepage = None
        self.compile()
        
    def compile(self):
        state = MachineState()
        for item in self.code:
            item.compile(state)

        self.codepage = CodePage(state.asm)
        
        for name, obj in state.globals.items():
            if isinstance(obj, Function):
                func = self.codepage.get_function(obj.name)
                func.restype = obj.c_restype
                func.argtypes = obj.c_argtypes
                func.name = obj.name
                setattr(self, obj.name, func)
        
    def dump_asm(self):
        return self.codepage.dump()

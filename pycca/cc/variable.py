# -*- coding: utf-8 -*-
from ..asm import Register, Pointer


types = ['int', 'double']

class Variable(object):
    def __init__(self, type, name=None, init=None, addr=None, reg=None, location=None):
        self.type = type
        if type not in types:
            raise TypeError('Invalid data type "%s"' % type)
        self.name = name
        self.init = init
        
        if isinstance(location, Register):
            assert reg is None
            reg = location
        elif isinstance(location, int):
            assert addr is None
            addr = location
        
        self.reg = reg
        self.addr = addr
            
            

    @property
    def location(self):
        if self.reg is not None:
            return self.reg
        elif self.addr is not None:
            return self.addr
        else:
            raise RuntimeError("Variable %s has no location." % self.name)
        
    def set_location(self, loc):
        if isinstance(loc, Register):
            self.reg = loc
        
        else:
            raise TypeError("Currently only reg supported for set_location.")

    def __repr__(self):
        return self.name
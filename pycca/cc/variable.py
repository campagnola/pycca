# -*- coding: utf-8 -*-
import struct

from ..asm import Register, Pointer
from .. import asm

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
            return None
        
    def set_location(self, loc):
        if isinstance(loc, Register):
            self.reg = loc
        else:
            raise TypeError("Invalid variable location: %r" % loc)

    def get_location(self, state):
        """Return location of this variable.
        
        If the variable has no location, then the machine state is modified 
        to generate a location.
        """
        loc = self.location
        if loc is not None:
            return loc
        if self.init is None:
            raise RuntimeError("%r has no location or value." % self)
        
        if self.type == 'int':
            reg = state.free_register()
            state.add_code([asm.mov(reg, self.init)])
            return reg
        else:
            raise NotImplementedError()
        
    def get_pointer(self, state):
        """Return a memory pointer for this variable. 
        
        If the variable is immediate, then the value will be stored alongside
        the machine code. If the variable only exists in a register, then an
        exception is raised.
        """
        if self.addr is None:
            if self.init is None:
                raise TypeError("Cannot get memory address for %s" % self)
            data = struct.pack(self.struct_typ, self.init)
            label = state.add_data(name=None, data=data)
            self.addr = Pointer(label=label)
        return self.addr

    @property
    def struct_typ(self):
        """Return a type code appropriate for encoding this variable using
        struct.pack().
        """
        return {
            'int': 'i',
            'double': 'd',
        }[self.type]

    @property
    def operand_type(self):
        """Return a code indicating the operand type for this variable:
        
        i=immediate, r=register, m=memory, ...
        """
        if self.reg is not None:
            return 'r'
        elif self.addr is not None:
            return 'm'
        else:
            return None

    def get_operand(self, types):
        """Return a representation of this variable that can be used as an 
        assembly instruction operand. 
        
        The type returned depends on *types*, which is a string composed of
        'i', 'r', and 'm'.
        """
        typ = self.operand_type
        if typ == 'i' and 'i' in types:
            if self.type == 'double':
                return struct.pack('d', self.init)
            else:
                return self.init
        elif typ == 'r' and 'r' in types:
            return self.reg
        elif typ == 'm' and 'm' in types:
            return self.addr
        else:
            raise NotImplementedError("Convert variable type %s to operand type %s" % (typ, typs))

    def get_register(self, state, type='gp'):
        """Return the register where this variable is stored, if available.
        If not, move the variable to a register first.
        """
        if self.reg is not None:
            return self.reg
        raise NotImplementedError()

    def __repr__(self):
        return '%s(name=%s, loc=%s, init=%s)' % (self.__class__.__name__, 
                                                 self.name, self.location, 
                                                 self.init)
    
    
class Constant(Variable):
    def __init__(self, value, type=None):
        if type is None:
            if isinstance(value, (int, long)):
                type = 'int'
            elif isinstance(value, float):
                type = 'double'

        Variable.__init__(self, name=None, type=type, init=value)

    @property
    def operand_type(self):
        typ = Variable.operand_type.fget(self)
        if typ is None:
            return 'i'
        return typ
        

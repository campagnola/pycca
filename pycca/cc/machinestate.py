# -*- coding: utf-8 -*-
import logging as log
from .. import asm

class MachineState(object):
    """Tracks / manages machine state during compile:

    * Global & local scopes
    * Register availability
    * Moving variables to/from registers 
    * Accumulates assembly and data
    """
    def __init__(self):
        self.asm = []
        self.data = []
        self.locals = None
        self.globals = {}
        self.registers = {}
        self.anon_id = 0
    
    @property
    def scope(self):
        if self.locals is not None:
            return self.locals
        return self.globals
    
    def get_register(self, var):
        """Return the register where *var* can be accessed.
        
        If *var* is not present in a register, then code will be added to move
        it.
        """
        if var.reg is None:
            if var.addr is None:
                raise NotImplementedError("Variable has no register or address; can't handle this yet..")
            reg = self.free_register(var.regtype, var.size)
            self.add_code([asm.mov(reg, var.addr)])
            var.reg = reg
        return var.reg
    
    def free_register(self, type='gp', bits=None):
        """Return a register that is available for use. 
        
        If no registers are available, then code is added to move a value out
        to memory.
        """
        for reg in all_registers(type, bits):
            if reg not in self.registers:
                return reg
        
        raise NotImplementedError('All registers in use; swap to stack not implemented yet.')

    def update_register(self, reg, var):
        """Update the machine to transfer ownership of *reg* to *var*.
        """
        log.info('Update register %s => %s' % (reg, var))
        var.reg = reg
        if reg in self.registers:
            oldvar = self.registers[reg]
            if oldvar.reg is reg:
                oldvar.reg = None
                log.info('  (taken from %s)' % oldvar)
        self.registers[reg] = var
    
    def set_var_location(self, var, loc):
        """Update var to have a new location.
        """
        var.set_location(loc)
        if isinstance(loc, asm.Register):
            self.update_register(loc, var)
    
    def add_variable(self, var):
        """Add a new variable to the current scope.
        """
        log.info('Add var %s' % (var))
        if var.name is None:
            var.name = 'anon_%d' % self.anon_id
            self.anon_id += 1
        if var.name in self.globals or (self.locals is not None and var.name in self.locals):
            raise NameError('Variable "%s" already declared.' % var.name)
        self.scope[var.name] = var
        if var.reg is not None:
            self.update_register(var.reg, var)
        
    def add_function(self, func):
        """Add a new function to the global scope.
        """
        log.info('Add func %s' % (func))
        if self.locals is not None:
            raise RuntimeError("Cannot declare function while inside previous function definition.")
        if func.name in self.globals:
            raise NameError('Name "%s" already declared.' % var.name)
        self.globals[func.name] = func
 
    def add_global(self, var):
        """Add a global variable.
        """
        self.globals[var.name] = var
 
    def enter_local(self):
        """Return a context manager that creates a new local scope in the
        machine state.
        
        When the context exits, the local scope will be cleared.
        """
        return LocalScope(self)
    
    def add_code(self, code):
        """Extend the assembly code 
        """
        if len(code) == 0:
            return
        log.info('Add code:\n%s' % '\n'.join([(' '*14)+str(i) for i in code]))
        self.asm.extend(code)
        
    def get_var(self, name):
        if self.locals is not None and name in self.locals:
            return self.locals[name]
        elif name in self.globals:
            return self.globals[name]
        else:
            raise NameError('Undefined name "%s".' % name)

    def move(self, dest, var):
        """Move the variable *var* to the register or memory address *dest*.
        """
        
        if var.operand_type == 'i':
            if var.type == 'int':
                state.add_code([asm.mov(dest, var.init)])
            elif var.type == 'double':
                reg = state.free_register(type='gp', size=64)
                state.add_code([
                    asm.mov(reg, result.get_operand()),
                    asm.movsd(asm.xmm0, reg)
                ])
            else:
                raise NotImplementedError('move %s, %s' % (dest, var))
        else:
            if var.type == 'int':
                if var.location is dest:
                    return
                state.add_code([asm.mov(dest, var.location)])
                state.update_register(dest, var)
                return
            elif var.type == 'double':
                state.add_code([asm.movsd(asm.xmm0, result.location)])
                state.update_register(asm.xmm0, result)
            else:
                raise NotImplementedError('move %s, %s' % (dest, var))
            
        


class LocalScope(object):
    def __init__(self, state):
        self.state = state
        
    def __enter__(self):
        log.info('Enter local scope')
        if self.state.locals is not None:
            raise RuntimeError("Cannot enter new scope; another is already active.")
        self.state.locals = {}
        return self
    
    def __exit__(self, *args):
        log.info('Exit local scope')
        for var in self.state.locals.values():
            if var.reg is None:
                continue
            var2 = self.state.registers.pop(var.reg)
            if var2 is not var:
                raise RuntimeError("Variable and MachineState register mismatch:"
                                   "\n%s and %s claim register %s." % (var, var2, var.reg))
        self.state.locals = None


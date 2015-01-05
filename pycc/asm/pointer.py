
class Pointer(object):
    """Representation of an effective memory address calculated as a 
    combination of values::
    
        ebp-0x10   # 16 bytes lower than base pointer
        0x1000 + 8*eax + ebx
    """
    def __init__(self, reg1=None, scale=None, reg2=None, disp=None):
        self.reg1 = reg1
        self.scale = scale
        self.reg2 = reg2
        self.disp = disp
        self._bits = None
    
    def copy(self):
        return Pointer(self.reg1, self.scale, self.reg2, self.disp)

    #@property
    #def addrsize(self):
        #"""Maximum number of bits for encoded address size.
        #"""
        #regs = []
        #if self.reg1 is not None:
            #regs.append(self.reg1.bits)
        #if self.reg2 is not None:
            #regs.append(self.reg2.bits)
        #if self.disp is not None:
            #if len(regs) == 0:
                
                #return ARCH
            #regs.append(32)
        #return max(regs)
    @property
    def prefix(self):
        """Return prefix string required when encoding this address.
        
        The value returned will be either '' or '\x67'
        """
        regs = []
        if self.reg1 is not None:
            regs.append(self.reg1.bits)
        if self.reg2 is not None:
            regs.append(self.reg2.bits)
        if len(regs) == 0:
            return ''
        if max(regs) == ARCH//2:
            return '\x67'
        return ''
        
    @property
    def bits(self):
        """The size of the data referenced by this pointer.
        """
        if self._bits is None:
            return ARCH
        else:
            return self._bits
        
    @bits.setter
    def bits(self, b):
        self._bits = b

    def __add__(self, x):
        y = self.copy()
        if isinstance(x, Register):
            if y.reg1 is None:
                y.reg1 = x
            elif y.reg2 is None:
                y.reg2 = x
            else:
                raise TypeError("Pointer cannot incorporate more than"
                                " two registers.")
        elif isinstance(x, int):
            if y.disp is None:
                y.disp = x
            else:
                y.disp += x
        elif isinstance(x, Pointer):
            if x.disp is not None:
                y = y + x.disp
            if x.reg2 is not None:
                y = y + x.reg2
            if x.reg1 is not None and x.scale is None:
                y = y + x.reg1
            elif x.reg1 is not None and x.scale is not None:
                if y.scale is not None:
                    raise TypeError("Pointer can only hold one scaled"
                                    " register.")
                if y.reg1 is not None:
                    if y.reg2 is not None:
                        raise TypeError("Pointer cannot incorporate more than"
                                        " two registers.")
                    # move reg1 => reg2 to make room for a new reg1*scale
                    y.reg2 = y.reg1
                y.reg1 = x.reg1
                y.scale = x.scale
            
        return y

    def __radd__(self, x):
        return self + x

    def __repr__(self):
        return "Pointer(%s)" % str(self)

    def __str__(self):
        parts = []
        if self.disp is not None:
            parts.append('0x%x' % self.disp)
        if self.reg1 is not None:
            if self.scale is not None:
                parts.append("%d*%s" % (self.scale, self.reg1.name))
            else:
                parts.append(self.reg1.name)
        if self.reg2 is not None:
            parts.append(self.reg2.name)
        ptr = '[' + ' + '.join(parts) + ']'
        if self._bits is None:
            return ptr
        else:
            pfx = {8: 'byte', 16: 'word', 32: 'dword', 64: 'qword'}[self._bits]
            return pfx + ' ptr ' + ptr

    def modrm_sib(self, reg=None):
        """Generate a string consisting of mod_reg_r/m byte, optional SIB byte,
        and optional displacement bytes.
        
        The *reg* argument is placed into the modrm.reg field.
        
        Return tuple (rex, code).
        
        Note: this method implements many special cases required to match 
        GNU output:
        * Using ebp/rbp/r13 as r/m or as sib base causes addition of an 8-bit
          displacement (0)
        * For [reg1+esp], esp is always moved to base
        * Special encoding for [*sp]
        * Special encoding for [disp]
        """
        # check address size is supported
        for r in (self.reg1, self.reg2):
            if r is not None and r.bits < ARCH//2:
                raise TypeError("Invalid register for pointer: %s" % r.name)

        # do some simple displacement parsing
        if self.disp in (None, 0):
            disp = ''
            mod = 'ind'
        else:
            disp = pack_int(self.disp, int8=True, int16=False, int32=True, int64=False)
            mod = {1: 'ind8', 4: 'ind32'}[len(disp)]

        if self.scale in (None, 0):
            # No scale means we are free to change the order of registers
            regs = [x for x in (self.reg1, self.reg2) if x is not None]
            
            if len(regs) == 0:
                # displacement only
                if self.disp in (None, 0):
                    raise TypeError("Cannot encode empty pointer.")
                disp = struct.pack('i', self.disp)
                mrex, modrm = mod_reg_rm('ind', reg, 'sib')
                srex, sib = mk_sib(0, None, 'disp')
                return mrex|srex, modrm + sib + disp
            elif len(regs) == 1:
                # one register; put this wherever is most convenient.
                if regs[0].val == 4:
                    # can't put this in r/m; use sib instead.
                    mrex, modrm = mod_reg_rm(mod, reg, 'sib')
                    srex, sib = mk_sib(0, rsp, regs[0])
                    return mrex|srex, modrm + sib + disp
                elif regs[0].val == 5 and disp == '':
                    mrex, modrm = mod_reg_rm('ind8', reg, regs[0])
                    return mrex, modrm + '\x00'
                else:
                    # Put single register in r/m, add disp if needed.
                    mrex, modrm = mod_reg_rm(mod, reg, regs[0])
                    return mrex, modrm + disp
            else:
                # two registers; swap places if necessary.
                if regs[0] in (esp, rsp): # seems to be unnecessary for r12d
                    if regs[1] in (esp, rsp):
                        raise TypeError("Cannot encode registers in SIB: %s+%s" 
                                        % (regs[0].name, regs[1].name))
                    # don't put *sp registers in offset
                    regs.reverse()
                elif regs[1].val == 5 and disp == '':
                    # if *bp is in base, we need to add 8bit disp
                    mod = 'ind8'
                    disp = '\x00'
                    
                mrex, modrm = mod_reg_rm(mod, reg, 'sib')
                srex, sib = mk_sib(0, regs[0], regs[1])
                return mrex|srex, modrm + sib + disp
                
        else:
            # Must have SIB; cannot change register order
            byts = {None:0, 1:0, 2:1, 4:2, 8:3}[self.scale]
            offset = self.reg1
            base = self.reg2
            
            # sanity checks
            if offset is None:
                raise TypeError("Cannot have SIB scale without offset register.")
            if offset.val == 4:
                raise TypeError("Cannot encode register %s as SIB offset." % offset.name)
            #if base is not None and base.val == 5:
                #raise TypeError("Cannot encode register %s as SIB base." % base.name)

            if base is not None and base.val == 5 and disp == '':
                mod = 'ind8'
                disp = '\x00'
            
            if base is None:
                base = rbp
                mod = 'ind'
                disp = disp + '\0' * (4-len(disp))
            
            mrex, modrm = mod_reg_rm(mod, reg, 'sib')
            srex, sib = mk_sib(byts, offset, base)
            return mrex|srex, modrm + sib + disp
                
        

def qword(ptr):
    if not isinstance(ptr, Pointer):
        if not isinstance(ptr, list):
            ptr = [ptr]
        ptr = interpret(ptr)
    ptr.bits = 64
    return ptr

def dword(ptr):
    if not isinstance(ptr, Pointer):
        if not isinstance(ptr, list):
            ptr = [ptr]
        ptr = interpret(ptr)
    ptr.bits = 32
    return ptr
        
def word(ptr):
    if not isinstance(ptr, Pointer):
        if not isinstance(ptr, list):
            ptr = [ptr]
        ptr = interpret(ptr)
    ptr.bits = 16
    return ptr
        
def byte(ptr):
    if not isinstance(ptr, Pointer):
        if not isinstance(ptr, list):
            ptr = [ptr]
        ptr = interpret(ptr)
    ptr.bits = 8
    return ptr

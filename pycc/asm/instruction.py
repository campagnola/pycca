# -'- coding: utf-8 -'-

import struct, collections

from .register import Register
from .pointer import Pointer, pack_int, ModRmSib, interpret, rex
from . import ARCH


#   Misc. utilities required by instructions
#------------------------------------------------


class Code(object):
    """
    Represents partially compiled machine code with a table of unresolved
    expression replacements.
    
    Code instances can be compiled to a complete machine code string once all
    expression values can be determined.
    """
    def __init__(self, code):
        self.code = code
        self.replacements = {}
        
    def replace(self, index, expr, packing):
        """
        Add a new replacement starting at *index*. 
        
        When this Code is compiled, the value of *expr* will be evaluated,
        packed with *packing* and written into the code at *index*. The expression
        is evaluated using the program's symbols as local variables.
        """
        self.replacements[index] = (expr, packing)
        
    def __len__(self):
        return len(self.code)
    
    def compile(self, symbols):
        code = self.code
        for i,repl in list(self.replacements.items()):
            expr, packing = repl
            val = eval(expr, symbols)
            val = struct.pack(packing, val)
            code = code[:i] + val + code[i+len(val):]
        return code


def label(name):
    """
    Create a label referencing a location in the code.
    
    The name of this label may be used by other assembler calls that require
    a code pointer.
    """
    return Label(name)

class Label(object):
    def __init__(self, name):
        self.name = name
        
    def __len__(self):
        return 0
        
    def compile(self, symbols):
        return ''



class Instruction(object):
    # Variables to be overridden by Instruction subclasses:
    modes = {}  # maps operand signature to instruction modes
    operand_enc = {}  # maps operand type to encoding mode
    
    address_size = 'seg'  # address size is usually determined by code segment
    operand_size = 'reg'  # operand size is usually determined by register size
    
    def __init__(self, *args):
        self.args = args

        # Analysis of input arguments and the corresponding instruction
        # mode to use 
        self._sig = None
        self._clean_args = None        
        self._use_sig = None
        self._mode = None
        
        # Compiled bytecode pieces
        self._prefixes = None
        self._rex_byte = None
        self._opcode = None
        self._operands = None
        
        # Complete, assembled instruction or Code instance
        self._code = None

    def __len__(self):
        return len(self.code)

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def sig(self):
        """The signature of arguments provided for this instruction. 
        
        This is a tuple with strings like 'r32', 'r/m64', and 'imm8'.
        """
        if self._sig is None:
            self.read_signature()
        return self._sig
    
    @property
    def clean_args(self):
        """Filtered arguments. 
        
        These are derived from the arguments supplied when instantiating the
        instruction, with possible changes:
        
        * int values are converted to a packed string
        * lists are converted to Pointer
        """
        if self._clean_args is None:
            self.read_signature()
        return self._clean_args

    @property
    def use_sig(self):
        """The argument signature supported by this instruction that is 
        compatible with the supplied arguments.
        
        The format is the same as the `sig` property.
        """
        if self._use_sig is None:
            self.select_instruction_mode()
        return self._use_sig
    
    @property
    def mode(self):
        """The selected encoding mode to use for this instruction.
        """
        if self._mode is None:
            self.select_instruction_mode()
        return self._mode

    @property
    def prefixes(self):
        """List of string prefixes to use in the compiled instruction.
        """
        if self._prefixes is None:
            self.generate_instruction_parts()
        return self._prefixes

    @property
    def rex_byte(self):
        """REX byte string to use in the compiled instruction.
        """
        if self._rex_byte is None:
            self.generate_instruction_parts()
        return self._rex_byte

    @property
    def opcode(self):
        """Opcode string to use in the compiled instruction.
        """
        if self._opcode is None:
            self.generate_instruction_parts()
        return self._opcode

    @property
    def operands(self):
        """List of compiled operands to use in the compiled instruction.
        """
        if self._operands is None:
            self.generate_instruction_parts()
        return self._operands

    @property
    def code(self):
        """The compiled machine code for this instruction.
        
        If the instruction uses an unresolved symbol (such as a label)
        then a Code instance is returned which can be used to compile the 
        final machine code after symbols are resolved.
        """
        if self._code is None:
            self.generate_code()
        return self._code    
        
    @property
    def asm(self):
        """An intel-syntax assembler string matching this instruction.
        """
        args = []
        for arg in self.args:
            if isinstance(arg, list):
                arg = Pointer(arg[0])
            args.append(arg)
        return self.name + ' ' + ', '.join(map(str, args))
        
    def __eq__(self, code):
        if isinstance(code, (bytes, bytearray)):
            return self.code == code
        else:
            raise TypeError("Unsupported type '%s' for Instruction.__eq__" % 
                            type(code))
        
    def read_signature(self):
        """Determine signature of argument types.
        
        This method may be overridden by subclasses.
        
        Sets self._sig to a tuple of strings like 'r32', 'r/m64', and 'imm8'
        Sets self._clean_args to a tuple of arguments that have been processed:
            - lists are converted to Pointer
            - ints are converted to packed string
        """
        sig = []
        clean_args = []
        for arg in self.args:
            if isinstance(arg, list):
                arg = interpret(arg)
                
            if isinstance(arg, Register):
                if arg.name.startswith('xmm'):
                    sig.append('xmm')
                else:
                    sig.append('r%d' % arg.bits)
            elif isinstance(arg, Pointer):
                sig.append('m%d' % arg.bits)
            elif isinstance(arg, int):
                arg = pack_int(arg, int8=True)
                sig.append('imm%d' % (8*len(arg)))
            elif isinstance(arg, str):
                sig.append('imm%d' % len(arg))
            else:
                raise TypeError("Invalid argument type %s." % type(arg))
            clean_args.append(arg)
        
        self._sig = tuple(sig)
        self._clean_args = tuple(clean_args)

    def select_instruction_mode(self):
        """Select a compatible instruction mode from self.modes based on the 
        signature of arguments provided.
        
        Sets self.use_sig to the compatible signature selected.
        Sets self.mode to the instruction mode selected.
        """
        modes = self.modes
        sig = self.sig
        
        # filter out modes not supported by this arch
        archind = 2 if ARCH == 64 else 3
        modes = collections.OrderedDict([sm for sm in list(modes.items()) if sm[1][archind]])
        
        #print "Select instruction mode for sig:", sig
        #print "Available modes:", modes
        orig_sig = sig
        if sig in modes:
            self._use_sig = sig
            self._mode = modes[sig]
            return
        
        # Check each instruction mode one at a time to see whether it is compatible
        # with supplied arguments.
        for mode in modes:
            if len(mode) != len(sig):
                continue
            usemode = True
            for i in range(len(mode)):
                if self.check_mode(sig[i], mode[i]):
                    continue
                else:
                    usemode = False
                    break
            
            if usemode:
                self._use_sig = mode
                self._mode = modes[mode]
                return
        
        raise TypeError('Argument types not accepted for instruction %s: %s' 
                        % (self.name, str(orig_sig)))

    def check_mode(self, sig, mode):
        """Return True if an argument of type *sig* may be used to satisfy
        operand type *mode*.
        
        *sig* may look like 'r16', 'm32', 'imm8', 'rel32', 'xmm1', etc.
        *mode* may look like 'r8', 'm32/64', 'r/m32', 'xmm1/m64', 'xmm2', etc.
        """
        sbits = sig.lstrip('irel/xm')
        stype = sig[:-len(sbits)] if len(sbits) > 0 else sig
        mbits = mode.lstrip('irel/xm')
        mtype = mode[:-len(mbits)] if len(mbits) > 0 else mode
        try:
            mbits = int(mbits)
        except ValueError:
            mbits = 0
        try:
            sbits = int(sbits)
        except ValueError:
            sbits = 0

        if mtype == 'r':
            return stype == 'r' and mbits == sbits
        elif mtype == 'r/m':
            return stype in ('r', 'm') and mbits == sbits
        elif mtype == 'imm':
            return stype == 'imm' and mbits >= sbits
        elif mtype == 'rel':
            return stype == 'rel'
        elif mtype == 'm':
            if stype != 'm':
                return False
            if mbits > 0 and mbits != sbits:
                return False
            return True
        elif mtype == 'xmm':
            if stype == 'xmm':
                return True
            if '/m' in mode and stype == 'm':
                # handle mode like "xmm1/m64"
                return self.check_mode(sig, mode[mode.index('/')+1:])
            return False
        raise Exception("Invalid operand type %s" % mtype)

    def generate_instruction_parts(self):
        """Generate bytecode strings for each piece of the instruction.
        
        Sets self._prefixes, self._rex_byte, self._opcode, and self._operands
        """
        # parse opcode string (todo: these should be pre-parsed)
        mode = self.mode
        
        op_parts = mode[0].split(' ')
        rexw = False
        if op_parts[:2] == ['REX.W', '+']:
            op_parts = op_parts[2:]
            rexw = True
        
        opcode_s = op_parts[0]
        if '+' in opcode_s:
            opcode_s = opcode_s.partition('+')[0]
            reg_in_opcode = True
        else:
            reg_in_opcode = False
        
        # assemble initial opcode
        #opcode = b''
        #for i in range(0, len(opcode_s), 2):
            #opcode += chr(int(opcode_s[i:i+2], 16))
        opcode = bytearray.fromhex(opcode_s)
        
        # check for opcode extension
        opcode_ext = None
        if len(op_parts) > 1:
            if op_parts[1] == '/r':
                pass  # handled by operand encoding
            elif op_parts[1][0] == '/':
                opcode_ext = int(op_parts[1][1])

        # Parse operands into encodable pieces
        prefixes, rex_byt, opcode_reg, modrm_reg, modrm_rm, imm = self.parse_operands()
        
        
        # encode complete instruction:
        
        # decide value for ModR/M reg field
        if modrm_reg is None:
            modrm_reg = opcode_ext
        elif opcode_ext is not None:
            raise RuntimeError("Cannot encode both register and opcode "
                               "extension in ModR/M.")

        # encode register in opcode if requested
        if opcode_reg is not None:
            opcode[-1] |= opcode_reg
        
        # encode ModR/M and SIB bytes
        operands = []
        if modrm_rm is not None:
            modrm = ModRmSib(modrm_reg, modrm_rm)
            operands.append(modrm.code)
            rex_byt |= modrm.rex
            
        # encode immediate operands
        if imm is not None:
            operands.append(imm)
        
        # encode REX byte
        if rexw:
            rex_byt |= rex.w
        
        if rex_byt == 0:
            rex_byt = b''
        else:
            rex_byt = bytearray([rex_byt])
        
        self._prefixes = prefixes
        self._rex_byte = rex_byt
        self._opcode = opcode
        self._operands = operands
        
    def generate_code(self):
        """Generate complete bytecode for this instruction.
        
        Sets self._code.
        """
        prefixes = self.prefixes
        rex_byte = self.rex_byte
        opcode = self.opcode
        operands = self.operands
        
        self._code = (b''.join(prefixes) + 
                      rex_byte + 
                      opcode + 
                      b''.join(operands))

    def parse_operands(self):
        """Use supplied arguments and selected operand encodings to determine
        how to encode operands. 
        
        Returns a tuple:
            prefixes: a list of prefix strings
            rex_byt: an integer REX byte (0 for no REX byte)
            opcode_reg: a register to encode as the last 3 bits of the opcode 
                        (or None)
            reg: register to use in the reg field of a ModR/M byte
            rm: register or pointer to use in the r/m field of a ModR/M byte
            imm: immediate string
        """
        clean_args = self.clean_args
        operand_enc = self.operand_enc
        use_sig = self.use_sig
        mode = self.mode
        
        reg = None
        rm = None
        imm = None
        prefixes = []
        rex_byt = 0
        opcode_reg = None  # register code embedded in opcode
        for i,arg in enumerate(clean_args):
            # look up encoding for this operand
            enc = operand_enc[mode[1]][i]
            #print "operand encoding:", i, arg, enc 
            if enc.startswith('opcode +rd'):
                opcode_reg = arg.val
                if arg.rex:
                    rex_byt = rex_byt | rex.b
                if arg.bits == 16:
                    prefixes.append('\x66')
            elif enc.startswith('ModRM:r/m'):
                rm = arg
                if arg.bits == 16:
                    prefixes.append('\x66')
                if isinstance(arg, Pointer):
                    addrpfx = arg.prefix
                    if addrpfx != '':
                        prefixes.append(addrpfx)  # adds 0x67 prefix if needed
            elif enc.startswith('ModRM:reg'):
                reg = arg
            elif enc.startswith('imm'):
                immsize = int(use_sig[i][3:])
                opsize = 8 * len(arg)
                assert opsize <= immsize
                imm = arg + '\0'*((immsize-opsize)//8)
            else:
                raise RuntimeError("Invalid operand encoding: %s" % enc)
        
        return (prefixes, rex_byt, opcode_reg, reg, rm, imm)
        


class RelBranchInstruction(Instruction):
    """Instruction supporting branching to a relative memory location.
    
    Subclasses must set _addr_offset and _instr_len attributes.
    """
    def __init__(self, addr):
        self._label = None
        Instruction.__init__(self, addr)
            
    def read_signature(self):
        if len(self.args) != 1:
            Instruction.read_signature(self)  # should raise exception
        
        # Need to intercept immediate args and subtract instr_len or set label
        addr = self.args[0]
        if isinstance(addr, (int, str)):
            
            # Generate relative call to label / offset
            self._label = addr
            self._sig = ('rel32',)
            self._clean_args = [struct.pack('i', 0)]
        else:
            Instruction.read_signature(self)
         
    def generate_code(self):
        prefixes = self.prefixes
        rex_byte = self.rex_byte
        opcode = self.opcode
        operands = self.operands
        
        if self._label is not None:
            # If an operand used a label, we need to account for relative addressing
            # here.
            code = (''.join(prefixes) + 
                        rex_byte + 
                        opcode)
            # get the location and size of the relative operand in the instruction
            addr_offset = None
            for i, op in enumerate(operands):
                if self.use_sig[i].startswith('rel'):
                    addr_offset = len(code)
                    op_size = len(op)
                code += op
            
            if addr_offset is None:
                raise RuntimeError("No 'rel' operand in signature; cannot apply label.")
            op_pack = {1: 'b', 2: 'h', 4: 'i'}[op_size]
            
            if isinstance(self._label, str):
                # Set a Code instance that will insert the correct address once
                # the label is resolved.
                code = Code(code)
                code.replace(addr_offset, "%s - next_instr_addr" % self._label, op_pack)
                self._code = code
            elif isinstance(self._label, int):
                # Adjust offset to account for size of instruction
                offset = struct.pack(op_pack, self._label - len(code))
                self._code = code[:addr_offset] + offset + code[addr_offset+op_size:]
            else:
                raise TypeError("Invalid label type: %s" % type(self._label))
        else:
            Instruction.generate_code(self)


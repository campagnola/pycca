# -'- coding: utf-8 -'-

import sys, mmap, ctypes
from .instruction import Instruction, Code, Label
from .parser import parse_asm


class CodePage(object):
    """Compiles assembly, loads machine code into executable memory, and 
    generates python functions for accessing the code.
    
    Initialize with either an assembly string or a list of 
    :class:`Instruction <pycc.asm.Instruction>` instances. The *namespace*
    argument may be used to define extra symbols when compiling from an 
    assembly string. 
    
    This class encapsulates a block of executable mapped memory to which a 
    sequence of asm commands are compiled and written. The memory page(s) may 
    contain multiple functions; use get_function(label) to create functions 
    beginning at a specific location in the code.
    """
    def __init__(self, asm, namespace=None):
        self.labels = {}
        if isinstance(asm, str):
            asm = parse_asm(asm, namespace=namespace)
        else:
            if namespace is not None:
                raise TypeError("Namespace argument may only be used with "
                                "string assembly type.")
        
        self.asm = asm
        code_size = len(self)
        #pagesize = os.sysconf("SC_PAGESIZE")
        
        # Create a memory-mapped page with execute privileges
        if sys.platform == 'win32':
            #self.page = mmap.mmap(-1, code_size, access=0x40)
            self.page = WinPage(code_size)
            self.page_addr = self.page.addr
        else:
            PROT_NONE = 0
            PROT_READ = 1
            PROT_WRITE = 2
            PROT_EXEC = 4
            self.page = mmap.mmap(-1, code_size, prot=PROT_READ|PROT_WRITE|PROT_EXEC)

            # get the page address
            buf = (ctypes.c_char * code_size).from_buffer(self.page)
            self.page_addr = ctypes.addressof(buf)
        
        # Compile machine code and write to the page.
        code = self.compile(asm)
        assert len(code) <= len(self.page)
        self.page.write(bytes(code))
        self.code = code
        
    def __len__(self):
        return sum(map(len, self.asm))

    def get_function(self, label=None):
        """Create and return a python function that points to a specific label
        within the compiled code block, or the first byte if no label is given. 
        
        The return value is a *ctypes* function; it is recommended to set the
        restype and argtypes properties on the function before calling it.
        """
        addr = self.page_addr
        if label is not None:
            addr = self.labels[label]
        
        # Turn this into a callable function
        if sys.platform == 'win32':
            f = ctypes.WINFUNCTYPE(None)(addr)  # stdcall    
        else:
            f = ctypes.CFUNCTYPE(None)(addr)    # cdecl
        f.page = self  # Make sure page stays alive as long as function pointer!
        return f

    def compile(self, asm):
        ptr = self.page_addr
        # First locate all labels
        for cmd in asm:
            ptr += len(cmd)
            if isinstance(cmd, Label):
                self.labels[cmd.name] = ptr
                
        # now compile
        symbols = self.labels.copy()
        code = b''
        for cmd in asm:
            if isinstance(cmd, Label):
                continue
            
            if isinstance(cmd, Instruction):
                cmd = cmd.code
                
            if isinstance(cmd, Code):
                # Make some special symbols available when resolving
                # expressions:
                symbols['instr_addr'] = self.page_addr + len(code)
                symbols['next_instr_addr'] = symbols['instr_addr'] + len(cmd)
                
                cmd = cmd.compile(symbols)
            
            code += cmd
        return code

    def dump(self):
        """Return a string representation of the machine code and assembly
        instructions contained in the code page.
        """
        code = ''
        ptr = 0
        for instr in self.asm:
            hex = ''
            if isinstance(instr, Instruction):
                for c in bytearray(instr.code):
                    hex += '%02x' % c
            code += '0x%04x: %s%s%s\n' % (ptr, hex, ' '*(40-len(hex)), instr)
            ptr += len(hex)/2
        return code


class WinPage(object):
    """Emulate mmap using windows memory block."""
    def __init__(self, size):
        kern = ctypes.windll.kernel32
        valloc = kern.VirtualAlloc
        valloc.argtypes = (ctypes.c_uint32,) * 4
        valloc.restype = ctypes.c_uint32
        MEM_COMMIT = 0x1000
        MEM_RESERVE = 0x2000
        PAGE_EXECUTE_READWRITE = 0x40
        self.addr = valloc(0, size, MEM_RESERVE | MEM_COMMIT, PAGE_EXECUTE_READWRITE)
        self.ptr = 0
        self.size = size
        self.mem = (ctypes.c_char * size).from_address(self.addr)

    def write(self, data):
        self.mem[self.ptr:self.ptr+len(data)] = data
        self.ptr += len(data)

    def __len__(self):
        return self.size

    def __del__(self):
        kern = ctypes.windll.kernel32
        vfree = kern.VirtualFree
        vfree.argtypes = (ctypes.c_uint32,) * 3
        MEM_RELEASE = 0x8000
        vfree(self.addr, self.size, MEM_RELEASE)
    

def mkfunction(code, namespace=None):
    """Convenience function that creates a 
    :class:`CodePage <pycca.asm.CodePage>` from the supplied *code* argument 
    and returns a function pointing to the first byte of the compiled code. 
    
    See :func:`CodePage.get_function() <pycca.asm.CodePage.get_function>`.
    """
    page = CodePage(code, namespace=namespace)
    return page.get_function()

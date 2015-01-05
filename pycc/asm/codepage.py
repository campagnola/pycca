# -'- coding: utf-8 -'-

import mmap, ctypes
from .instruction import Instruction, Code, Label

class CodePage(object):
    """
    Encapsulates a block of executable mapped memory to which a sequence of
    asm commands are compiled and written. 
    
    The memory page(s) may contain multiple functions; use get_function(label)
    to create functions beginning at a specific location in the code.
    """
    def __init__(self, asm):
        self.labels = {}
        self.asm = asm
        code_size = len(self)
        #pagesize = os.sysconf("SC_PAGESIZE")
        
        # Create a memory-mapped page with execute privileges
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
        self.page.write(code)
        
    def __len__(self):
        return sum(map(len, self.asm))

    def get_function(self, label=None):
        addr = self.page_addr
        if label is not None:
            addr += self.labels[label]
        
        # Turn this into a callable function
        f = ctypes.CFUNCTYPE(None)(addr)
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
        code = ''
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
        
        
def mkfunction(code):
    page = CodePage(code)
    return page.get_function()

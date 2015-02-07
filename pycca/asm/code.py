import struct


class Code(object):
    """Represents partially compiled machine code with a table of unresolved
    expression replacements.
    
    Code instances can be compiled to a complete machine code string once all
    expression values can be determined.
    """
    def __init__(self, code):
        self.code = code
        self.replacements = []
        
    def replace(self, index, expr, packing):
        """
        Add a new replacement starting at *index*. 
        
        When this Code is compiled, the value of *expr* will be evaluated,
        packed with *packing* and written into the code at *index*. The expression
        is evaluated using the program's symbols as local variables.
        """
        self.replacements.append((index, expr, packing))
        
    def __len__(self):
        return len(self.code)
    
    def compile(self, symbols):
        code = self.code
        for i, expr, packing in self.replacements:
            val = eval(expr, symbols)
            val = struct.pack(packing, val)
            code = code[:i] + val + code[i+len(val):]
        return code

    def __add__(self, x):
        if isinstance(x, Code):
            code = Code(self.code + x.code)
            for index, expr, packing in self.replacements:
                code.replace(index, expr, packing)
            for index, expr, packing in x.replacements:
                code.replace(index+len(self.code), expr, packing)
            return code
            
        elif isinstance(x, (bytes, bytearray)):
            append = bytes(x)
            code = Code(self.code + append)
            for index, expr, packing in self.replacements:
                code.replace(index, expr, packing)
            return code
        
        else:
            raise TypeError("Cannot add Code to type %s" % type(x))

    def __radd__(self, x):
        if not isinstance(x, (bytes, bytearray)):
            raise TypeError("Cannot add Code to type %s" % type(x))
        prepend = bytes(x)
        code = Code(prepend + self.code)
        for index, expr, packing in self.replacements:
            code.replace(index+len(prepend), expr, packing)
        return code


def label(name):
    """
    Create a label referencing a location in the code.
    
    The name of this label may be used by other assembler calls that require
    a code pointer. When the label is compiled, it is replaced by its address
    within the CodePage.
    """
    return Label(name)


class Label(object):
    """Marks or references a location in assembly code. 
    """
    def __init__(self, name):
        self.name = name
        
    def __len__(self):
        return 0
        
    def __str__(self):
        return ':' + self.name
        
    def compile(self, symbols):
        return ''

    def __add__(self, disp):
        if not isinstance(disp, int):
            raise TypeError("Can only add integer to label.")
        from .pointer import Pointer
        return Pointer(label=self.name, disp=disp)
        
    def __sub__(self, disp):
        return self + (-disp)
    
    def __radd__(self, x):
        return self + x
        
    def __eq__(self, x):
        return x.name == self.name

#class LabelOffset(object):
    #"""References a location in a CodePage that is marked by a label, plus a
    #constant offset.
    #"""
    #def __init__(self, name, offset):
        #self.name = name
        #self.offset = offset
        
    #def __len__(self):
        #return 0
        
    #def __str__(self):
        #return "%s + %d" % (self.name, self.offset)
        
    #def compile(self, symbols):
        #return ''

    #def __add__(self, disp):
        #if not isinstance(disp, int):
            #raise TypeError("Can only add integer to label.")
        #return LabelOffset(self.name, self.offset+disp)
        
    #def __radd__(self, x):
        #return self + x

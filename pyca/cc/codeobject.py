# -*- coding: utf-8 -*-

class CodeObject(object):
    """Base class for all C code constructs.
    """
    def __init__(self, lineno=None):
        self._lineno = lineno

    def attach(self):
        CCode.append(self)


class CodeContainer(CodeObject):
    """C code construct that may contain others (functions, loops, etc).
    """
    _code_stack = []
    
    def __init__(self, code=None):
        if code is None:
            self._code = []
        else:
            self._code = code
    
    def append(self, code):
        self._code.append(code)
        
    @property
    def code(self):
        return self._code
        
    @property
    def current(self):
        return self._code_stack[-1]
    
    def names_in_scope(self):
        return {}
    
    def __enter__(self):
        CodeContainer._code_stack.append(self)
    
    def __exit__(self, *args):
        CodeContainer._code_stack.pop()
        

    
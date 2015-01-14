# -*- coding: utf-8 -*-
import numpy as np
from pycc.cc import CCode, Function, Assign, Return

code = CCode([
    Function('int', 'add_one', [('int', 'x')], [
        Assign(x='x + 1'),
        Return('x')
    ])
])
print code.dump_asm()
print "3 + 1 = %d" % code.add_one(3)


c = CCode([Function('double', 'fn', [], [Return(12.3)]) ])
print c.dump_asm()
print "12.3 = ", c.fn()


# Example: a little closer to C
#code = CCode([
    #Function('int add_one(int x)', [
        #Assign(x='x + 1'),
        #Return('x')
    #])
#])


# Example: GIL handling for long operations
#code = CCode([
    #Function('int', 'add_one', [('int', 'x')], [
        #Declare(['int', 'ts']),
        #Assign(ts=Call(ctypes.pythonapi.PyThreadState_Get)),
        #Assign(ts=ctypes.pythonapi.PyEval_SaveThread, 'ts'),
        ## GIL is released, now do work:
        #Assign(x='x + 1'),
        ## Re-acquire GIL before returning:
        #Call(ctypes.pythonapi.PyEval_RestoreThread, 'ts'),
        #Return('x')
    #])
#])


# Example: coding in pure C        
#find_greater = compile("""
    #int find_greater(int* array, int size, int threshold) {
        #int i;
        #for( i=0; i<size; i++) {
            #if( array[i] > threshold )
                #return i;
        #}
        #return -1;
    #}
#""")


# Example: inserting objects into global namespace
#compile("""
    #double exp_x_plus_one(double x) {
        #return exp(x + 1);
    #}
#""", globals={'exp': ctypes.cdll.LoadLibrary('m').exp})


#data = np.arange(10000)
#print "First > 5000:", find_greater(data, len(data), 5000)


# Examples: coding using with-blocks 
# Note 1: No need for Assign in this example, which means we can 
#         use Python to parse expressions.
# Note 2: Might be confusing because variables outlive their function scope
# Note 3: This should be considered lower priority than parsing regular C. 
#
#code = CCode()
#with code:
#    exp = import_func(libm.exp)
#    with Function('void', 'test_func', ('float', 'x')) as func:
#        x = func.args[0]
#        y = double(x+1) 
#        Return( exp(x * (y + 1))) )
        
#code = CCode()
#with code:
    #with If(cond):
        #statements
    #with ElseIf(cond):
        #statements
    #with Else():
        #statements
        


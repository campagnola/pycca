# -*- coding: utf-8 -*-
import numpy as np
from pycc.cc import CCode, Function, Assignment, Return

code = CCode([
    Function('int', 'add_one', [('int', 'x')], [
        Assignment(x='x + 1'),
        Return('x')
    ])
])
code.compile()

print "3 + 1 = %d" % code.add_one(3)



#code = CCode()
#with code:
    #import_(ctypes.cdll.LoadLibrary('libm.so'), 'exp')
    #with Function('void', 'test_func', ('float', 'x')):
        #Assign(x='x + 1')
        #Return(Call('exp', 'x'))
        

#code = CCode()
#with code:
    #with If(cond):
        #statements
    #with ElseIf(cond):
        #statements
    #with Else():
        #statements
        
        
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


#data = np.arange(10000)
#print "First > 5000:", find_greater(data, len(data), 5000)

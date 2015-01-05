import ctypes, struct
import numpy as np
import user

from pycc.asm import *

try:
    import faulthandler
    faulthandler.enable()
except ImportError:
    pass

print """
   Example 1: Write a string to stdout
------------------------------------------------------
"""

msg = ctypes.create_string_buffer("Howdy.\n")
if ARCH == 32:
    prnt = [  # write to stdout on 32-bit linux
        mov(eax, 4),  # sys_write  (see unistd_32.h)
        mov(ebx, 1),  # stdout
        mov(ecx, ctypes.addressof(msg)),
        mov(edx, len(msg)-1),
        int_(0x80),
        ret()
    ]
else:
    prnt = [  # write to stdout on 64-bit linux
        mov(rax, 1),   # write  (see unistd_64.h)
        mov(rdi, 1),   # stdout
        mov(rsi, ctypes.addressof(msg)),
        mov(rdx, len(msg)-1),
        syscall(),
        ret()
    ]

# print!
fn = mkfunction(prnt)
fn.restype = ctypes.c_uint64
fn()


print """
   Example 2: Return a value from call
------------------------------------------------------
"""

# just leave the value in eax/rax before returning
fn = mkfunction([
    mov(rax, 0xdeadbeef),
    ret()
])

# Tell ctypes how to interpret the return value
fn.restype = ctypes.c_uint64

# Call! Hopefully we get 0xdeadbeef back.
print "Return: 0x%x" % fn()


print """
   Example 3: Pass arguments to function
------------------------------------------------------
"""

# There are a few different calling conventions we might want to support..
# This example uses the System V AMD64 convention (used by most *nixes)
# and the Microsoft x64 convention.
# See: http://en.wikipedia.org/wiki/X86_calling_conventions

fn = mkfunction([
    # copy 8 bytes from arg2 to arg 1
    # (both args are pointers to char*)
    mov(rax, [argi[1]]),
    mov([argi[0]], rax),
    ret(),
])
fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
msg1 = ctypes.create_string_buffer("original original")
msg2 = ctypes.create_string_buffer("modified modified")
fn(msg1, msg2)
print 'Modified string: "%s"' % msg1.value


print """
   Example 4: Call an external function
------------------------------------------------------
"""

# Again we need to worry about calling conventions here.
# Most common 64-bit conventions pass the first float arg in xmm0

libm = ctypes.cdll.LoadLibrary('libm.so.6')
# look up math.exp() from C standard lib, dereference function pointer
fp = (ctypes.c_char*8).from_address(ctypes.addressof(libm.exp))
fp = struct.unpack('Q', fp[:8])[0]

exp = mkfunction([
    mov(rax, fp),      # Load address of exp()
    call(rax),         # call exp()  - input arg is already in xmm0
    ret(),             # return; now output arg is in xmm0
])

op = 3.1415
exp.restype = ctypes.c_double
exp.argtypes = (ctypes.c_double,)
out = exp(op)
print "exp(%f) = %f =? %f" % (op, out, np.exp(op))


print """
   Example 5: Jump to label
----------------------------------------------
"""

fn = mkfunction([
    mov(rax, 0x1),
    jmp('start'),
    label('end'),
    ret(),
    mov(rax, 0x1),
    mov(rax, 0x1),
    label('start'),
    mov(rax, 0xdeadbeef),
    jmp('end'),
    mov(rax, 0x1),
])
fn.restype = ctypes.c_uint64

# We get 0xdeadbeef back if jumps are followed.
print "Return: 0x%x" % fn()


print """
   Example 6: Access values from an array
------------------------------------------------------
"""

import numpy as np
data = np.ones(10, dtype=np.uint64)
I = 5
data[I] = 12345
addr = data.ctypes.data
fn = mkfunction([
    mov(rax, [addr+I*data.strides[0]]),  # return value from array[5]
    mov(rbx, addr),                      # copy array address to register
    mov(rcx, 54321),                     # copy new value to register
    mov([rbx+I*data.strides[0]], rcx),   # copy new value to array[5]
    ret(),
])
fn.restype = ctypes.c_uint64

print "Read from array: %d" % fn()
print "Modified array: %d" % data[5]


print """
   Example 7: a basic for-loop
------------------------------------------------------
"""

fn = mkfunction([
    mov(rax, 0),
    label('startfor'),
    cmp(rax, 10),
    jge('breakfor'),
    inc(rax),
    jmp('startfor'),
    label('breakfor'),
    ret()
])

fn.restype = ctypes.c_uint64
print "Iterate to 10:", fn()


print """
   Example 7: a useful function!
------------------------------------------------------
"""

find_first = mkfunction([
    mov(rax, 0),
    label('start_for'),
    cmp([argi[0]+rax*8], 0),
    jge('break_for'),
    inc(rax),
    cmp(rax, argi[1]),
    jge('break_for'),
    jmp('start_for'),
    label('break_for'),
    ret()
])

find_first.argtypes = [ctypes.c_uint64, ctypes.c_uint64]
find_first.restype = ctypes.c_uint64
find_first.__doc__ = "Return index of first value in an array that is >= 0"

data = -1 + np.zeros(10000000, dtype=np.int64)
data[-1] = 1
import time
start = time.time()
ind1 = find_first(data.ctypes.data, len(data))
duration1 = time.time() - start

start = time.time()
ind2 = np.argwhere(data >= 0)[0,0]
duration2 = time.time() - start

assert ind1 == ind2
print "First >= 0:", ind1
print "ASM version took %0.2fms" % (duration1*1000) 
print "NumPy version took %0.2fms" % (duration2*1000) 

import ctypes
import numpy as np
import user

from pycc.asm import *

try:
    import faulthandler
    faulthandler.enable()
except ImportError:
    pass


#   Example 1: Write a string to stdout
#------------------------------------------------------

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



#   Example 2: Return a value from call
#------------------------------------------------------

# just leave the value in eax/rax before returning
fn = mkfunction([
    mov(eax,0xdeadbeef),
    ret()
])

# Tell ctypes how to interpret the return value
fn.restype = ctypes.c_uint64

# Call! Hopefully we get 0xdeadbeef back.
print "Return: 0x%x" % fn()



#   Example 3: Pass arguments to function
#------------------------------------------------------

# There are a few different calling conventions we might want to support..
# This example uses the System V AMD64 convention (used by most *nixes)
# and the Microsoft x64 convention.
# See: http://en.wikipedia.org/wiki/X86_calling_conventions

if sys.platform == 'win32':
    args = [rcx, rdx] #, r8, r9]
else:
    args = [rdi, rsi, rdx, rcx] #, r8, r9]
fn = mkfunction([
    # copy 8 bytes from arg2 to arg 1
    # (both args are pointers to char*)
    mov(rax, [args[1]]),
    mov([args[0]], rax),
    ret(),
])
fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
msg1 = ctypes.create_string_buffer("original original")
msg2 = ctypes.create_string_buffer("modified modified")
fn(msg1, msg2)
print 'Modified string: "%s"' % msg1.value



#   Example 4: Call an external function
#------------------------------------------------------

# Again we need to worry about calling conventions here.
# Most common 64-bit conventions pass the first float arg in xmm0

libm = ctypes.cdll.LoadLibrary('libm.so.6')
# look up math.exp() from C standard lib, dereference function pointer
fp = (ctypes.c_char*8).from_address(ctypes.addressof(libm.exp))
fp = struct.unpack('Q', fp[:8])[0]

# prepare input operand
op = 3.1415
xop = struct.unpack('q', struct.pack('d', op))[0]

exp = mkfunction([
    push(rbp),
    mov(rbp, rsp),
    add(rsp, -0x10),          # increase stack depth
    mov(rax, xop),            # place operand in rx => stack => xmm0
    mov([rbp-0x10], rax),
    movsd(xmm0, [rbp-0x10]),  
    mov(rbx, fp),
    call(rbx),                # call exp()
    movsd([rbp-0x10], xmm0),  # copy result from xmm0 back to rax
    mov(rax, [rbp-0x10]),
    leave(),
    ret(),
    
    # For some reason this version segfaults..
    #add(rsp, -0x18),     # increase stack depth
    #mov(rax, xop),       # place operand in xmm0
    #mov([rsp], rax),
    #movsd(xmm0, [rsp]),
    #mov(rax, fp),        # set branch pointer
    #call(rax),           # call exp()
    #movsd([rsp], xmm0),  # copy result from xmm0 back to rax
    #mov(rax, [rsp]),
    #add(rsp, 0x18),      # decrease stack depth
    #ret(),
])

exp.restype = ctypes.c_double
out = exp()
print "exp(%f) = %f =? %f" % (op, out, np.exp(op))



#   Example 5: Jump to label
#----------------------------------------------

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


#   Example 6: Access values from an array
#------------------------------------------------------

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



#   Example 7: a basic for-loop
#------------------------------------------------------

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



#   Example 7: a useful function!
#------------------------------------------------------

if sys.platform == 'win32':
    args = [rcx, rdx] #, r8, r9]
else:
    args = [rdi, rsi, rdx, rcx] #, r8, r9]

find_first = mkfunction([
    mov(rax, 0),
    label('start_for'),
    cmp([args[0]+rax*8], 0),
    jge('break_for'),
    inc(rax),
    cmp(rax, args[1]),
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

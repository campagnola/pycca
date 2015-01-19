import ctypes, struct, time, math
try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    import array
    HAVE_NUMPY = False

from pyca.asm import *

try:
    import faulthandler
    faulthandler.enable()
except ImportError:
    pass



print("""
   Example 1: Return a value from call
------------------------------------------------------
""")

# just leave the value in eax/rax before returning
reg = rax if ARCH == 64 else eax
val = struct.pack('I', 0xdeadbeef)
fn = mkfunction([
    mov(reg, val),
    ret()
])

# Tell ctypes how to interpret the return value
fn.restype = ctypes.c_uint32

# Call! Hopefully we get 0xdeadbeef back.
print("Return: 0x%x" % fn())


print("""
   Example 2: Jump to label
----------------------------------------------
""")

# Also show that we can give an assembly string rather than 
# instruction objects:
fn = mkfunction("""
        mov  eax, 0x1
        jmp  start
    end:
        ret
        mov  eax, 0x1
        mov  eax, 0x1
    start:
        mov  eax, 0xdeadbeef
        jmp  end
        mov  eax, 0x1
""")

fn.restype = ctypes.c_uint32

# We get 0xdeadbeef back if jumps are followed.
print("Return: 0x%x" % fn())


print("""
   Example 3: Access values from an array
------------------------------------------------------
""")

# Show how to access data from both numpy array and python arrays
if HAVE_NUMPY:
    data = np.ones(10, dtype=np.uint32)
    addr = data.ctypes.data
    stride = data.strides[0]
else:
    data = array.array('I', [1]*10)
    addr = data.buffer_info()[0]
    stride = 4

I = 5   # will access 5th item from asm function
data[I] = 12345
offset = I * stride
    
if ARCH == 64:
    fn = mkfunction([
        mov(rcx, addr),                    # copy memory address to rcx
        mov(eax, dword([rcx+offset])),     # return value from array[5]
        mov(dword([rcx+offset]), 54321),   # copy new value to array[5]
        ret(),
    ])
else:
    fn = mkfunction([
        mov(ecx, addr),             # copy memory address to rcx
        mov(eax, [ecx+offset]),     # return value from array[5]
        mov([ecx+offset], 54321),   # copy new value to array[5]
        ret(),
    ])
fn.restype = ctypes.c_uint32

print("Read from array: %d" % fn())
print("Modified array: %d" % data[5])


print("""
   Example 4: a basic for-loop
------------------------------------------------------
""")

fn = mkfunction([
    mov(eax, 0),
    label('startfor'),
    cmp(eax, 10),
    jge('breakfor'),
    inc(eax),
    jmp('startfor'),
    label('breakfor'),
    ret()
])

fn.restype = ctypes.c_uint32
print("Iterate to 10: %d" % fn())


print("""
   Example 5: Write a string to stdout
------------------------------------------------------
""")

# Printing requires OS calls that are different for every platform.
msg = ctypes.create_string_buffer(b"Howdy.\n")
if sys.platform == 'win32':
    print("[ not implemented on win32 ]")
else:
    if ARCH == 32:
        prnt = [  # write to stdout on 32-bit linux
            mov(eax, 4),  # sys_write  (see unistd_32.h)
            mov(ebx, 1),  # stdout
            mov(ecx, ctypes.addressof(msg)),
            mov(edx, len(msg)-1),
            int_(0x80),
            ret()
        ]
        fn = mkfunction(prnt)
        fn.restype = ctypes.c_uint32
    else:
        if sys.platform == 'darwin':
            syscall_cmd = 0x2000004
        else:
            syscall_cmd = 0x1
        prnt = [  # write to stdout on 64-bit linux
            mov(rax, syscall_cmd),   # write  (see unistd_64.h)
            mov(rdi, 1),   # stdout
            mov(rsi, ctypes.addressof(msg)),
            mov(rdx, len(msg)-1),
            syscall(),
            ret()
        ]
        fn = mkfunction(prnt)
        fn.restype = ctypes.c_uint64

    # print!
    fn()


print("""
   Example 6: Pass arguments to function
------------------------------------------------------
""")

# This example copies 8 bytes from one char* to another char*.

# Each platform uses a different calling convention:
if ARCH == 32:
    if sys.platform == 'win32':
        ret_byts = 8
    else:
        ret_byts = 0
        
    # stdcall convention
    fn = mkfunction([
        mov(ecx, [esp+8]),  # get arg 1 location from stack
        mov(edx, [esp+4]),  # get arg 0 location from stack
        mov(eax, [ecx]),    # get 4 bytes from arg 1 string
        mov([edx], eax),    # copy to arg 0 string
        mov(eax, [ecx+4]),  # get next 4 bytes
        mov([edx+4], eax),  # copy to arg 0 string
        ret(8),             # in stdcall, the callee must clean up the stack
    ])
    
else:
    if sys.platform == 'win32':
        # Microsoft x64 convention
        fn = mkfunction([
            mov(rax, [rdx]),  # copy 8 bytes from second arg
            mov([rcx], rax),  # copy to first arg
            ret(),            # caller clean-up
        ])
    else:
        # System V AMD64 convention
        fn = mkfunction([
            mov(rax, [argi[1]]),  # copy 8 bytes from second arg
            mov([argi[0]], rax),  # copy to first arg
            ret(),                # caller clean-up
        ])
fn.argtypes = (ctypes.c_char_p, ctypes.c_char_p)
msg1 = ctypes.create_string_buffer(b"original original")
msg2 = ctypes.create_string_buffer(b"modified modified")
fn(msg1, msg2)
print('Modified string: "%s"' % msg1.value)


print("""
   Example 7: Call an external function
------------------------------------------------------
""")


# look up math.exp() from C standard lib
if sys.platform == 'darwin':
    libm = ctypes.cdll.LoadLibrary('libm.dylib')
elif sys.platform == 'win32':
    libm = ctypes.windll.msvcrt
else:
    libm = ctypes.cdll.LoadLibrary('libm.so.6')

# Again we need to worry about calling conventions here..
if ARCH == 64:
    # dereference the function pointer
    fp = (ctypes.c_char*8).from_address(ctypes.addressof(libm.exp))
    fp = struct.unpack('Q', fp[:8])[0]

    # Most common 64-bit conventions pass the first float arg in xmm0
    if sys.platform == 'win32':
        exp = mkfunction([
            push(rbp),
            mov(rbp, rsp),
            mov(rax, struct.pack('Q', fp)),      # Load address of exp()
            sub(rsp, 32),      # MS requires 32-byte shadow on the stack.
            call(rax),         # call exp()  - input arg is already in xmm0
            add(rsp, 32),
            pop(rbp),
            ret(),             # return; now output arg is in xmm0
        ])        
    else:
        exp = mkfunction([
            mov(rax, fp),      # Load address of exp()
            call(rax),         # call exp()  - input arg is already in xmm0
            ret(),             # return; now output arg is in xmm0
        ])

else:
    # dereference the function pointer
    fp = (ctypes.c_char*4).from_address(ctypes.addressof(libm.exp))
    fp = struct.unpack('I', fp[:4])[0]

    if sys.platform == 'win32':
        ret_byts = 8
    else:
        ret_byts = 0
        
    exp = mkfunction([
        push(ebp),         # Need to set up a proper frame here.
        mov(ebp, esp),
        push(dword([ebp+12])),     # Copy input value to new location in stack
        push(dword([ebp+8])),
        mov(eax, fp),      # Load address of exp()
        call(eax),         # call exp() - will clean up stack for us
        mov(esp, ebp),
        pop(ebp),
        ret(ret_byts),            # return; clean stack only in windows
    ])

exp.restype = ctypes.c_double
exp.argtypes = (ctypes.c_double,)

op = 3.1415
out = exp(op)
print("exp(%f) = %f =? %f" % (op, out, math.exp(op)))


print("""
   Example 8: a useful function!
------------------------------------------------------
""")

if ARCH == 64:
    find_first = mkfunction([
        mov(rax, 0),
        label('start_for'),
        cmp(dword([argi[0]+rax*4]), 0),
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
else:
    if sys.platform == 'win32':
        ret_byts = 8
    else:
        ret_byts = 0
        
    find_first = mkfunction([
        mov(eax, 0),
        mov(edx, dword([esp+8])),   # array length
        mov(ecx, dword([esp+4])),   # base array pointer
        label('start_for'),
        cmp(dword([ecx+eax*4]), 0),
        jge('break_for'),
        inc(eax),
        cmp(eax, edx),
        jge('break_for'),
        jmp('start_for'),
        label('break_for'),
        ret(ret_byts)
    ])
        
    find_first.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    find_first.restype = ctypes.c_uint32

find_first.__doc__ = "Return index of first value in an array that is >= 0"

# Create numpy array if possible, otherwise python array
if HAVE_NUMPY:
    data = -1 + np.zeros(10000000, dtype=np.int32)
    data[-1] = 1
    addr = data.ctypes.data
else:
    data = array.array('i', [-1]*1000000)
    data[-1] = 1
    addr = data.buffer_info()[0]

# Find first element >= 0 using asm
start = time.clock()
ind1 = find_first(addr, len(data))
duration1 = time.clock() - start
    
if HAVE_NUMPY:
    # Find the first element >= 0 using numpy
    start = time.clock()
    ind2 = np.argwhere(data >= 0)[0,0]
    duration2 = time.clock() - start
    assert ind1 == ind2
    print("First >= 0: %d" % ind1)
    print("ASM version took %0.2fms" % (duration1*1000)) 
    print("NumPy version took %0.2fms" % (duration2*1000)) 
else:    
    # Find the first element >= 0 using python 
    start = time.clock()
    for i in range(len(data)):
        if data[i] >= 0:
            break
    ind2 = i
    duration2 = time.clock() - start
    assert ind1 == ind2
    print("First >= 0: %d" % ind1)
    print("ASM version took %0.2fms" % (duration1*1000)) 
    print("Python version took %0.2fms" % (duration2*1000)) 
    




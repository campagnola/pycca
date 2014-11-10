from pycc.asm import *
import user


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

#
# Function calls:
#
# 1. Push function arguments onto stack
#       push eax
#       push ebx
# 2. Call relative address of function
#       call dword ptr [102]
# 3. From function, read args by accessing esp + offset
# 4. Set return value to eax
#       mov eax, 456
# 5. Return, pop correct number of argument bytes from stack
#       ret 8



#   Example 4: Call an external function
#------------------------------------------------------
import ctypes
msg = ctypes.create_string_buffer("A double:\n")

## Why do these segv??

#libc = ctypes.cdll.LoadLibrary('libc.so.6')
#printf = mkfunction([
    #mov(rax, ctypes.addressof(msg)),
    #push(rax),
    #mov(rax, ctypes.addressof(libc.printf)),
    #call(rax),
    #pop(0x8),
#])

#printf()

libm = ctypes.cdll.LoadLibrary('libm.so.6')
exp = mkfunction([
    mov(rax, 0x123),
    push(rax),
    mov(rbx, ctypes.addressof(libm.exp)),
    mov(rcx, ptr(rbx))
    call(rcx),
    pop(0x8),
])

exp.restype = ctypes.c_double
print "exp(0x128) = %f" % exp()


# -'- coding: utf-8 -'-

import re, sys, tempfile, subprocess

def phex(code):
    if not isinstance(code, list):
        code = [code]
    for instr in code:
        for c in bytearray(instr):
            sys.stdout.write('%02x' % c)
        print('')

def pbin(code):
    if not isinstance(code, list):
        code = [code]
    for instr in code:
        for c in bytearray(instr):
            sys.stdout.write(format(c, '08b'))
        print('')

def phexbin(code):
    if not isinstance(code, list):
        code = [code]
    for instr in code:
        line = ''
        for c in bytearray(instr):
            line += '%02x ' % c
        line += ' ' * (40 - len(line))
        for c in bytearray(instr):
            line += format(c, '08b') + ' '
        print(line)


def compare(instr):
    """Print instruction's code beside the output of gnu as.
    """
    asm = str(instr)
    print("asm:  " + asm)
    
    try:
        code1 = instr.code
    except Exception as exc1:
        try:
            code2 = as_code(asm)
        except Exception as exc2:
            print(exc1.message)
            print("[pycc and gnu-as both failed.]")
            return
        print("[pycc failed; gnu-as did not]")
        phexbin(code2)
        raise

    try:
        code2 = as_code(asm)
        phexbin(code1)
        phexbin(code2)
        if code1 == code2:
            print("[codes match]")
    except Exception as exc2:
        phexbin(code1)
        print("[gnu-as failed; pycc did not]")
        raise

    
def run_as(asm, quiet=False, check_invalid_reg=False):
    """ Use gnu as and objdump to show ideal compilation of *asm*.
    
    This prepends the given code with ".intel_syntax noprefix\n" 
    """
    #asm = """
    #.section .text
    #.globl _start
    #.align 4
    #_start:
    #""" + asm + '\n'
    if check_invalid_reg:
        for reg in invalid_regs():
            if reg.name in asm:
                raise Exception("asm '%s' contains invalid register '%s'" % (asm, reg.name))
    
    asm = ".intel_syntax noprefix\n" + asm + "\n"
    #print asm
    fname = tempfile.mktemp('.s')
    open(fname, 'w').write(asm)
    if quiet:
        redir = '2>&1'
    else:
        redir = ''
    cmd = 'as {file} -o {file}.o {redirect} && objdump -d {file}.o; rm -f {file} {file}.o'.format(file=fname, redirect=redir)
    #print cmd
    out = subprocess.check_output(cmd, shell=True)
    out = out.decode('ascii').split('\n')
    for i,line in enumerate(out):
        if "Disassembly of section .text:" in line:
            return out[i+3:]
    if not quiet:
        print("--- code: ---")
        print(asm)
        print("-------------")
    exc = Exception("Error running 'as' or 'objdump' (see above).")
    exc.asm = asm
    exc.output = '\n'.join(out)
    raise exc


def as_code(asm, quiet=False, check_invalid_reg=False):
    """Return machine code string for *asm* using gnu as and objdump.
    """
    code = b''
    for line in run_as(asm, quiet=quiet, check_invalid_reg=check_invalid_reg):
        if line.strip() == '':
            continue
        m = re.match(r'\s*[a-f0-9]+:\s+(([a-f0-9][a-f0-9]\s+)+)', line)
        if m is None:
            raise Exception("Can't parse objdump output: \"%s\"" % line)
        byts = re.split(r'\s+', m.groups()[0])
        for byt in byts:
            if byt == '':
                continue
            code += bytearray.fromhex(byt)
    return code


def all_registers():
    """Return all registers defined in asm.register
    """
    from . import register
    regs = []
    for name in dir(register):
        obj = getattr(register, name)
        if isinstance(obj, register.Register):
            regs.append(obj)
    return regs


_invalid_regs = None
def invalid_regs():
    """Return a list of registers that are invalid for GNU-as on this arch.
    
    When running GNU-as in 32-bit mode, the rxx registers do not exist. 
    This would be fine except that instead of generating an error, the 
    compiler simply treats the unknown name as a null pointer [0x0]. To work 
    around this, we first probe AS to see which registers it doesn't know about,
    then raise an exception when attempting to compile using those registers.
    """
    from . import register
    global _invalid_regs
    if _invalid_regs is not None:
        return _invalid_regs

    _invalid_regs = []
    nullptr = as_code('push [0x0]')
    for reg in all_registers():
        try:
            code = as_code('push %s' % reg.name, quiet=True)
            if code == nullptr:
                _invalid_regs.append(reg)
        except:
            pass
    return _invalid_regs
            

def check_valid_pointer(instr='push', pre=None, post=None):
    """Print a table indicating valid pointer modes for each register.
    """
    from . import instructions
    regs = all_registers()
    regs.sort(key=lambda a: (a.bits, a.name))
    checks = ['{reg}', 
              '[{reg}]',   '[2*{reg}]',   '[{reg}+{reg}]',   '[2*{reg}+{reg}]', 
              '[{reg}+1]', '[2*{reg}+1]', '[{reg}+{reg}+1]', '[2*{reg}+{reg}+1]']
    line = '       '
    cols = [len(line)]
    for check in checks:
        add = check.format(reg='reg')+'  '
        cols.append(len(add))
        line += add
    print(line)
        
    icls = getattr(instructions, instr)
    for reg in regs:
        if reg in invalid_regs() or 'mm' in reg.name:
            continue
        line = reg.name + ':'
        line += ' '*(cols[0]-len(line))
        for i,check in enumerate(checks):
            arg = check.format(reg=reg.name)
            arg = eval(arg, {reg.name: reg})
            args = [x for x in [pre, arg, post] if x is not None]
            instr = icls(*args)
            
            try:
                code = instr.code
                err1 = False
            except:
                err1 = True
                
            try:
                code = as_code(str(instr), quiet=True, check_invalid_reg=True)
                err2 = False
            except:
                err2 = True
                
            if err1 and err2:
                add = '.'
            elif err1:
                add = 'GNU'
            elif err2:
                add = 'PY'
            else:
                add = '+++'
            line += add + ' '*(cols[i+1]-len(add))
        print(line)



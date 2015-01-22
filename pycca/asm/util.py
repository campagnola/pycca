# -'- coding: utf-8 -'-

import os, re, sys, pickle, tempfile, subprocess, atexit

try:
    from __builtin__ import long
except ImportError:
    long = int


def phex(code):
    """Print hexadecimal representation of machine code.
    """
    if not isinstance(code, list):
        code = [code]
    for instr in code:
        for c in bytearray(instr):
            sys.stdout.write('%02x' % c)
        print('')

def pbin(code):
    """Print binary representation of machine code.
    """
    if not isinstance(code, list):
        code = [code]
    for instr in code:
        for c in bytearray(instr):
            sys.stdout.write(format(c, '08b'))
        print('')

def phexbin(code):
    """Print hexadecimal and binary representations of machine code.
    
    Argument may be string, bytes, or bytearray.
    """
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
    """Print instruction's code beside the output of GNU-as.
    
    Accepts a single :class:`Instruction <pycca.asm.Instruction>` argument. This is used to determine the 
    machine code differences (hopefully there are none!) between the output
    of an Instruction and the equivalent output from the GNU assembler.
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
            print("[pycca and gnu-as both failed.]")
            return
        print("[pycca failed; gnu-as did not]")
        phexbin(code2)
        raise

    try:
        code2 = as_code(asm)
        sys.stdout.write('py:  ')
        phexbin(code1)
        sys.stdout.write('gnu: ')
        phexbin(code2)
        if code1 == code2:
            print("[codes match]")
    except Exception as exc2:
        phexbin(code1)
        print("[gnu-as failed; pycca did not]")
        raise

    
def run_as(asm, quiet=False, check_invalid_reg=False):
    """Use GNU assembler to compile the *asm* string argument.  
    
    This prepends the given code with ".intel_syntax noprefix\n" before
    compiling and returns only the relevant machine code output. If the
    compile fails, then an exception is raised.
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
    cmd = 'as {file} -o {file}.o 2>&1 && objdump -d {file}.o; rm -f {file} {file}.o'.format(file=fname)
    #print cmd
    out = subprocess.check_output(cmd, shell=True)
    out = out.decode('ascii').split('\n')
    for i,line in enumerate(out):
        if "Disassembly of section .text:" in line:
            return out[i+3:]
    if not quiet:
        print("--- code: ---")
        print(asm)
        print("--- output: ---")
        print('\n'.join(out))
        print("-------------")
        
    errmsg = re.search(r'Error:\s*(.*)\n', '\n'.join(out))
    if errmsg is None:
        errmsg = "Error running 'as' or 'objdump' (see above)."
    else:
        errmsg = errmsg.groups()[0]
    exc = Exception(errmsg)
    exc.asm = asm
    exc.output = '\n'.join(out)
    raise exc


def as_code(asm, quiet=False, check_invalid_reg=False, cache=False):
    """Use GNU assembler to compile the *asm* string argument.  
    
    This prepends the given code with ``.intel_syntax noprefix`` before
    compiling and returns the machine code output converted to a
    bytearray. If the compile fails, then an exception is raised.
    
    If *check_invalid_reg* is True, then an exception will be raised if the
    instruction makes use of a register that is not supported on the current
    architecture (by default, GNU-as silently ignores such symbols).
    
    If *cache* is True, then the result will be cached in 
    ``pycca/asm/gnu_as_cache.pk`` to speed up subsequent requests for the same
    instruction.
    """
    # First try returning cached output
    if cache:
        return as_code_cached(asm, quiet, check_invalid_reg)

    # execute GAS, return compiled bytecode (or raise exception)
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


_as_code_cache = None
def as_code_cached(asm, quiet, check_invalid_reg):
    # return cached output of as_code(). This returns the compiled machine
    # code or raises an exception with a cached error message.
    global _as_code_cache
    path = os.path.dirname(__file__)
    cachefile = os.path.join(path, 'gnu_as_cache.pk')
    key = (asm, check_invalid_reg)
    if _as_code_cache is None:
        if os.path.exists(cachefile):
            if sys.version_info.major == 2:
                _as_code_cache = pickle.load(open(cachefile, 'rb'))
            else:
                _as_code_cache = pickle.load(open(cachefile, 'rb'), fix_imports=True)
        else:
            _as_code_cache = {'__counter__': 0}
        atexit.register(write_as_code_cache)
    if key not in _as_code_cache:
        try:
            _as_code_cache[key] = (True, as_code(asm, quiet, check_invalid_reg, cache=False))
        except Exception as err:
            _as_code_cache[key] = (False, (err.message, err.output))
            raise
        finally:
            cnt = (_as_code_cache['__counter__'] + 1) % 100
            _as_code_cache['__counter__'] = cnt
            if cnt == 0:
                write_as_code_cache()
    ok, output = _as_code_cache[key]
    if ok:
        return output
    else:
        err = Exception(output[0])
        err.output = output[1]
        raise err


def write_as_code_cache():
    # write the cache of as_code() results to disk. 
    global _as_code_cache
    path = os.path.dirname(__file__)
    cachefile = os.path.join(path, 'gnu_as_cache.pk')
    if sys.version_info.major == 2:
        pk = pickle.dumps(_as_code_cache, protocol=0)
    else:
        pk = pickle.dumps(_as_code_cache, protocol=0, fix_imports=True)
    try:
        open(cachefile, 'wb').write(pk)
    except IOError:
        # probably no write permission; skip caching.
        pass


def all_registers():
    """Return all registers defined in asm.register
    (excluding st(i) registers)
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
                code1 = instr.code
                err1 = False
            except:
                err1 = True
                
            try:
                code2 = as_code(str(instr), quiet=True, check_invalid_reg=True)
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
                if code1 != code2:
                    add = 'XXX'
                else:
                    add = '+++'
            line += add + ' '*(cols[i+1]-len(add))
        print(line)



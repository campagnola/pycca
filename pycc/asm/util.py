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
    

def run_as(asm, quiet=False):
    """ Use gnu as and objdump to show ideal compilation of *asm*.
    
    This prepends the given code with ".intel_syntax noprefix\n" 
    """
    #asm = """
    #.section .text
    #.globl _start
    #.align 4
    #_start:
    #""" + asm + '\n'
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

def as_code(asm, quiet=False):
    """Return machine code string for *asm* using gnu as and objdump.
    """
    code = b''
    for line in run_as(asm, quiet=quiet):
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



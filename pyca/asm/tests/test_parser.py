from pytest import raises
from pyca.asm.parser import parse_asm
from pyca.asm import *
from pyca.asm.instruction import Label


def check_typs(code, typs):
    assert len(code) == len(typs)
    for i in range(len(code)):
        assert isinstance(code[i], typs[i])

def test_parser():
    code = parse_asm("""
        label1:
        label2:  # comment
        label3:  ret
        label4:  ret  # comment
        
        ret
        ret #comment
    """)
    
    check_typs(code, [Label, Label, Label, ret, Label, ret, ret, ret])
    
    some_val = 0x123
    asm = parse_asm("""
        label1:
        mov eax, some_val
        je label2
        add [ebx], eax
        label2:
        sub eax, [ecx+ebx*2 + 1]
        jmp label1
        add eax, dword ptr [eax]
        mov bx, word ptr [ebx+eax]
        fadd st(0), st(5)
        ret
    """, {'some_val': some_val})
    page1 = CodePage(asm)
    
    code = [
        label('label1'),
        mov(eax, some_val),
        je('label2'),
        add([ebx], eax),
        label('label2'),
        sub(eax, [ecx + ebx*2 + 1]),
        jmp('label1'),
        add(eax, dword([eax])),
        mov(bx, word([ebx+eax])),
        fadd(st(0), st(5)),
        ret(),
    ]
    page2 = CodePage(code)
    
    assert page1.code == page2.code
    

def test_parse_errors():
    # Error parsing label
    for asm in ['0ax:', ':   ', '012: mov rax, eax', ':: ret']:
        with raises(SyntaxError):
            parse_asm(asm)

    # Duplicate label
    with raises(NameError):
        parse_asm('label1: \nret\nlabel2:\nlabel1:\n')
        
    # Error parsing mnemonic
    for asm in ['label: 0mov', '0mov', 'mo-v', 'mov,rax,rax']:
        with raises(SyntaxError):
            parse_asm(asm)
        
    # Unknown instruction
    with raises(NameError):
        parse_asm('move rax, rax')
    
    # Operand parsing errors
    for asm in ['call .+0x12', 'mov eax,eax,', 'add rax, 1;']:
        with raises(SyntaxError):
            parse_asm(asm)
    with raises(NameError):
        parse_asm('mov rax, rsx')
    
    # Instruction compile errors
    for asm in ['add rax, eax', 'push 0x123456789']:
        with raises(TypeError):
            parse_asm(asm)
    
    
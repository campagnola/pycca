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
    
    asm = parse_asm("""
        label1:
        mov rax, rbx
        je label2
        add [ebx], eax
        label2:
        sub eax, [ecx+ebx*2 + 1]
        jmp label1
        add eax, dword ptr [rax]
        mov bx, word ptr [rbx+rax]
        ret
    """)
    page1 = CodePage(asm)
    code = [
        label('label1'),
        mov(rax, rbx),
        je('label2'),
        add([ebx], eax),
        label('label2'),
        sub(eax, [ecx + ebx*2 + 1]),
        jmp('label1'),
        add(eax, dword([rax])),
        mov(bx, word([rbx+rax])),
        ret(),
    ]
    page2 = CodePage(code)
    
    assert page1.code == page2.code
    

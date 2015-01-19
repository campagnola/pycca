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
    
    
    

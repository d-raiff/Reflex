from .a import A

# Fake alias decorator
def alias():
    pass

# This should not match
class D:
    @alias('fake')
    def fake_aliased(self) -> None:
        return

class D_sub_A(A):
    @A.alias()
    def write(self, x: float) -> str:
        return f'{x:,.0f}'
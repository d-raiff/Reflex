from ..b import B
from reflexsive.core import ReflexsiveMeta, Reflexsive

class F(B):
    @Reflexsive.alias()
    def divide_two_numbers(self, u: int, v: int) -> int:
        return u / v
    
    @Reflexsive.alias(u='x', v='y')
    def divide_two_numbers(self, u: int, v: int) -> int:
        return u / v

class B_meta(metaclass=ReflexsiveMeta):
    pass
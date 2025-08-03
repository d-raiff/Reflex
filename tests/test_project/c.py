from functools import lru_cache
from reflexsive import Reflexsive as Base
from .d import D_sub_A

class C(Base):
    @lru_cache
    def fib(n: int) -> int:
        pass
    
    @Base.alias
    def test(self) -> None:
        pass

class C_sub_D_sub_A(D_sub_A):
    @D_sub_A.alias('sum', x='n1', y='args')
    def compute_sum(self, x: int, y: int) -> int:
        return x + y
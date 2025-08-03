from functools import lru_cache
from pathlib import Path
from reflexsive import Reflexsive

class A(Reflexsive):
    @Reflexsive.alias('log')
    @Reflexsive.alias('open')
    def print(self, *args) -> None:
        print(*args)
        
    @Reflexsive.alias('open', path='p')
    @lru_cache
    @Reflexsive.alias('parse', path='p')
    @lru_cache
    @classmethod
    def read(path: Path) -> str:
        if path.exists():
            return str(path)
        else:
            return 'None'
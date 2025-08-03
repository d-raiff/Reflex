from reflexsive import Reflexsive

class NoAlias:
    @Reflexsive.alias('hi')
    def hello(self) -> None:
        print('hello')
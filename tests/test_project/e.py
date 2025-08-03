import reflexsive

class Reflexsive:
    pass

class E(Reflexsive):
    pass  # This is a false positive if only checking by name

class E_core(reflexsive.core.Reflexsive): 
    pass
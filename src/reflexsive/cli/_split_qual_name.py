# Split out to remove circular dependency

def split_qual_name(qual_name: str) -> tuple[str, str]:
    '''
    Split a dotted qualified name into (module_name, real_name).
    E.g., 'a.b.C' → ('a.b', 'C')
    '''
    parts = qual_name.rsplit('.', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    else:
        return '', parts[0]
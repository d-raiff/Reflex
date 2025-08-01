# Reflexsive

<p align="center">
  <a href="https://github.com/d-raiff/Reflexsive/actions/workflows/ci-release.yml">
    <img src="https://github.com/d-raiff/Reflexsive/actions/workflows/ci-release.yml/badge.svg" alt="ci-release"/>
  </a>
  <a href="https://github.com/d-raiff/Reflexsive/actions/workflows/ci-release.yml">
    <img src="https://codecov.io/gh/d-raiff/Reflex/branch/main/graph/badge.svg" alt="codedev"/>
  </a>
  <a href="https://github.com/d-raiff/Reflexsive/actions/workflows/ci-release.yml">
    <img src="https://img.shields.io/github/license/d-raiff/Reflexsive.svg" alt="license"/>
  </a>
</p>

A lightweight Python library that enables concise method aliasing with optional argument remapping. Designed for ergonomic command interfaces, alternative method names, and API compatibility layers.

---

## ✨ Features

- Define aliases for class methods with different argument names.
- Supports instance, static, and class methods.
- Optional argument renaming per alias.
- Flexible usage with or without arguments.
- Stub file (`.pyi`) generation for autocompletion support.
- Optional prefixing for namespacing aliases.
- Strict conflict checking to prevent ambiguous mappings.

---

## 🔧 Installation

```bash
pip install reflexsive
```

## 🚀 Usage
```python
from reflexsive import Reflexsive

class MyAPI(Reflexsive):
    @Reflexsive.alias('short', username='u', password='p')
    def authenticate(self, username, password):
        return f"{username}:{password}"

obj = MyAPI()
print(obj.authenticate('admin', '123'))     # 'admin:123'
print(obj.short('admin', '123'))            # Same result using alias
print(obj.short(u='admin', p='123'))        # Keyword aliasing
```

## ⚙️ Configuration Options

When using `class A(Reflexsive, ...)`, you can pass configuration flags:

| Option                  | Type  | Default | Description                                 |
|-------------------------|-------|---------|---------------------------------------------|
| allow_kwargs_override   | bool  | False   | Allow alias names to override `**kwargs`    |
| expose_alias_map        | bool  | False   | *(Planned)* Expose alias map on class       |
| docstring_alias_hints   | bool  | True    | *(Planned)* Include alias info in docstrings|
| alias_prefix            | str   | None    | Prefix added to all alias names             |

### Example 1: Without options
```python
class Example(Reflexsive):
    ...
```

### Example 2: With options
```python
class Example(Reflexsive, create_pyi_stub=True, alias_prefix='a_'):
    ...
```

## 🧪 Testing

Tests are provided using pytest.\n

Tests cover:
  - Alias mapping (positional and keyword)
  - Class/Static method support
  - Error handling for conflicting or invalid aliases
  - Stub generation
  - Prefix options
  - Edge cases (built-in names, decorator order, etc.)

## ❗ Exception Types

The library defines the following custom exceptions:

  - `AliasNameConflictError`: Raised when an alias name conflicts with another method or alias.
  - `AliasArgumentError`: Raised when alias mappings include invalid or forbidden parameters (e.g., `*args`).
  - `AliasConfigurationError`: Raised when invalid configuration options are passed to `@aliased_class`.

## Notes

- Using classmethod/staticmethod decorators before `@alias` makes Pylance complain - but does work at runtime 
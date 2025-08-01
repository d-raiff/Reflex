from typing import Any, Callable, Dict, Optional, Tuple, Mapping, Type, TypeVar, Union, cast
import inspect

from .config import ReflexsiveOptions
from .errors import ReflexsiveArgumentError, ReflexsiveNameConflictError

FuncType = Callable[..., Any]
Decorated = Union[FuncType, staticmethod, classmethod]
    
def create_alias_function(
        fn: Union[Callable[..., Any], staticmethod, classmethod],
        alias_name: str,
        arg_map: Optional[Mapping[str, str]],
        options: ReflexsiveOptions
    ) -> Any:
    '''
    Create a dynamically wrapped alias function that remaps keyword arguments
    to the original function's argument names.

    This supports:
    - [ ] Freestanding functions
    - [X] Instance functions
    - [X] Classmethod functions
    - [X] Staticmethod functions

    Parameters
    ----------
    fn (Callable[..., Any]):
        The original method or function to alias.

    alias_name (str):
        The alias name to expose on the class.

    arg_map (Optional[Mapping[str, str]]):
        A dictionary mapping original argument names to their shorter alias forms.

    options (ReflexsiveOptions):
        Options used when creating the alias function.

    Returns
    -------
    Callable:
        A new method with remapped arguments, the same behavior as the original, and a short alias name.
    '''
    reverse_map = {v: k for k, v in arg_map.items()} if arg_map else {}

    real_fn = fn.__func__ if isinstance(fn, (staticmethod, classmethod)) else fn
    sig = inspect.signature(real_fn)

    # Determine first argument name (self/cls) if present
    params = list(sig.parameters.values())
    needs_first_arg = (
        params and
        params[0].name in ('self', 'cls') and
        params[0].kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.POSITIONAL_ONLY)
    )
    first_arg_name = params[0].name if needs_first_arg else None

    # Validate that all keys in arg_map match named parameters
    valid_param_names = {
        p.name for p in sig.parameters.values()
        if p.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
            inspect.Parameter.POSITIONAL_ONLY
        )
    }

    for arg in (arg_map or {}):
        if not options.allow_kwargs_override and arg not in valid_param_names:
            raise ReflexsiveArgumentError(
                f'Cannot alias parameter \'{arg}\'; it is not an explicitly named parameter of \'{real_fn.__name__}\'.'
            )

    def alias_fn(*args: Any, **kwargs: Any) -> Any:
        # Step 1: Disallow original param names in kwargs
        if arg_map:
            for original_name in arg_map:
                if original_name in kwargs:
                    raise ReflexsiveArgumentError(
                        f'Argument \'{original_name}\' is not valid in alias \'{alias_name}\'; '
                        f'use \'{arg_map[original_name]}\' instead.'
                    )   

        # Step 2: remap keyword arguments first
        remapped_kwargs = {
            reverse_map.get(k, k): v
            for k, v in kwargs.items()
        }

        # Step 4: Bind arguments
        bound = sig.bind_partial(*args, **remapped_kwargs)
        bound.apply_defaults()

        # Step 4: remove 'self' and split variatic args before passing to fn
        args_list       = []
        var_args_list   = []
        kwargs_dict     = {}

        for name, value in bound.arguments.items():
            if name == first_arg_name:
                continue

            param = sig.parameters[name]
            if param.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                args_list.append(value)
            elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                var_args_list.extend(value)
            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                kwargs_dict[name] = value
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                kwargs_dict.update(value)

        # Add back the first argument (self/cls) if needed
        if first_arg_name is not None:
            bound_obj = bound.arguments[first_arg_name]
            return real_fn(bound_obj, *args_list, *var_args_list, **kwargs_dict)
        else:
            return real_fn(*args_list, *var_args_list, **kwargs_dict)
    
    alias_fn.__name__ = alias_name
    alias_fn.__doc__ = f'[alias for {real_fn.__name__}]'

    if isinstance(fn, staticmethod):
        return staticmethod(alias_fn)
    elif isinstance(fn, classmethod):
        return classmethod(alias_fn)
    else:
        return alias_fn
    
class ReflexsiveMeta(type):
    '''
    Metaclass that constructs alias functions based on function flags set by the `@Reflexsive.alias`
    decorator. Optionally takes parameters to modify behavior. Should use `Reflexsive` instead.\n

    This usage pattern for this metaclass is as follows:

        >>> class MyClass(metaclass=ReflexsiveMeta, **kwargs):
        >>>     ...
        
    Options
    -------
        - allow_kwargs_override (bool):
            If True, allows alias-invoked methods to override kwargs in the original signature.
            ✅ Not yet implemented.

        - expose_alias_map (bool):
            If True, exposes the internal alias map as a class attribute.
            🚫 Not yet implemented.

        - docstring_alias_hints (bool):
            If True, includes alias information in the decorated method docstrings.
            🚫 Not yet implemented.

        - alias_prefix (Optional[str]):
            Prefix applied to all generated aliases for disambiguation or namespacing.
            ✅ Implemented.

    Raises
    ------
        ReflexsiveNameConflictError: If any alias has a conflicting name with another alias or another class member.
        ReflexsiveArgumentError: If an invalid argument is attempted to be aliased.
        ReflexsiveConfigurationError: If an invalid option is passed to the metaclass.
    '''

    def __new__(cls, name: str, bases: Tuple, namespace: Dict[str, Any], **kwargs: Any) -> Type:
        options = ReflexsiveOptions(**kwargs)
        alias_map: Dict[str, str] = {}

        for attr_name, attr_val in list(namespace.items()):
            if attr_name.startswith('__') and attr_name.endswith('__'):
                continue

            unwrapped = attr_val if not isinstance(attr_val, (staticmethod, classmethod)) else attr_val.__func__
            if not callable(unwrapped):
                continue

            func = unwrapped
            cls_or_static = attr_val

            if hasattr(func, '_aliases'):
                if options.alias_prefix:
                    func._aliases = {
                        f"{options.alias_prefix}{k}": v for k, v in func._aliases.items()
                    }

                for alias, argmap in func._aliases.items():
                    if alias in namespace:
                        if alias in alias_map:
                            raise ReflexsiveNameConflictError(
                                f"Class '{name}' already has alias '{alias}' from '{alias_map[alias]}'."
                            )
                        raise ReflexsiveNameConflictError(
                            f"Alias '{alias}' conflicts with an existing attribute on class '{name}'."
                        )
                    alias_fn = create_alias_function(cls_or_static, alias, argmap, options)
                    namespace[alias] = alias_fn
                    alias_map[alias] = func.__name__

        return super().__new__(cls, name, bases, namespace)
    
class Reflexsive(metaclass=ReflexsiveMeta):
    '''
    Metaclass wrapper that constructs alias functions based on function flags set by the `@Reflexsive.alias`
    decorator. Optionally takes parameters to modify behavior.\n

    This usage pattern for this metaclass is as follows:

        >>> class MyClass(Reflexsive, **kwargs):
        >>>     ...
        
    Options
    -------
        - allow_kwargs_override (bool):
            If True, allows alias-invoked methods to override kwargs in the original signature.
            ✅ Not yet implemented.

        - expose_alias_map (bool):
            If True, exposes the internal alias map as a class attribute.
            🚫 Not yet implemented.

        - docstring_alias_hints (bool):
            If True, includes alias information in the decorated method docstrings.
            🚫 Not yet implemented.

        - alias_prefix (Optional[str]):
            Prefix applied to all generated aliases for disambiguation or namespacing.
            ✅ Implemented.

    Raises
    ------
        ReflexNameConflictError: If any alias has a conflicting name with another alias or another class member.
        ReflexArgumentError: If an invalid argument is attempted to be aliased.
        ReflexsiveConfigurationError: If an invalid option is passed to the metaclass.
    '''
    @staticmethod
    def alias(_alias: str, **arg_map: Any) -> Callable[[Decorated], Decorated]:
        '''
        Declare an alias for a method and optionally remap argument names.

        This decorator registers a short alias name for a method, optionally providing a mapping
        from original argument names to shorter aliases. The alias metadata is stored on the function
        for later processing by the `@Reflexsive.alias` system, which creates the actual bound aliases.

        This decorator supports instance methods, static methods, and class methods.

        Parameters
        ----------
        _alias (str):
            The alias name to be registered for the target method.

        **arg_map:
            Optional keyword arguments that map original argument names to their alias names.
            Argument names such as 'args' and 'kwargs' (i.e., *args and **kwargs) are reserved
            and cannot be aliased here.

        Returns
        -------
        Callable:
            A decorator that attaches alias metadata to the decorated function.

        Raises
        ------
        ReflexsiveArgumentError:
            If the alias attempts to rename reserved arguments like '*args' or '**kwargs'.

        ReflexsiveNameConflictError:
            If the alias name is already registered for the same function.
        '''
        def decorator(fn: Decorated) -> Decorated:
            # Unwrap method to get underlying function
            if isinstance(fn, staticmethod):
                real_fn = cast(Callable[..., Any], fn.__func__)
            elif isinstance(fn, classmethod):
                real_fn = cast(Callable[..., Any], fn.__func__)
            else:
                real_fn = cast(Callable[..., Any], fn)
            
            # We can check args and kwargs, but we have to check if the arg_map entry is declared vs kwargs
            # and reject/accept in the class decorator, as its determiend by a option
            for original_name in arg_map:
                if original_name in ('args', 'kwargs'):
                    raise ReflexsiveArgumentError(
                        f'Cannot alias parameter \'{original_name}\'; \'*args\' and \'**kwargs\' are reserved.'
                    )
            
            # Preserve existing aliases if already decorated
            existing_aliases = getattr(real_fn, '_aliases', {})
            if _alias in existing_aliases:
                raise ReflexsiveNameConflictError(
                    f'Alias name \'{_alias}\' is already defined for function \'{real_fn.__name__}\'.'
                )

            setattr(real_fn, "_aliases", {**existing_aliases, _alias: arg_map})
            if not hasattr(real_fn, "_source_filename"):
                setattr(real_fn, "_source_filename", real_fn.__code__.co_filename)
            
            # Re-wrap for correct method binding
            if isinstance(fn, staticmethod):
                return staticmethod(real_fn)
            elif isinstance(fn, classmethod):
                return classmethod(real_fn)
            else:
                return real_fn
            
        return decorator
"""cache.py"""
from collections import OrderedDict
from inspect import signature, Signature
from typing import Any, Callable, Dict, List

from fastapi import Request, Response

from fastapi_redis_cache.types import ArgType, SigParameters

ALWAYS_IGNORE_ARG_TYPES = [Response, Request]


def get_cache_key(func: Callable, ignore_arg_types: List[ArgType], *args: List, **kwargs: Dict) -> str:
    """Ganerate a string that uniquely identifies the function and values of all arguments."""
    if not ignore_arg_types:
        ignore_arg_types = []
    ignore_arg_types.extend(ALWAYS_IGNORE_ARG_TYPES)
    sig = signature(func)
    sig_params = sig.parameters
    func_args = get_func_args(sig, *args, **kwargs)
    args_str = get_args_str(sig_params, func_args, ignore_arg_types)
    return f"{func.__module__}.{func.__name__}({args_str})"


def get_func_args(sig: Signature, *args: List, **kwargs: Dict) -> "OrderedDict[str, Any]":
    """Return a dict object containing the name and value of all function arguments."""
    func_args = sig.bind(*args, **kwargs)
    func_args.apply_defaults()
    return func_args.arguments


def get_args_str(sig_params: SigParameters, func_args: "OrderedDict[str, Any]", ignore_arg_types: List[ArgType]) -> str:
    """Return a string with the name and value of all args whose type is not included in `ignore_arg_types`"""
    return "_".join(
        f"{arg}={val}" for arg, val in func_args.items() if not ignore_arg_type(arg, sig_params, ignore_arg_types)
    )


def ignore_arg_type(arg_name: str, sig_params: SigParameters, ignore_arg_types: List[ArgType]) -> bool:
    """Check if a function arg is of a type that must NOT be used to construct the cache key."""
    return any(sig_params[arg_name].annotation is ignore_type for ignore_type in ignore_arg_types)

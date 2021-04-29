"""cache.py"""
from collections import OrderedDict
from inspect import signature, Signature
from typing import Any, Callable, Dict, List

from fastapi import Request, Response

from fastapi_redis_cache.types import ArgType, SigParameters

ALWAYS_IGNORE_ARG_TYPES = [Response, Request]


def get_cache_key(prefix: str, ignore_arg_types: List[ArgType], func: Callable, *args: List, **kwargs: Dict) -> str:
    """Ganerate a string that uniquely identifies the function and values of all arguments.

    Args:
        prefix (`str`): Customizable namespace value that will prefix all cache keys.
        ignore_arg_types (`List[ArgType]`): Each argument to the API endpoint function is
            used to compose the cache key by calling `str(arg)`. If there are any keys that
            should not be used in this way (i.e., because their value has no effect on the
            response, such as a `Request` or `Response` object) you can remove them from
            the cache key by including their type as a list item in ignore_key_types.
        func (`Callable`): Path operation function for an API endpoint.

    Returns:
        `str`: Unique identifier for `func`, `*args` and `**kwargs` that can be used as a
            Redis key to retrieve cached API response data.
    """

    if not ignore_arg_types:
        ignore_arg_types = []
    ignore_arg_types.extend(ALWAYS_IGNORE_ARG_TYPES)
    ignore_arg_types = list(set(ignore_arg_types))
    prefix = f"{prefix}:" if prefix else ""

    sig = signature(func)
    sig_params = sig.parameters
    func_args = get_func_args(sig, *args, **kwargs)
    args_str = get_args_str(sig_params, func_args, ignore_arg_types)
    return f"{prefix}{func.__module__}.{func.__name__}({args_str})"


def get_func_args(sig: Signature, *args: List, **kwargs: Dict) -> "OrderedDict[str, Any]":
    """Return a dict object containing the name and value of all function arguments."""
    func_args = sig.bind(*args, **kwargs)
    func_args.apply_defaults()
    return func_args.arguments


def get_args_str(sig_params: SigParameters, func_args: "OrderedDict[str, Any]", ignore_arg_types: List[ArgType]) -> str:
    """Return a string with the name and value of all args whose type is not included in `ignore_arg_types`"""
    return ",".join(
        f"{arg}={val}" for arg, val in func_args.items() if sig_params[arg].annotation not in ignore_arg_types
    )

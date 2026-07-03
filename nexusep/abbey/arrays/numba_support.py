"""
ABBEY optional numba support.

Phase 18:
    Selective njit acceleration.

Important:
    Public API must not depend on numba.
    If numba is missing, these decorators return plain Python functions.
"""

try:
    from numba import njit
    NUMBA_AVAILABLE = True
except Exception:
    NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):
        """
        Fallback njit replacement.

        Supports both:

            @njit
            def f(...)

        and:

            @njit(cache=True)
            def f(...)
        """
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]

        def decorator(func):
            return func

        return decorator


def optional_njit(*args, **kwargs):
    """
    Alias used by ABBEY numba modules.
    """
    return njit(*args, **kwargs)


def numba_status():
    return {
        "numba_available": NUMBA_AVAILABLE,
    }
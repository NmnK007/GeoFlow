"""Peak resident process memory (includes Python and native libraries)."""

import sys


def peak_mib():
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (key, ctypes.c_size_t)
                for key in ("peak", "current", "a", "b", "c", "d", "e", "f")
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not ctypes.windll.psapi.GetProcessMemoryInfo(
            wintypes.HANDLE(-1), ctypes.byref(counters), counters.cb
        ):
            raise ctypes.WinError()
        return counters.peak / 2**20
    import resource

    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / (2**20 if sys.platform == "darwin" else 1024)

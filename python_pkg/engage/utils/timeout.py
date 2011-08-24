"""
utilities for timeouts, retrying
"""

import time


def retry(fn, tries, time_between_tries_in_fp_secs, *args, **kwargs):
    for i in range(tries):
        if fn(*args, **kwargs):
            return True
        else:
            time.sleep(time_between_tries_in_fp_secs)
    return False

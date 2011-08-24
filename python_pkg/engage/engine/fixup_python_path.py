
# fix path if necessary (if running from source or running as test)

import sys
import os.path

try:
    import engage.utils
except:
    sys.exc_clear()
    dir_to_add_to_python_path = os.path.abspath(os.path.expanduser(os.path.join(os.path.dirname(__file__), "../..")))
    if not (dir_to_add_to_python_path in sys.path):
        sys.path.append(dir_to_add_to_python_path)


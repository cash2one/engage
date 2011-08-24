import os
import os.path


def find_python_module(qualified_module_name, root_dir):
    """This utility function looks for a python module
    under the specified directory. It returns the full
    path to the directory above the module. This directory can
    be added to sys.path to successfully import the module. If
    the module is not found, we return None.

    There is a special case for when the root directory is the
    first (topmost) component of the module. In this case, we return
    the directory above the root directory.
    """
    def check_module_file(parent_dir, module_name):
        module_file = os.path.join(parent_dir, module_name + ".py")
        if os.path.exists(module_file):
            return True
        else:
            return False
    
    def check_dir(current_dir, module_list):
        """Return True if the module_list exists in the current directory"""
        if len(module_list)==1:
            return check_module_file(current_dir, module_list[0])
        else:
            next_dir = os.path.join(current_dir, module_list[0])
            if os.path.isdir(next_dir) and os.path.exists(os.path.join(next_dir, "__init__.py")):
                return check_dir(next_dir, module_list[1:])
            else:
                return False

    full_module_list = qualified_module_name.split('.')
    for (dirname, subdirs, files) in os.walk(os.path.abspath(os.path.expanduser(root_dir))):
         module_path = check_dir(dirname, full_module_list)
         if module_path:
             return dirname
    # if we get here, the module isn't under root_dir. we have a special case for when
    # current_dir is the top directory of the module.
    if check_dir(os.path.dirname(root_dir), full_module_list):
        return os.path.dirname(root_dir)
    else:
        return None



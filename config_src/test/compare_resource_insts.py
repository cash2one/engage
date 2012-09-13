#!/usr/bin/env python
"""Script to compare to resource instances. Prints mismatches to stderr.
Exits with 0 if successful, 1 if there were one or more mismatches, or 2 if there
was another problem
"""

import json
import sys
import os.path


def get_resource_map_and_id_set(inst_list):
    m = {}
    s = set()
    for inst in inst_list:
        iid = inst['id']
        s.add(iid)
        m[iid] = inst
    return (m, s)

def compare_objs(prop, exp, act):
    if type(exp)!=type(act):
        sys.stderr.write("%s: types mismatch (%s and %s)\n" %
                         (prop, type(exp), type(act)))
        return 1
    if isinstance(exp, list):
        if len(exp) != len(act):
            sys.stderr.write("%s: list length mismatch (%d and %d)\n" %
                             (prop, len(exp), len(act)))
            return 1
        else:
            errcnt = 0
            for i in range(0, len(exp)):
                errcnt += compare_objs("%s[%d]" % (prop, i), exp[i], act[i])
            return errcnt
    elif isinstance(exp, dict):
        k_exp = set(exp.keys())
        k_act = set(act.keys())
        if k_exp != k_act:
            sys.stderr.write("%s: Properties differ between expected and actual: %s" %
                             (prop, k_exp.symmetric_difference(k_act).__repr__()))
            return 1
        else:
            errcnt = 0
            for k in exp.keys():
                errcnt += compare_objs("%s.%s" % (prop, k), exp[k], act[k])
            return errcnt
    else:
        if exp != act:
            sys.stderr.write("%s: Values differ (%s and %s)\n" %
                             (prop, exp, act))
            return 1
        else:
            return 0
                    
        
        
def compare(exp, act):
    errcnt = 0
    (exp_m, exp_s) = get_resource_map_and_id_set(exp)
    (act_m, act_s) = get_resource_map_and_id_set(act)
    if act_s != exp_s:
        sys.stderr.write("Set of resources does not match. Differences are: %s\n" %
                         exp_s.symmetric_difference(act_s))
        errcnt += 1
    for r in exp:
        assert r.has_key('id'), "Bad exp resource %s" % r.__repr__()
        if act_m.has_key(r['id']):
            errcnt += compare_objs(r['id'], r, act_m[r['id']])
    
    sys.stdout.write("%d errors found\n" % errcnt)
    return 0 if errcnt==0 else 1

def main(argv=sys.argv[1:]):
    if len(argv)!=2:
        sys.stderr.write("Incorrect number of filenames. Should be:\n%s expected_file actual_file\n" %
                         sys.argv[0])
        return 2
    exp_filename = argv[0]
    act_filename = argv[1]
    if not os.path.exists(exp_filename):
        sys.stderr.write("File %s does not exist\n" % exp_filename)
        return 2
    if not os.path.exists(act_filename):
        sys.stderr.write("File %s does not exist\n" % act_filename)
        return 2
    try:
        with open(exp_filename, "rb") as f:
            exp_data = json.load(f)
        with open(act_filename, "rb") as f:
            act_data = json.load(f)
    except Exception, e:
        sys.stderr.write("%s\n" % str(e))
        return 2
    
    return compare(exp_data, act_data)


if __name__ == "__main__":
    sys.exit(main())

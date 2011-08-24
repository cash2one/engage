import re

# start = group(one_or_more(complement_char_set(">=<")))
# comp = group(or_match(lit(">"), lit(">="), lit("==")))
# end = line_ends_with(group(one_or_more(complement_char_set(">=<"))))
# full = concat(start, comp, end)

def parse_requirements(fp, parse_version_constraints=False):
    requirements = []
    dependencies = []
    for line in fp.read().split('\n'):
        if re.match(r'(\s*#)|(\s*$)', line):
            continue
        if re.match(r'\s*-r\s+', line):
            dependencies.append(re.sub(r'\s*-r\s+', '', line))
        elif re.match(r'\s*-f\s+', line):
            requirements.append(re.sub(r'\s*-f\s+[^\s]*\s+([^\>\<\=]*)[\>|\>\=|\=\=](.*)$', r'\1', line))
        elif re.match(r'\s*--find-links\s*', line):
            requirements.append(re.sub(r'\s*--find-links\s+[^\s]*\s+([^\>\<\=]*)[\>|\>\=|\=\=](.*)$', r'\1', line))
        elif re.match(r'\s*-e\s+', line):
            requirements.append(re.sub(r'\s*-e\s+.*#egg=(.*)$', r'\1', line))
        elif re.match(r'(.*)[\>|\>\=|\=\=](.*)$', line):
            if parse_version_constraints:
                m = re.match('([^>=<]+)(\\>|(?:\\>\\=)|(?:\\=\\=))([^>=<]+)$', line)
                assert m, "Did not get match for line %s" % line
                requirements.append((m.group(1), m.group(2), m.group(3)),)
            else:
                requirements.append(re.sub(r'([^\>\=\<]*)[\>|\>\=|\=\=](.*)$', r'\1', line))
        elif re.match(r'\s*index-url\s*', line):
            print 'Warning: --index-url not supported yet.'
            pass
        else:
            requirements.append(line)
    return (requirements, dependencies)

def parse_dependency_links(fp):
    dependency_links = []
    for line in fp.read().split('\n'):
        if re.match(r'\s*-[ef]\s+', line):
            dependency_links.append(re.sub(r'\s*-[ef]\s+', '', line))
    return dependency_links

def parse(fname, parse_version_constraints=False):
    packages = []
    fset = set()
    files = [fname]
    while (files):
        f = files.pop()
        if f in fset:
            print 'Warning: circular dependency in requirements.txt file: %s' % f
            break
        fset.add(f)
        try:
            fp = open(f, 'r')
        except IOError:
            print 'Warning: requirements file %s not found for reading' % f
            break
        (reqs, deps) = parse_requirements(fp, parse_version_constraints)
        fp.close()
        packages = packages + reqs
        files = files + deps
    return packages

# Regexp for matching a file package
# version = group(concat(one_or_more(character_set("0-9")), zero_or_more(concat(lit("."), one_or_more(character_set("0-9"))))))
# file_ext = or_match(lit(".tar.gz"), lit(".tgz"), lit(".zip"))
# pkg_file = concat(line_starts_with(lit(pkg_name)), lit("-"), version, line_ends_with(file_ext))
def _get_pkg_file_re(pkg):
    return re.compile('^(?:' + pkg + ')\\-([0-9]+(?:\\.[0-9]+)*)(?:(?:\\.tar\\.gz)|(?:\\.tgz)|(?:\\.zip))$')

def compare_versions(v1, v2):
    """Compare two version numbers. If v1 > v2, return 1. If v1 < v2, return -1.
    If v1 == v2, return 0
    """
    if v1==v2:
        return 0
    v1l = v1.split('.')
    v2l = v2.split('.')
    v1_length = len(v1l)
    v2_length = len(v2l)
    for i in range(v1_length):
        if i==v2_length:
            return 1
        elif int(v1l[i])>int(v2l[i]):
            return 1
        elif int(v2l[i])>int(v1l[i]):
            return -1
    # if we get here, everything equal up to len(v1)
    assert v2_length>v1_length, "problem in version compare(%s, %s)" % (v1, v2)
    return -1

def get_local_files_matching_requirements(requirements_file, package_cache_files):
    """Give a requirements file and a list of files in a package cache,
    return the files from the list that best satisfy the requirements.
    """
    packages = parse(requirements_file, parse_version_constraints=True)
    matching_files = {}
    files_by_prefix = {}
    for f in package_cache_files:
        prefix = f.split('-')[0]
        if files_by_prefix.has_key(prefix):
            files_by_prefix[prefix].append(f)
        else:
            files_by_prefix[prefix] = [f]
        
    for pkg in packages:
        if isinstance(pkg, tuple):
            assert(len(pkg)==3)
            pkg_name = pkg[0]
            pkg_version = pkg[2]
            pkg_comp = pkg[1]
        elif isinstance(pkg, str) or isinstance(pkg, unicode):
            pkg_name = pkg
            pkg_version = None
            pkg_comp = None
        else:
            continue
        prefix = pkg_name.split("-")[0]
        files = files_by_prefix[prefix] if files_by_prefix.has_key(prefix) else []
        regexp = _get_pkg_file_re(pkg_name)
        for f in files:
            m = regexp.match(f)
            if not m: continue
            file_version = m.group(1)
            # does f satisfy the requirement?
            if pkg_comp:
                cv = compare_versions(file_version, pkg_version)
                if (pkg_comp=='==' and cv==0) or \
                   (pkg_comp=='>=' and (cv==0 or cv==1)) or \
                   (pkg_comp=='>' and cv==1):
                    satisfied = True
                else:
                    satisfied = False
            else:
                satisfied = True
            if satisfied:
                if matching_files.has_key(pkg_name):
                    v_other = regexp.match(matching_files[pkg_name]).group(1)
                    if compare_versions(file_version, v_other)==1:
                        matching_files[pkg_name] = f
                else:
                    matching_files[pkg_name] = f
    return matching_files.values()
        
        
        
if __name__ == '__main__':
    packages = parse('requirements.txt', parse_version_constraints=True) 
    print packages

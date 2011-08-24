"""install_plan: create a plan for the installation, given an install
solution. The plan is just a list of resource instances, sorted by
dependency order. Thus, if resource r1 appears in the plan before r2, then
r1 has no dependencies for r2. Note that this is an over-specification of the
plan - one could instead return a a list of sets, where each resource in a
set can be installed in parallel. This could be accomodated pretty easily,
but we'll keep things simple for now.
"""

import sys
import os.path

# fix path if necessary (if running from source or running as test)
import fixup_python_path

from engage.utils.log_setup import setup_engine_logger
from engage.utils.digraph import digraph

logger = setup_engine_logger(__name__)

class InstallPlanError(Exception):
    pass


class _DepGraph:
    def __init__(self):
        self.node_map = {}
        self.starting_nodes = set()
        self.working_set_node_ids = None
        self.total_links = 0

    def create_node(self, resource):
        node = _DepGraphNode(resource, self)
        self.node_map[resource.id] = node
        self.starting_nodes.add(resource.id)

    def all_nodes(self):
        return self.node_map.values()

    def is_start_set_empty(self):
        return len(self.starting_nodes)==0

    def init_working_set_from_start_set(self):
        """Initialize the working set from the start set. To make this
        algorithm deterministic, we sort the node ids and store in a list"""
        self.working_set_node_ids = list(self.starting_nodes)
        self.working_set_node_ids.sort()

    def take_node_from_working_set(self):
        node_id = self.working_set_node_ids.pop(0)
        return self.node_map[node_id]

    def add_node_to_working_set(self, node):
        self.working_set_node_ids.append(node.resource.id)

    def is_working_set_empty(self):
        return len(self.working_set_node_ids)==0

    def get_node(self, node_id):
        return self.node_map[node_id]

    def add_all_dependencies(self):
        """Add all node dependencies in the graph"""
        for node in self.all_nodes():
            if node.resource.inside!=None:
                node.add_dependency(node.resource.inside.id)
            for resource_ref in node.resource.environment:
                node.add_dependency(resource_ref.id)
            for resource_ref in node.resource.peers:
                node.add_dependency(resource_ref.id)


class _DepGraphNode:
    def __init__(self, resource, graph):
        self.resource = resource
        self.graph = graph
        self.depends_on_set = set()
        self.dependent_set = set()

    def add_dependency(self, depends_on_node_id):
        """Add a dependency to this node. This node depends on
        depends_on_node_id.
        """
        logger.debug("Added resource dependency: %s depends on %s" % 
                     (self.resource.id, depends_on_node_id))
        if not self.graph.node_map.has_key(depends_on_node_id):
            raise InstallPlanError, \
                "Resource %s depends on resource %s, which is not in install solution" % \
                (self.resource.id, depends_on_node_id)
        depends_on_node = self.graph.node_map[depends_on_node_id]
        depends_on_node.dependent_set.add(self.resource.id)
        self.depends_on_set.add(depends_on_node_id)
        self.graph.starting_nodes.discard(self.resource.id)
        self.graph.total_links = self.graph.total_links + 1

    def remove_dependency(self, dependent_node):
        """Remove a link between this node and the dependent node"""
        assert self.resource.id in dependent_node.depends_on_set, \
           "remove_dependency: node %s not in depends_on_set for %s" % \
           (self.resource.id, dependent_node.resource.id)
        assert dependent_node.resource.id in self.dependent_set, \
           "remove_dependency: node %s not in dependent_set for %s" % \
           (dependent_node.resource.id, self.resource.id)
        self.dependent_set.remove(dependent_node.resource.id)
        dependent_node.depends_on_set.remove(self.resource.id)
        self.graph.total_links = self.graph.total_links - 1


def create_install_plan(resource_list):
    """The main entry point for the install_plan module. Given a resource
    list representing an install solution, return a new list which is
    ordered by install dependency. We include resources that have already
    been installed, as, if they are services, we need to check that they are
    available.

    The algorithm used here is from:
    Kahn, A. B. (1962), "Topological sorting of large networks",
      Communications of the ACM 5 (11): 558-562.

    See the wikipedia page on Topological_sort for a good discussion.

    >>> import engage.drivers.resource_metadata as resource_metadata
    >>> #logger.setLevel(logging.DEBUG)
    >>> #logger.addHandler(logging.StreamHandler(sys.stdout))
    >>> # For our unit test, we first build a plan for the following resources:
    >>> #  r1: no dependencies
    >>> #  r2: depends on r1
    >>> #  r3: depends on r1 and r2
    >>> #  r4: depends on r1 and r3
    >>> #  r5: depends on r2
    >>> r1_key = {"name":"r1_type"}
    >>> r2_key = {"name":"r2_type"}
    >>> r3_key = {"name":"r3_type"}
    >>> r4_key = {"name":"r4_type"}
    >>> r5_key = {"name":"r5_type"}
    >>> r1 = resource_metadata.ResourceMD("r1", r1_key)
    >>> r2 = resource_metadata.ResourceMD("r2", r2_key,
    ...        inside=resource_metadata.ResourceRef("r1", r1_key))
    >>> r3 = resource_metadata.ResourceMD("r3", r3_key,
    ...        inside=resource_metadata.ResourceRef("r1", r1_key),
    ...        peers=[resource_metadata.ResourceRef("r2", r2_key)])
    >>> r4 = resource_metadata.ResourceMD("r4", r4_key,
    ...        inside=resource_metadata.ResourceRef("r1", r1_key),
    ...        environment=[resource_metadata.ResourceRef("r3", r3_key)])
    >>> r5 = resource_metadata.ResourceMD("r5", r5_key,
    ...        peers=[resource_metadata.ResourceRef("r2", r2_key)])
    >>> plan = create_install_plan([r2, r5, r3, r4, r1])
    >>> [resource.id for resource in plan]
    ['r1', 'r2', 'r3', 'r5', 'r4']
    >>>
    >>> # Next, we change r1 to be dependent on r4, resulting in a cyclic
    >>> # reference error.
    >>> r1_bad = resource_metadata.ResourceMD("r1", r1_key,
    ...             peers=[resource_metadata.ResourceRef("r4", r4_key)])
    >>> try:
    ...     plan = create_install_plan([r2, r5, r3, r4, r1_bad])
    ... except InstallPlanError, msg:
    ...     print msg
    Install solution contains cycles: all resources have dependencies
    >>>
    >>> # Finally, we try the cyclic reference case, adding a resource r6
    >>> # which has no dependencies. This will result in a slightly different
    >>> # error message.
    >>> r6 = resource_metadata.ResourceMD("r6", {"name":"r6_type"})
    >>> try:
    ...     plan = create_install_plan([r2, r5, r3, r4, r1_bad, r6])
    ... except InstallPlanError, msg:
    ...     print msg
    Install solution contains a cycle
    >>>
    """
    # first, we add nodes to graph
    graph = _DepGraph()
    for resource in resource_list:
        graph.create_node(resource)

    # now we go through the nodes and add dependency links
    graph.add_all_dependencies()

    result_list = []
    if graph.is_start_set_empty():
        raise InstallPlanError, "Install solution contains cycles: all resources have dependencies"

    # here's the main loop
    graph.init_working_set_from_start_set()
    while not graph.is_working_set_empty():
        node = graph.take_node_from_working_set()
        result_list.append(node.resource)
        dep_nodes = list(node.dependent_set)
        dep_nodes.sort()
        for dep_node_id in dep_nodes:
            dep_node = graph.get_node(dep_node_id)
            node.remove_dependency(dep_node)
            if len(dep_node.depends_on_set)==0:
                graph.add_node_to_working_set(dep_node)
    
    if graph.total_links > 0:
        raise InstallPlanError, "Install solution contains a cycle"

    return result_list


def create_multi_node_install_plan(resource_list):
    """Install plan for multiple machines
    """
    r_list = create_install_plan(resource_list)
    print 'After toposort'; print [r.id for r in r_list]
    machine_of = { } # for each resource, find the machine where it is installed (machine_of(machine) = machine)
    machine_dep_graph = digraph() # graph with machines as nodes and dependency edges between machines
    multi_node_install_plans = { }

    for r in r_list:
        if r.inside is None: # r is a machine
            multi_node_install_plans[r.id] = [r]
            machine_of[r.id] = r.id 
            machine_dep_graph.add_node(r.id)
            m_id = machine_of[r.id]
            m_node = machine_dep_graph.get_node(m_id)
        else:
            m_id = machine_of[r.inside.id]
            m_node = machine_dep_graph.get_node(m_id)
            machine_of[r.id] = m_id
            multi_node_install_plans[m_id].append(r)
        for resource_ref in r.environment:
            m_ref = machine_of[resource_ref.id]
            m_ref_node = machine_dep_graph.get_node(m_ref)
            if m_ref != m_id:
                machine_dep_graph.add_edge(m_ref, m_id)
        for resource_ref in r.peers:
            m_ref = machine_of[resource_ref.id]
            m_ref_node = machine_dep_graph.get_node(m_ref)
            if m_ref != m_id:
                machine_dep_graph.add_edge(m_ref, m_id)
    machine_dep_graph.print_graph()
    l = machine_dep_graph.toposort()
    print l
    ml = map(lambda l:multi_node_install_plans[l], l)
    return ml 
 
def _test():
    print "Running tests for %s ..." % sys.argv[0]
    import doctest
    results = doctest.testmod()
    if results.failed>0: 
        print 'failed'
        sys.exit(1)
    import engage.drivers.resource_metadata as resource_metadata
    r1_key = {"name":"r1_type"}
    r2_key = {"name":"r2_type"}
    r3_key = {"name":"r3_type"}
    r4_key = {"name":"r4_type"}
    r5_key = {"name":"r5_type"}
    r1 = resource_metadata.ResourceMD("r1", r1_key)
    r2 = resource_metadata.ResourceMD("r2", r2_key,
            inside=resource_metadata.ResourceRef("r1", r1_key))
    r3 = resource_metadata.ResourceMD("r3", r3_key,
            inside=resource_metadata.ResourceRef("r1", r1_key),
            peers=[resource_metadata.ResourceRef("r2", r2_key)])
    r4 = resource_metadata.ResourceMD("r4", r4_key,
            inside=resource_metadata.ResourceRef("r1", r1_key),
            environment=[resource_metadata.ResourceRef("r3", r3_key)])
    r5 = resource_metadata.ResourceMD("r5", r5_key,
            peers=[resource_metadata.ResourceRef("r2", r2_key)])
    plan = create_multi_node_install_plan([r2, r5, r3, r4, r1])
    for l in plan:
        print [r.id for r in l]


def get_resource_dependencies(resource_list):
    """Give a list of resources, return a map
    from resource ids to dependent resource ids. This
    is useful for management tools

    >>> # A simple doctest to validate this function, using
    >>> # the same resources as above.
    >>> import engage.drivers.resource_metadata as resource_metadata
    >>> r1_key = {"name":"r1_type"}
    >>> r2_key = {"name":"r2_type"}
    >>> r3_key = {"name":"r3_type"}
    >>> r4_key = {"name":"r4_type"}
    >>> r5_key = {"name":"r5_type"}
    >>> r1 = resource_metadata.ResourceMD("r1", r1_key)
    >>> r2 = resource_metadata.ResourceMD("r2", r2_key,
    ...        inside=resource_metadata.ResourceRef("r1", r1_key))
    >>> r3 = resource_metadata.ResourceMD("r3", r3_key,
    ...        inside=resource_metadata.ResourceRef("r1", r1_key),
    ...        peers=[resource_metadata.ResourceRef("r2", r2_key)])
    >>> r4 = resource_metadata.ResourceMD("r4", r4_key,
    ...        inside=resource_metadata.ResourceRef("r1", r1_key),
    ...        environment=[resource_metadata.ResourceRef("r3", r3_key)])
    >>> r5 = resource_metadata.ResourceMD("r5", r5_key,
    ...        peers=[resource_metadata.ResourceRef("r2", r2_key)])
    >>> map = get_resource_dependencies([r1, r2, r3, r4, r5])
    >>> map
    {'r4': ['r1', 'r3'], 'r5': ['r2'], 'r1': [], 'r2': ['r1'], 'r3': ['r1', 'r2']}
    
    """
    # first, we add nodes and dependencies to graph
    graph = _DepGraph()
    for resource in resource_list:
        graph.create_node(resource)
    graph.add_all_dependencies()

    # build the table
    results = {}
    for node in graph.all_nodes():
        dependent_ids = [node_id for node_id in node.depends_on_set]
        results[node.resource.id] = dependent_ids
    return results


if __name__ == "__main__": _test()

class GraphError(Exception):
    pass

class digraph (object):
    """
    Digraph class.
    
    Digraphs are built of nodes and directed edges.

    """
    
    def __init__(self):
        """
        Initialize a digraph.
        """
        self.children = {}     # Node -> Neighbors
        self.parents = {}     # Node -> Incident nodes
        self.node_labels = {}        # Node -> label
        self.edge_labels = {}        # Node -> label
        self.num_nodes = 0
        self.num_edges = 0
        

    def add_node(self, node, label=None):
        if (not node in self.children):
            self.children[node] = []
            self.parents[node] = []
            self.node_labels[node] = label
            self.num_nodes += 1

    def get_node(self, node):
        if (not node in self.children):
            return None
        else:
            return node

    def get_node_label(self, node):
        if (not node in self.children):
            return None
        else:
            return self.node_labels[node]

    def get_nodes(self):
        return list(self.children.keys())


    def get_children(self, node):
        return list(self.children[node])
    
    
    def get_parents(self, node):
        return list(self.parents[node])

    def get_indegree(self, node):
        return len(self.parents[node])
    def get_outdegree(self, node):
        return len(self.children[node])

    def get_edges(self):
        """
        Return all edges in the graph.
        """
        return [ a for a in self._edges() ]
        
    def _edges(self):
        for n, children in self.children.items():
            for child in children:
                yield (n, child)


    def add_edge(self, u, v, label=None):
        for n in [u,v]:
            if not n in self.children:
                raise GraphError,  "%s is missing from the node table" % n 
            if not n in self.parents:
                raise GraphError, "%s is missing from the node table" % n 
            
        if v in self.children[u] and u in self.parents[v]:
            pass
        else:
            self.children[u].append(v)
            self.parents[v].append(u)
            self.edge_labels[(u, v)] = label
            self.num_edges += 1


    def del_node(self, node):
        assert(self.has_node(node))
        for each in list(self.parents(node)):
            self.del_edge((each, node))
            
        for each in list(self.children(node)):
            self.del_edge((node, each))
        
        # Remove this node from the neighbors and incidents tables   
        del(self.children[node])
        del(self.parents[node])
        del(self.node_labels[node])
        self.num_nodes -= 1


    def del_edge(self, u, v):
        assert(self.has_edge(u,v))
        self.children[u].remove(v)
        self.parents[v].remove(u)
        del(self.edge_labels[(u,v)])
        self.num_edges -= 1

    def has_node(self, node):
        return node in self.children

    def has_edge(self, u, v):
        return (u, v) in self.edge_labels

    
    def _get_no_incoming(self):
        l = [ ]
        for n in self.children.keys():
             if self.get_indegree(n) == 0:
                 l.append(n)
        return l

    def toposort(self):
        l = []
        worklist = self._get_no_incoming()
        if len(worklist) == 0:
            raise GraphError, "Toposort: graph is not acyclic [no starting nodes]" 
        while len(worklist) != 0:
            # self.print_graph()
            node = worklist.pop(0)
            l.append(node)
            ch = self.get_children(node)
            for dnode in ch:  
                self.del_edge(node, dnode)
                if len(self.get_parents(dnode)) == 0:
                    worklist.append(dnode)
        if self.num_edges != 0:
            raise GraphError, "Toposort: graph is not acyclic"
        return l

    def print_graph(self):
        print self.children
        print self.parents
        print self.edge_labels

def test():
    g = digraph()
    g.add_node(1)
    g.add_node(2)
    g.add_node(3)
    g.add_node(4)
    g.add_edge(1,2)
    g.add_edge(1,4)
    g.add_edge(3,1)
    g.add_edge(2,4)
    print g.get_nodes()
    print g.get_children(1)
    print g.toposort()

if __name__ == "__main__":
    test()

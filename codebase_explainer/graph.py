import networkx as nx

GraphPair = tuple[nx.DiGraph, nx.DiGraph]


def build_graphs(
    module_deps: dict[str, list[str]],
    class_inherit: dict[str, str],
) -> GraphPair:
    g_mod = nx.DiGraph()
    for mod, deps in module_deps.items():
        g_mod.add_node(mod)
        for d in deps:
            g_mod.add_edge(mod, d)

    g_cls = nx.DiGraph()
    for child, parent in class_inherit.items():
        g_cls.add_edge(parent, child)

    return g_mod, g_cls

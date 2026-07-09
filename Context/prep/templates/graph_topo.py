"""Pattern: topological sort (Kahn's algorithm). O(V + E) time, O(V + E) space.
Same shape as the Kahn cycle-check in DecisionCanvas's graph compiler (v0.3.0 prototype)."""
from collections import deque


def topo_order(num_nodes, edges):
    indeg = [0] * num_nodes
    adj = [[] for _ in range(num_nodes)]
    for a, b in edges:            # edge a -> b  (a must run before b)
        adj[a].append(b)
        indeg[b] += 1
    q = deque(n for n in range(num_nodes) if indeg[n] == 0)
    order = []
    while q:
        n = q.popleft()
        order.append(n)
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    return order if len(order) == num_nodes else None   # None => a cycle exists

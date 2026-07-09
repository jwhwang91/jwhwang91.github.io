"""Pattern: grid/graph BFS + DFS. O(V + E) time, O(V) space."""
from collections import deque


def bfs(start, neighbors):
    seen = {start}
    q = deque([start])
    while q:
        node = q.popleft()
        for nxt in neighbors(node):
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return seen


def dfs(node, neighbors, seen):
    seen.add(node)
    for nxt in neighbors(node):
        if nxt not in seen:
            dfs(nxt, neighbors, seen)

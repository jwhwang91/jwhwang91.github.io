"""Pattern: heap / priority queue. push/pop O(log n)."""
import heapq


def k_largest(nums, k):                    # O(n log k) time, O(k) space
    h = []
    for x in nums:
        heapq.heappush(h, x)
        if len(h) > k:
            heapq.heappop(h)
    return h[0]                            # kth largest is the heap root

"""Pattern: interval merge. O(n log n) time (sort-dominated), O(n) space.
Same shape as coalescing event windows when segmenting drive logs for replay."""


def merge(intervals):
    intervals.sort(key=lambda iv: iv[0])
    out = []
    for start, end in intervals:
        if out and start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out

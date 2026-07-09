"""Pattern: binary search + 'search on the answer'. O(log n) (or O(n log range))."""


def bisect_left(nums, target):
    lo, hi = 0, len(nums)
    while lo < hi:
        mid = (lo + hi) // 2
        if nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def min_feasible(lo, hi, feasible):        # smallest x in [lo, hi] with feasible(x) True
    while lo < hi:
        mid = (lo + hi) // 2
        if feasible(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo

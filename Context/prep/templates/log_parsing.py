"""Pattern: parse a channel log and window a signal into fixed time buckets.
O(n) to bucket + O(m log m) to emit sorted buckets. Same daily shape as drive-log replay/triage."""
from collections import defaultdict


def window_signal(samples, bucket_seconds):
    # samples: iterable of (timestamp_seconds, value)
    buckets = defaultdict(list)
    for ts, value in samples:
        buckets[int(ts // bucket_seconds)].append(value)
    return {b: sum(vs) / len(vs) for b, vs in sorted(buckets.items())}


def first_divergence(a, b, threshold):     # first index where two signals diverge
    for i, (x, y) in enumerate(zip(a, b)):
        if abs(x - y) > threshold:
            return i
    return -1

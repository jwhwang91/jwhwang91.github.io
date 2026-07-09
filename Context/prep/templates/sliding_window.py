"""Pattern: variable-size sliding window. O(n) time, O(k) space."""


def longest_window(s, ok):
    left = 0
    best = 0
    window = {}
    for right, ch in enumerate(s):
        window[ch] = window.get(ch, 0) + 1
        while not ok(window):              # shrink until the window is valid again
            window[s[left]] -= 1
            if window[s[left]] == 0:
                del window[s[left]]
            left += 1
        best = max(best, right - left + 1)
    return best

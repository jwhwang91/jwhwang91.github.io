"""Pattern: 1-D dynamic programming. O(n * choices) time, O(n) (often O(1)) space."""


def climb(n):                              # count ways; O(n) time, O(1) space
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def coin_change(coins, amount):            # fewest coins; O(amount * len(coins))
    INF = amount + 1
    dp = [0] + [INF] * amount
    for a in range(1, amount + 1):
        for c in coins:
            if c <= a:
                dp[a] = min(dp[a], dp[a - c] + 1)
    return dp[amount] if dp[amount] != INF else -1

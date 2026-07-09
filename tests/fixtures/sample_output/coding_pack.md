# Coding prep — tesla-adas-validation-2026-07

Format: **practical-python**  ·  plan: **4w**
Basis: validation/test role with Python scripting / log analysis

## Pattern priority
log-parsing -> state-machine -> arrays-hashing -> sliding-window -> graph-bfs-dfs -> intervals -> heap

## Problems
- [ ] `cb-ah-01` [easy] Two Sum (LeetCode 1) — arrays-hashing
- [ ] `cb-ah-02` [easy] Contains Duplicate (LeetCode 217) — arrays-hashing
- [ ] `cb-tp-01` [easy] Valid Palindrome (LeetCode 125) — two-pointers
- [ ] `cb-sw-01` [easy] Best Time to Buy and Sell Stock (LeetCode 121) — sliding-window
- [ ] `cb-st-01` [easy] Valid Parentheses (LeetCode 20) — stack
- [ ] `cb-bs-01` [easy] Binary Search (LeetCode 704) — binary-search
- [ ] `cb-ll-01` [easy] Reverse Linked List (LeetCode 206) — linked-list
- [ ] `cb-ll-02` [easy] Merge Two Sorted Lists (LeetCode 21) — linked-list
- [ ] `cb-tr-02` [easy] Maximum Depth of Binary Tree (LeetCode 104) — trees-bfs-dfs
- [ ] `cb-hp-01` [easy] Kth Largest Element in a Stream (LeetCode 703) — heap
- [ ] `cb-lp-01` [easy] Logger Rate Limiter (LeetCode 359) — log-parsing
- [ ] `cb-ah-04` [medium] Top K Frequent Elements (LeetCode 347) — arrays-hashing
      talk: Frequency-bucketing is the same shape as ranking recurring false-detection signatures in the BEV log-replay triage work.
- [ ] `cb-sw-02` [medium] Longest Substring Without Repeating Characters (LeetCode 3) — sliding-window
- [ ] `cb-st-03` [medium] Daily Temperatures (LeetCode 739) — stack
- [ ] `cb-tr-03` [medium] Binary Tree Level Order Traversal (LeetCode 102) — trees-bfs-dfs
- [ ] `cb-iv-01` [medium] Merge Intervals (LeetCode 56) — intervals
      talk: Merging overlapping time ranges is the same shape as coalescing event windows over drive logs in the replay/triage work.
- [ ] `cb-gr-01` [medium] Number of Islands (LeetCode 200) — graph-bfs-dfs
- [ ] `cb-lp-02` [medium] Parse a channel log and window a signal into fixed time buckets (custom (domain)) — log-parsing
      talk: Windowing a time-series channel log is the daily shape of the drive-log replay/triage work at HMC.
- [ ] `cb-lp-03` [medium] Extract and align named channels from an MF4-style measurement file (custom (domain)) — log-parsing
- [ ] `cb-lp-04` [medium] Detect the first frame where two logged signals diverge beyond a threshold (custom (domain)) — log-parsing
      talk: First-divergence detection is the same shape as localizing false target selections when replaying production logs offline.
- [ ] `cb-sm-03` [medium] Model an SCC emergency-stop handover as a guarded state machine (custom (domain)) — state-machine
      talk: The SCC emergency-stop behavior I independently developed and validated at HMC — describe the guarded transitions.
- [ ] `cb-to-02` [medium] Course Schedule II (LeetCode 210) — graph-topo
      talk: DecisionCanvas's compiler detects control cycles via Kahn topological sort — the same algorithm; mention you built it there in a v0.3.0 prototype if it comes up.
- [ ] `cb-hp-03` [hard] Find Median from Data Stream (LeetCode 295) — heap
- [ ] `cb-sm-04` [hard] Validate an actuator command sequence against a safety interlock FSM (custom (domain)) — state-machine

## Complexity expectations
- **log-parsing:** O(n) single pass over samples; O(k) buckets
- **state-machine:** O(n) in events; explicit guarded transition table

## Mock questions
- Window a noisy channel log into fixed time buckets and flag buckets over threshold.
- Given two logged signals, find the first frame where they diverge beyond a tolerance.
- Model the SCC emergency-stop handover as a guarded state machine.

## Debug / code-review exercises
- A given windowing function drops the last partial bucket — find and fix the off-by-one.
- A BFS grid solution TLEs on large inputs — spot the missing visited-set guard.

## Practical tasks
- Parse an MF4-style measurement export and align two named channels by timestamp.
- Write a small replay harness that reports first-divergence indices across a log set.

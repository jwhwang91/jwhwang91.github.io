"""Pattern: explicit finite state machine over an event stream. O(n) in events.
Mirrors K2 TCU shift-state / SCC emergency-stop guarded transitions."""

# transitions[state][event] -> next_state ; guards keep illegal transitions out
def run_fsm(events, start, transitions, on_enter=None):
    state = start
    for ev in events:
        nxt = transitions.get(state, {}).get(ev)
        if nxt is None:
            continue                       # ignore illegal event in this state (debounce)
        if nxt != state and on_enter:
            on_enter(nxt, ev)
        state = nxt
    return state

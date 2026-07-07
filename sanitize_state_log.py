import json
import os

STATE_FILE = "state_run2_ablated_run1.json"

def sanitize():
    if not os.path.exists(STATE_FILE):
        print(f"Error: {STATE_FILE} not found.")
        return
        
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
        
    print(f"Original state stats:")
    print(f"  Round count: {state.get('round_count')}")
    print(f"  Turn count: {state.get('turn_count')}")
    print(f"  Global_Square messages: {len(state['channels']['Global_Square'])}")
    print(f"  Tier2_Family messages: {len(state['channels']['Tier2_Family'])}")
    print(f"  Cosmopolitan_Family messages: {len(state['channels']['Cosmopolitan_Family'])}")
    
    # Slice channels to restore Round 6 state (which was clean)
    # Global_Square: 6 turns/round * 6 rounds + 1 seed message = 37 messages
    state["channels"]["Global_Square"] = state["channels"]["Global_Square"][:37]
    # Tier2_Family: 5 turns/round * 6 rounds = 30 messages
    state["channels"]["Tier2_Family"] = state["channels"]["Tier2_Family"][:30]
    # Cosmopolitan_Family: 5 turns/round * 6 rounds = 30 messages
    state["channels"]["Cosmopolitan_Family"] = state["channels"]["Cosmopolitan_Family"][:30]
    
    # Correct turn and round count (Round 6 finished, next is Round 7, turn count is 97)
    state["round_count"] = 6
    state["turn_count"] = 96
    
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
        
    print(f"\nSanitized state stats:")
    print(f"  Round count: {state['round_count']}")
    print(f"  Turn count: {state['turn_count']}")
    print(f"  Global_Square messages: {len(state['channels']['Global_Square'])}")
    print(f"  Tier2_Family messages: {len(state['channels']['Tier2_Family'])}")
    print(f"  Cosmopolitan_Family messages: {len(state['channels']['Cosmopolitan_Family'])}")
    print("\nSanitization complete. State restored to pristine Round 6 completion.")

if __name__ == "__main__":
    sanitize()

import time
import json
import os
import urllib.request
import urllib.parse
import datetime

CONV_ID = "f9fbf2f9"
NTFY_URL = f"https://ntfy.sh/niranjan_jee_sim_status_{CONV_ID}"
LOG_DIR = "/home/niranjan/sociology_experiment"
STATE_FILE_1 = os.path.join(LOG_DIR, "state_run2_ablated_run1.json")
STATE_FILE_2 = os.path.join(LOG_DIR, "state_run2_ablated_run2.json")
AUDIT_FILE = os.path.join(LOG_DIR, "quality_control_audit.json")

# Global tracking variables
last_turn = 0
last_time = time.time()
avg_time_per_turn = 90.0  # default fallback (1.5 min per turn)
last_fsm_line = 0

def send_notification(title, message):
    try:
        req = urllib.request.Request(
            NTFY_URL,
            data=message.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": "high"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            response.read()  # Consume stream
            print("Notification sent successfully.")
    except Exception as e:
        print(f"Error sending notification: {e}")

def get_cpu_temp():
    cpu_temp = None
    for zone in os.listdir("/sys/class/thermal"):
        if zone.startswith("thermal_zone"):
            zone_path = os.path.join("/sys/class/thermal", zone)
            type_path = os.path.join(zone_path, "type")
            temp_path = os.path.join(zone_path, "temp")
            if os.path.exists(type_path) and os.path.exists(temp_path):
                try:
                    with open(type_path, "r") as f:
                        ztype = f.read().strip().lower()
                    with open(temp_path, "r") as f:
                        ztemp = int(f.read().strip()) / 1000.0
                    if "tcpu" in ztype or "cpu" in ztype or "pkg" in ztype:
                        cpu_temp = ztemp
                        break
                    elif "acpitz" in ztype and cpu_temp is None:
                        cpu_temp = ztemp
                except Exception:
                    pass
    if cpu_temp is not None:
        return f"{cpu_temp:.1f}°C"
    return "N/A"

def get_agents_mood(state_data):
    agent_moods = {}
    for channel, history in state_data.get("channels", {}).items():
        for msg in history:
            sender_id = msg.get("sender_id")
            if sender_id and sender_id != "system":
                mood = msg.get("emotional_state")
                if mood:
                    agent_moods[msg.get("sender_name", sender_id)] = mood
    
    # Summarize count of moods
    from collections import Counter
    counts = Counter(agent_moods.values())
    mood_str = ", ".join([f"{mood}: {count}" for mood, count in counts.items()])
    return mood_str if mood_str else "N/A"

def get_new_messages(state_data, l_turn):
    all_msgs = []
    for channel, history in state_data.get("channels", {}).items():
        for msg in history:
            if msg.get("sender_id") == "system":
                continue
            all_msgs.append((msg.get("timestamp", ""), channel, msg.get("sender_name", ""), msg.get("content", "")))
    all_msgs.sort(key=lambda x: x[0])
    
    curr_turn = state_data.get("turn_count", 0)
    count_new = max(0, curr_turn - l_turn)
    return all_msgs[-count_new:] if count_new > 0 else []

def get_new_fsm_transitions():
    global last_fsm_line
    transitions = []
    fsm_file = os.path.join(LOG_DIR, "fsm_transitions.csv")
    if not os.path.exists(fsm_file):
        return []
    try:
        with open(fsm_file, "r") as f:
            lines = f.readlines()
        
        start = max(1, last_fsm_line)
        for idx in range(start, len(lines)):
            line = lines[idx].strip()
            if not line:
                continue
            parts = line.split(",", 4)
            if len(parts) >= 4:
                rnd, agent, prev, new_state = parts[0], parts[1], parts[2], parts[3]
                reason = parts[4].strip('"') if len(parts) > 4 else ""
                transitions.append(f"• {agent}: {prev} -> {new_state} ({reason[:45]}...)")
        
        last_fsm_line = len(lines)
    except Exception as e:
        print(f"Error reading FSM log: {e}")
    return transitions

def get_channel_activity(new_messages):
    if not new_messages:
        return "No activity."
    
    activity = {}
    speakers = set()
    for _, ch, sender, _ in new_messages:
        activity[ch] = activity.get(ch, 0) + 1
        speakers.add(sender)
        
    summary_lines = []
    summary_lines.append(f"Turns: " + ", ".join([f"{ch}: {count}" for ch, count in activity.items()]))
    summary_lines.append(f"Speakers: {', '.join(speakers)}")
    return "\n".join(summary_lines)

def update_etc_pass1(curr_turn, pass_num):
    global last_turn, last_time, avg_time_per_turn
    now = time.time()
    
    if curr_turn > last_turn and last_turn > 0:
        elapsed = now - last_time
        turns_done = curr_turn - last_turn
        current_rate = elapsed / turns_done
        # Exponential moving average (alpha=0.3)
        avg_time_per_turn = 0.7 * avg_time_per_turn + 0.3 * current_rate
        
    last_time = now
    
    if pass_num == 1:
        turns_left_pass1 = max(0, 304 - curr_turn)
        seconds_left_pass1 = turns_left_pass1 * avg_time_per_turn
        
        etc_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds_left_pass1)
        etc_str = etc_time.strftime("%I:%M %p")
        
        hrs = int(seconds_left_pass1 // 3600)
        mins = int((seconds_left_pass1 % 3600) // 60)
        remaining_str = f"{hrs}h {mins}m" if hrs > 0 else f"{mins}m"
        
        return f"{etc_str} ({remaining_str} remaining)"
    else:
        return "Pass 1 Completed"

def main():
    global last_turn, last_fsm_line
    print(f"ntfy Notifier started. Exposing to URL: {NTFY_URL}")
    send_notification("Simulation Tracker Started", f"Monitoring active simulation. Check updates live at: {NTFY_URL}")
    
    while True:
        try:
            # Check which state file is active dynamically (Pass 1 or Pass 2)
            active_file = None
            pass_num = 1
            
            # Find all run state files in the directory
            run_states = [f for f in os.listdir(LOG_DIR) if f.startswith("state_") and f.endswith(".json") and f != "state_human_baseline.json"]
            active_config_base = None
            if run_states:
                # Resolve the latest modified file to detect current config target
                latest_file = max([os.path.join(LOG_DIR, f) for f in run_states], key=os.path.getmtime)
                filename = os.path.basename(latest_file)
                if "_run" in filename:
                    active_config_base = filename.replace("state_", "").split("_run")[0]
            
            if active_config_base:
                file2 = os.path.join(LOG_DIR, f"state_{active_config_base}_run2.json")
                file1 = os.path.join(LOG_DIR, f"state_{active_config_base}_run1.json")
                if os.path.exists(file2):
                    active_file = file2
                    pass_num = 2
                elif os.path.exists(file1):
                    active_file = file1
                    pass_num = 1
                
            if active_file:
                with open(active_file, "r") as f:
                    state_data = json.load(f)
                
                curr_round = state_data.get('round_count', 0)
                curr_turn = state_data.get('turn_count', 0)
                
                # Initialize variables on first run of the script
                if last_turn == 0:
                    last_turn = curr_turn
                    # Initialize FSM lines
                    fsm_file = os.path.join(LOG_DIR, "fsm_transitions.csv")
                    if os.path.exists(fsm_file):
                        try:
                            with open(fsm_file, "r") as f:
                                last_fsm_line = len(f.readlines())
                        except Exception:
                            last_fsm_line = 0
                
                # Fetch CPU temp
                cpu_temp = get_cpu_temp()
                
                # Fetch overall agent moods
                overall_moods = get_agents_mood(state_data)
                
                # Fetch FSM transitions since last check
                fsm_transitions = get_new_fsm_transitions()
                
                # Fetch new messages and format activity
                new_msgs = get_new_messages(state_data, last_turn)
                channel_activity = get_channel_activity(new_msgs)
                
                # Calculate ETC of Pass 1
                etc_pass1 = update_etc_pass1(curr_turn, pass_num)
                
                # Update last_turn
                last_turn = curr_turn
                
                # Fetch QC stats
                qc_str = "N/A"
                if os.path.exists(AUDIT_FILE):
                    with open(AUDIT_FILE, "r") as f:
                        qc_data = json.load(f)
                        qc_str = (
                            f"Attempts={qc_data.get('total_attempts', 0)} | "
                            f"XML={qc_data.get('xml_tags', 0)} | "
                            f"Role={qc_data.get('role_leak', 0)} | "
                            f"Speech={qc_data.get('preachy_leak', 0) + qc_data.get('no_change_leak', 0)} | "
                            f"Rep={qc_data.get('trigram_repetition', 0)} | "
                            f"Fallback={qc_data.get('fallback_triggers', 0)}"
                        )
                
                # Formatting FSM transition block
                fsm_block = "\n".join(fsm_transitions) if fsm_transitions else "No mood transitions."
                
                status_title = f"Simulation Update (Pass {pass_num})"
                status_message = (
                    f"Active Pass: {pass_num}/2\n"
                    f"Current Progress: Round {curr_round}/19 | Turn {curr_turn}/304\n"
                    f"Pass 1 ETC: {etc_pass1}\n"
                    f"CPU Temp: {cpu_temp}\n"
                    f"Overall Moods: {overall_moods}\n"
                    f"QC: {qc_str}\n\n"
                    f"--- Activity Since Last Notif ---\n"
                    f"{channel_activity}\n\n"
                    f"--- Mood Transitions ---\n"
                    f"{fsm_block}"
                )
                
                send_notification(status_title, status_message)
        except Exception as e:
            print(f"Error in notifier loop: {e}")
            
        time.sleep(300)  # Wait 5 minutes for more frequent updates (per user request)

if __name__ == "__main__":
    main()

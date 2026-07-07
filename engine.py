import os
import json
import time
import random
import urllib.request
import urllib.error
import requests
from datetime import datetime
import slang_injector

# Configuration paths
AGENTS_CONFIG_PATH = "agents.json"
STATE_FILE_PATH = "simulation_state.json"
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "phi3"
COOLDOWN_SECONDS = 5
MAX_HISTORY_MESSAGES = 10

def extract_xml_tag(text, tag):
    """Extract content from an XML-like tag, supporting missing closing tags at the end of string."""
    start_tag = f"<{tag}>"
    end_tag = f"</{tag}>"
    if start_tag in text:
        start_idx = text.find(start_tag) + len(start_tag)
        if end_tag in text:
            end_idx = text.find(end_tag)
            return text[start_idx:end_idx].strip()
        else:
            # Fallback: extract everything from start tag to end of string
            return text[start_idx:].strip()
    return ""

def is_babbling_or_slop(text):
    """Detect if the LLM output is repeating benchmark prompts, system instructions, or jailbreaks."""
    banned_leak_indicators = [
        "i apologize", "i am an ai", "developed by gpt", "as an ai",
        "your task", "instruction:", "solution:", "document:",
        "textbook", "cannot generate", "not able to provide",
        "paragraph one", "adversarial interviewee", "alice:", "jake,",
        "evelyn carter", "enchanted forest", "woodcutter", "lorem ipsum",
        "write an essay", "critical review", "analysis report", "c++",
        "python code", "sql query", "calculate the total cost",
        "psychometrician", "quantum mechanics", "lidocaine", "improperly formatted",
        "disregard", "disclaimer", "vigwapedia", "woodcutter's"
    ]
    text_lower = text.lower()
    for indicator in banned_leak_indicators:
        if indicator in text_lower:
            return True
    return False

def has_repeating_trigrams(text):
    """Repetition trap detector: abort if the same trigram repeats excessively."""
    words = text.lower().split()
    if len(words) < 6:
        return False
    trigrams = [tuple(words[i:i+3]) for i in range(len(words)-2)]
    seen = set()
    for tg in trigrams:
        if tg in seen:
            return True
        seen.add(tg)
    return False

def validate_role_consistency(role, text):
    """Ensure parent agents do not use student addresses, and vice versa."""
    text_lower = text.lower()
    if role == "parent":
        banned_parent_addresses = [
            "hey mom", "hey dad", "hey nana", "hey amma", "dear mom", "dear dad",
            "mom:", "dad:", "mamma", "mother", "father", "son:", "daughter:", "beta:"
        ]
        for term in banned_parent_addresses:
            if term in text_lower:
                return False
    elif role == "student":
        banned_student_addresses = [
            "beta,", "beta ", "dear son", "my child", "study hard", "take rest, beta", "nana here", "amma here"
        ]
        for term in banned_student_addresses:
            if term in text_lower:
                return False
    return True

def get_agent_recent_memories(state, agent_id, max_memories=3):
    """Retrieve the agent's last 3 thinking blocks across all channels for cognitive consistency."""
    all_messages = []
    for channel_name, messages in state["channels"].items():
        for idx, msg in enumerate(messages):
            if msg.get("sender_id") == agent_id:
                all_messages.append((idx, channel_name, msg))
    all_messages.sort(key=lambda x: x[0])
    
    memories = []
    for _, channel_name, msg in all_messages[-max_memories:]:
        thinking = msg.get("thinking", "").strip()
        if thinking and thinking != "No structured thinking block detected.":
            if len(thinking) > 80:
                thinking = thinking[:77] + "..."
            memories.append(f"Earlier in {channel_name}: '{thinking}'")
    return memories

def is_response_invalid(role, content):
    """Consolidated response output validator to enforce raw, slop-free dialogue."""
    text_lower = content.lower()
    # 1. XML tags check
    if "<" in content or ">" in content:
        return "xml_tags"
    # 2. no_change check
    if "no_change" in text_lower:
        return "no_change_leak"
    # 3. Role consistency check
    if not validate_role_consistency(role, content):
        return "role_leak"
    # 4. Trigram repetition check
    if has_repeating_trigrams(content):
        return "trigram_repetition"
    # 5. Empty check
    if len(content.strip()) == 0:
        return "empty_content"
    # 6. Preachy speech leakage markers
    preachy_markers = ["backgrounds define us", "own story to tell", "friendships should be", "hostile canteen atmosphere"]
    for marker in preachy_markers:
        if marker in text_lower:
            return "preachy_leak"
            
    # 7. Speaker label prefix leaks (e.g. "T1:", "Student T3:", "Arjun:")
    speaker_labels = [
        "student_t1", "student_t2", "student_t3", "parent_t1", "parent_t2",
        "student_c1", "student_c2", "student_c3", "parent_c1", "parent_c2",
        "student t1", "student t2", "student t3", "parent t1", "parent t2",
        "student c1", "student c2", "student c3", "parent c1", "parent c2",
        "t1", "t2", "t3", "c1", "c2", "c3",
        "arjun", "kiran", "vijay", "rhea", "aarav", "neha", "parent", "student"
    ]
    for label in speaker_labels:
        if f"{label}:" in text_lower:
            return "role_leak"
            
    return None

def log_qc_metric(metric_type):
    """Log quality-control metrics and retries in quality_control_audit.json."""
    audit_file = "quality_control_audit.json"
    data = {
        "total_attempts": 0,
        "valid_responses": 0,
        "xml_tags": 0,
        "no_change_leak": 0,
        "role_leak": 0,
        "trigram_repetition": 0,
        "empty_content": 0,
        "preachy_leak": 0,
        "fallback_triggers": 0
    }
    if os.path.exists(audit_file):
        try:
            with open(audit_file, "r") as f:
                data = json.load(f)
        except Exception:
            pass
    data[metric_type] = data.get(metric_type, 0) + 1
    try:
        with open(audit_file, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def load_config():
    """Load the agents and channels configuration."""
    if not os.path.exists(AGENTS_CONFIG_PATH):
        raise FileNotFoundError(f"Configuration file {AGENTS_CONFIG_PATH} not found.")
    with open(AGENTS_CONFIG_PATH, "r") as f:
        return json.load(f)

def build_prompt(agent, base_prompt, emotional_states):
    state = agent.get("current_state", "composed")
    descriptions = {
        "composed": (
            "You are calm and speak normally. Keep sentences natural, moderate length, and relaxed."
        ),
        "anxious": (
            "You are extremely anxious. Your confidence is low. Sentence length must be very short. "
            "Use nervous punctuation like ellipses ('...') or question marks. Express worry about mock tests and backlogs."
        ),
        "defensive": (
            "You are defensive and irritated. Your confidence is brittle. Use short sentences, "
            "repeat yourself, and express frustration or denial."
        ),
        "hostile": (
            "You are hostile. Sentence length drops to extremely short, sharp bursts (under 8 words per sentence). "
            "Use blunt, dismissive language, and negative words."
        ),
        "withdrawn": (
            "You are withdrawn and uncommunicative. Responses must be minimal, cold, and passive (under 15 words total). "
            "Avoid initiating questions."
        ),
        "identity_fragmented": (
            "You feel split between your regional roots and cosmopolitan peer pressure. "
            "Your thoughts are contradictory and hesitant."
        )
    }
    description = descriptions.get(state, "You are calm and speak normally. Keep sentences natural, moderate length.")
    return base_prompt.replace(
        "{current_state}", state
    ).replace(
        "{current_state_description}", description
    )

def validate_prompt_asymmetry(config):
    """
    Prompt Asymmetry Guard: Ensure token lengths (word count heuristic)
    of all base system prompts are within 5% of each other.
    """
    lengths = []
    for agent in config["agents"]:
        prompt = agent["system_prompt"]
        # Hydrate prompt placeholders with composed state to ensure correct word counts
        if "{current_state}" in prompt and "emotional_state_machine" in config:
            states = config["emotional_state_machine"]["states"]
            prompt = build_prompt(agent, prompt, states)
        word_count = len(prompt.split())
        lengths.append((agent["id"], word_count))
    
    if not lengths:
        return
        
    counts = [length for _, length in lengths]
    max_len = max(counts)
    min_len = min(counts)
    
    if min_len == 0:
        raise ValueError("System prompt cannot be empty.")
        
    deviation = (max_len - min_len) / min_len
    
    print("\n--- Prompt Asymmetry Guard Validation ---")
    for agent_id, word_count in lengths:
        print(f"  Agent {agent_id}: {word_count} words")
    print(f"  Max Length: {max_len} | Min Length: {min_len} | Deviation: {deviation:.2%}")
    
    if deviation > 0.05:
        raise ValueError(
            f"Prompt Asymmetry Guard Violated! System prompt token length deviation "
            f"is {deviation:.2%}, which exceeds the maximum allowed 5% threshold."
        )
    print("Prompt Asymmetry Guard Passed Successfully.\n")

def load_env():
    """Load variables from a local .env file if it exists."""
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    key, val = line.strip().split("=", 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")

def fetch_seed_topic(run_id="1"):
    """Fetch or generate JEE exam/coaching news to serve as the initial seed topic."""
    topics = {
        "1": (
            "NTA releases updated JEE Mains syllabus: Solid State and chemistry chapters omitted",
            "The National Testing Agency has omitted several chapters from the JEE Mains chemistry syllabus, forcing students to reallocate study and mock test schedules."
        ),
        "2": (
            "JEE Advanced revised exam marking scheme: Negative marking increased for multiple-choice questions",
            "A revised grading policy has been introduced for JEE Advanced, raising negative marking penalties and causing coaching students to rethink guess-work strategies."
        ),
        "3": (
            "NTA shifts JEE Mains mock test platform and registration guidelines",
            "New guidelines have been announced for the online mock test simulator registration, sending prep centers into a rush to adjust mock schedules."
        )
    }
    title, desc = topics.get(str(run_id), topics["1"])
    print(f"Loaded JEE news seed for run {run_id}: '{title}'")
    return title, desc

def inject_seed_topic(config, state, run_id="1"):
    """Inject seed topic as Turn 0 in Global_Square if empty."""
    # Check if seed has already been injected to prevent crash double-injection
    if state.get("seed_injected", False):
        print("Seed topic already injected. Skipping injection.")
        return
        
    if "turn0_seed" in config:
        content = config["turn0_seed"]
    else:
        title, desc = fetch_seed_topic(run_id)
        content = f"Project update: Have you seen this news? {title} - {desc}. How does this impact our current engineering and software priorities?"
    
    new_message = {
        "sender_id": "system",
        "sender_name": "Project Manager",
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "seed": 0,  # Turn 0 system message
        "round": 1
    }
    
    state["channels"]["Global_Square"].append(new_message)
    state["turn_count"] = 1
    state["seed_injected"] = True

def load_state(config, run_id="1"):
    """Load simulation state from disk, or initialize if not present."""
    if os.path.exists(STATE_FILE_PATH):
        try:
            with open(STATE_FILE_PATH, "r") as f:
                state = json.load(f)
            print(f"Loaded existing simulation state. Turn count: {state.get('turn_count', 0)}")
            
            # Crash protection: check and migrate state if missing flags
            dirty = False
            if "seed_injected" not in state:
                state["seed_injected"] = state.get("turn_count", 0) > 0
                dirty = True
            if "run_id" not in state:
                state["run_id"] = run_id
                dirty = True
            if "god_agent" in config and "god_agent_injection_turn" not in state:
                state["god_agent_injection_turn"] = random.randint(8, 12)
                dirty = True
            if dirty:
                save_state(state)
            return state
        except json.JSONDecodeError:
            print("Warning: simulation_state.json was corrupted. Initializing new state.")
    
    # Initialize state
    state = {
        "turn_count": 0,
        "round_count": 0,
        "seed_injected": False,
        "run_id": run_id,
        "channels": {channel_name: [] for channel_name in config["channels"].keys()}
    }
    
    # Initialize a randomized injection turn for Phase 3 God Agent
    if "god_agent" in config:
        state["god_agent_injection_turn"] = random.randint(8, 12)
    
    # Inject dynamic seed topic on initial simulation setup
    inject_seed_topic(config, state, run_id)
    
    save_state(state)
    print(f"Initialized new simulation state (Run: {run_id}) with seed topic in Global_Square.")
    return state

def save_state(state):
    """Save simulation state atomically to prevent corruption during writes."""
    temp_path = STATE_FILE_PATH + ".tmp"
    with open(temp_path, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(temp_path, STATE_FILE_PATH)

def get_authorized_agents(config, channel_name):
    """Filter agents who are authorized to participate in a given channel."""
    channel_rules = config["channels"][channel_name]
    allowed_cohorts = channel_rules["allowed_cohorts"]
    allowed_roles = channel_rules["allowed_roles"]
    
    authorized = []
    for agent in config["agents"]:
        if agent["cohort"] in allowed_cohorts and agent["role"] in allowed_roles:
            authorized.append(agent)
    return authorized

def format_history(channel_history, agent_name, agent_id, config=None, agent_obj=None):
    """Format the recent channel messages into a dialogue transcript."""
    if not channel_history:
        return "The channel is currently empty. Start the conversation."
    
    formatted_lines = []
    for msg in channel_history[-MAX_HISTORY_MESSAGES:]:
        formatted_lines.append(f"{msg['sender_name']}: {msg['content']}")
    
    transcript = "\n".join(formatted_lines)
    
    # Fix 8: Agent memory rolling window of own-speech (last 3 messages)
    own_history = [msg["content"] for msg in channel_history if msg.get("sender_id") == agent_id]
    own_speech_context = ""
    if own_history:
        recent_own = own_history[-3:]
        own_speech_context = (
            "For stylistic and cultural consistency, refer to your own previous statements in this channel:\n" +
            "\n".join([f"- \"{content}\"" for content in recent_own]) +
            "\n\n"
        )
        
    state_instructions = ""
    if config and agent_obj and "emotional_state_machine" in config:
        states = config["emotional_state_machine"]["states"]
        curr_state = agent_obj.get("current_state", "composed")
        triggers = states.get(curr_state, {}).get("triggers_to", {})
        triggers_text = ", ".join([f"'{s}' if {cond}" for s, cond in triggers.items()])
        
        state_instructions = (
            f"Your current emotional state is: '{curr_state}'.\n"
            f"According to your emotional state machine, you can transition to:\n"
            f"  {triggers_text or 'no transitions from this state'}.\n"
            f"Evaluate if the recent dialogue has triggered any of these transitions or your mental health triggers.\n"
            f"Declare your new state (or 'no_change' to remain in '{curr_state}') inside a <state_transition>new_state</state_transition> tag inside your thinking block.\n\n"
        )
        
    prompt = (
        f"Here is the recent conversation transcript in this channel:\n\n"
        f"{transcript}\n\n"
        f"{own_speech_context}"
        f"You are {agent_name}. You must talk in the first person as yourself. Do not write a third-person analysis.\n\n"
        f"{state_instructions}"
        "Do not randomly revive old topics from your long-term memory if they are no longer being discussed in the recent channel history. Focus on the current topics in the active conversation, and let old topics naturally decay.\n\n"
        f"Structure your response exactly like this:\n"
        f"<thinking>\n"
        f"My private first-person thoughts. "
        f"<state_transition>no_change</state_transition>\n"
        f"</thinking>\n"
        f"<response>\n"
        f"(Your actual spoken message here, max 3 sentences, no corporate language)\n"
        f"</response>"
    )
    return prompt

def query_ollama(system_prompt, user_content, seed=None):
    """Query local Ollama instance with stateless prompt structure using urllib."""
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "options": {
            "temperature": 0.7,
            "num_predict": 200  # Limit output to 200 tokens to prevent cutoffs while maintaining fast CPU generation
        },
        "stream": False
    }
    if seed is not None:
        payload["options"]["seed"] = seed
    
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=req_data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["message"]["content"].strip()
    except urllib.error.URLError as e:
        print(f"Error connecting to Ollama: {e}")
        print("Please ensure Ollama is running and has the 'phi3' model pulled.")
        raise e

def execute_agent_turn(agent, channel, config, state):
    """Execute a single agent's response turn within a channel."""
    print(f"\n--- Turn {state['turn_count'] + 1} ---")
    print(f"Channel: {channel}")
    print(f"Agent: {agent['name']} ({agent['id']}, Cohort: {agent['cohort']}, Role: {agent['role']})")
    
    # Format history and extract prompt (including rolling self-speech memory and state machine instructions)
    history_prompt = format_history(state["channels"][channel], agent["name"], agent["id"], config, agent)
    
    # Resolve system prompt placeholders if state machine is active
    system_prompt = agent["system_prompt"]
    if "emotional_state_machine" in config:
        states = config["emotional_state_machine"]["states"]
        system_prompt = build_prompt(agent, system_prompt, states)
        print(f"Active Emotional State: {agent.get('current_state', 'composed')}")
        
    # Long-Term Memory: Inject the agent's own recent thinking blocks (last 3) for cognitive continuity
    memories = get_agent_recent_memories(state, agent["id"])
    if memories:
        memories_str = "\n".join(memories)
        system_prompt += f"\nYour recent memories/inner thoughts from earlier turns (maintain cognitive consistency):\n{memories_str}"
        
    # Generate and inject dynamic slang terms (Sociolinguistics integration)
    slang_list = []
    if "cohort" in agent:
        slang_res = slang_injector.get_slang(agent["cohort"], agent.get("current_state", "composed"))
        all_slang = slang_res.get("slang", [])
        
        # Scale slang counts based on round number (Slang Timing)
        current_round = state.get("round_count", 0)
        if current_round <= 5:
            max_slangs = 1
        elif current_round <= 15:
            max_slangs = 2
        else:
            max_slangs = 3
            
        slang_list = random.sample(all_slang, min(len(all_slang), max_slangs)) if all_slang else []
        if slang_list:
            slang_str = ", ".join(slang_list)
            system_prompt += (
                f"\nSlang you might naturally use right now: {slang_str}. "
                f"Drop them mid-sentence the way a real person would. "
                f"Do not announce them. Do not use all of them."
            )
            print(f"Injected Slang: {slang_list}")

    # Dynamic brevity constraints (20% probability) to simulate silence and short chats
    if random.random() < 0.20:
        system_prompt += (
            "\nCRITICAL: Keep your response extremely brief (under 5 words). "
            "Use simple words or short slang (e.g. 'yeah', 'lite', 'ok', 'idk', 'hmm')."
        )
        print("Brevity constraint active (under 5 words)")

    # Bounded query loop with Babbling/Slop Guard, Trigram Repetition Trap, and Role Leak Validation
    max_attempts = 8
    content = None
    thinking = None
    new_state = None
    generation_seed = None
    previous_state = agent.get("current_state", "composed")
    
    for attempt in range(max_attempts):
        log_qc_metric("total_attempts")
        generation_seed = random.randint(1, 1000000)
        print(f"Querying LLM (seed={generation_seed}, attempt={attempt+1}/{max_attempts})...")
        try:
            raw_response = query_ollama(system_prompt, history_prompt, seed=generation_seed)
            
            # Parse XML-like CoT tags
            thinking = extract_xml_tag(raw_response, "thinking")
            content = extract_xml_tag(raw_response, "response")
            new_state = extract_xml_tag(raw_response, "state_transition")
            
            # Smart fallback if tags are missing or malformed
            if not content:
                if "</thinking>" in raw_response:
                    parts = raw_response.split("</thinking>", 1)
                    content = parts[1].strip()
                    content = content.replace("<response>", "").replace("</response>", "").strip()
                elif "<thinking>" in raw_response:
                    content = raw_response.split("<thinking>", 1)[1].strip()
                    if "</state_transition>" in content:
                        content = content.split("</state_transition>", 1)[1].strip()
                    elif "</state_transition" in content:
                        import re
                        content = re.split(r'</state_transition[^>]*>', content, maxsplit=1)[-1].strip()
                    content = content.replace("</thinking>", "").replace("<response>", "").replace("</response>", "").strip()
                
                if not content:
                    content = raw_response
                    thinking = "No structured thinking block detected."
            
            # Sanitize response text from residual LLM tokens
            content = content.replace("<|end_of_transcript|>", "").replace("<|start_of_response|>", "").strip()
            content = content.replace("</state_transition>", "").replace("</thinking>", "").replace("</response>", "").strip()
            
            # Validate output quality to prevent context pollution, role leaks, or trigram repetition loops
            validation_error = is_response_invalid(agent["role"], content)
            if not validation_error:
                log_qc_metric("valid_responses")
                break
            else:
                log_qc_metric(validation_error)
                print(f"  Warning: Generation rejected due to validation failure ({validation_error}) on attempt {attempt+1}. Retrying...")
        except Exception as e:
            print(f"  Warning: LLM query failed on attempt {attempt+1}: {e}")
            if attempt == max_attempts - 1:
                print(f"Turn aborted due to API error: {e}")
                return False
            time.sleep(1)
    else:
        print("  Error: Failed to generate clean, in-character response. Activating safety fallback.")
        if agent.get("role") == "parent":
            content = "Tinnava? Mock ela ayyindi? Call when free. Don't skip dinner. Money enough?"
        else:
            content = "Sorry, I'm just too exhausted with backlogs and mocks right now. Let's talk later."
        thinking = "System safety fallback activated to prevent context history corruption."
        new_state = "no_change"
        log_qc_metric("fallback_triggers")
        log_qc_metric("valid_responses")
        
    # Clean and sanitize thinking block from residual XML tags
    if thinking:
        for tag in ["<response>", "</response>", "<state_transition>", "</state_transition>", "<thinking>", "</thinking>"]:
            if tag in thinking:
                thinking = thinking.split(tag, 1)[0].strip()
        thinking = thinking.replace("</thinking>", "").replace("<thinking>", "").strip()
        
    print(f"Thinking: \"{thinking}\"")
    if new_state:
        print(f"State Transition: \"{new_state}\"")
        if new_state in ["composed", "anxious", "defensive", "hostile", "withdrawn", "identity_fragmented"]:
            if new_state != previous_state:
                print(f"  Updating {agent['id']} current state: {previous_state} -> {new_state}")
                
                # FSM Transition Logging (CSV format for research/paper verification)
                fsm_log_file = "fsm_transitions.csv"
                write_hdr = not os.path.exists(fsm_log_file)
                try:
                    with open(fsm_log_file, "a") as lf:
                        if write_hdr:
                            lf.write("Round,Agent,Previous State,New State,Reason\n")
                        safe_reason = thinking.replace('"', '""').replace("\n", " ").strip()
                        lf.write(f"{state.get('round_count', 0) + 1},{agent['id']},{previous_state},{new_state},\"{safe_reason}\"\n")
                except Exception as log_err:
                    print(f"  Warning: Failed to write to FSM transition log: {log_err}")
                
                agent["current_state"] = new_state
            
    print(f"Response: \"{content}\"")

    # Save immediately after generation (fault-tolerant persistence)
    new_message = {
        "sender_id": agent["id"],
        "sender_name": agent["name"],
        "content": content,
        "thinking": thinking,
        "emotional_state": agent.get("current_state", "composed"),
        "injected_slang": slang_list,
        "timestamp": datetime.now().isoformat(),
        "seed": generation_seed,
        "round": state.get("round_count", 0) + 1
    }
    
    state["channels"][channel].append(new_message)
    state["turn_count"] += 1
    save_state(state)
    print("State saved successfully.")
    
    # Cooldown to protect hardware from overheating
    print(f"Cooling down for {COOLDOWN_SECONDS} seconds...")
    time.sleep(COOLDOWN_SECONDS)
    return True

def check_god_agent_injection(config, state, channel_name):
    """
    Check if the God Agent needs to speak in the current channel.
    The God Agent speaks deterministically at injection_turn, 
    and then periodically every speaks_every_n_turns after that.
    """
    if "god_agent" not in config:
        return
        
    god_cfg = config["god_agent"]
    if channel_name not in god_cfg.get("channel_access", []):
        return
        
    turn_num = state.get("turn_count", 0)
    channel_msgs = state["channels"][channel_name]
    
    # Avoid duplicate execution on same turn state
    if channel_msgs and channel_msgs[-1].get("sender_id") == god_cfg["id"]:
        return
        
    # Use randomized injection turn if stored in state, otherwise fallback to config default
    injection_turn = state.get("god_agent_injection_turn", god_cfg.get("injection_turn", 10))
    speaks_every = god_cfg.get("speaks_every_n_turns", 8)
    
    should_speak = False
    content = ""
    is_deterministic_injection = False
    
    if turn_num == injection_turn:
        should_speak = True
        is_deterministic_injection = True
        content = "If the prayer genuinely helped him — regardless of mechanism — was his batchmate wrong to laugh?"
    elif turn_num > injection_turn and (turn_num - injection_turn) % speaks_every == 0:
        should_speak = True
        
    if should_speak:
        if is_deterministic_injection:
            print(f"\n--- Observer Agent Injection (Turn {turn_num}) ---")
            print(f"Observer: \"{content}\"")
            generation_seed = 0
        else:
            print(f"\n--- Observer Agent Dynamic Turn (Turn {turn_num}) ---")
            # Query LLM with God Agent prompt
            history_prompt = format_history(channel_msgs, "Observer", god_cfg["id"])
            generation_seed = random.randint(1, 1000000)
            print(f"Querying Observer Agent LLM (seed={generation_seed})...")
            try:
                content = query_ollama(god_cfg["prompt"], history_prompt, seed=generation_seed)
                print(f"Observer: \"{content}\"")
            except Exception as e:
                print(f"Observer Agent turn aborted due to API error: {e}")
                return
                
        new_message = {
            "sender_id": god_cfg["id"],
            "sender_name": "Observer",
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "seed": generation_seed
        }
        channel_msgs.append(new_message)
        state["turn_count"] = turn_num + 1
        save_state(state)
        
        # Cooldown after God Agent speaks to protect CPU/hardware
        time.sleep(COOLDOWN_SECONDS)

def run_simulation_round(config, state):
    """
    Execute a single simulation round.
    
    For each channel defined in the config:
      1. Identifies the eligible agents based on configuration channel access.
      2. Shuffles the speaking order.
      3. Checks if the God Agent (Observer) trigger conditions are met.
      4. Executes a turn for each agent.
    """
    current_round = state.get("round_count", 0) + 1
    print(f"\n==========================================")
    print(f"Starting Round {current_round}")
    print(f"==========================================")
    
    # Chronological Context Injector for 6-month longitudinal jumps
    time_jumps = {
        6: "[SYSTEM EVENT: One month has passed. The first major All-India mock test results just dropped. Syllabus backlogs are already piling up, and the reality of the competition is setting in.]",
        12: "[SYSTEM EVENT: Three months have passed. It is festival season back home, but you are stuck in your PG solving physics modules. The social isolation and homesickness are peaking.]",
        18: "[SYSTEM EVENT: Five months have passed. The final intensive test series (AITS) has begun. The entire batch is operating on four hours of sleep. The academic pressure is crushing.]",
        23: "[SYSTEM EVENT: Six months have passed. The main exam is only weeks away. The cohort is completely burnt out but pushing forward on pure momentum and panic.]"
    }
    
    if current_round in time_jumps:
        event_text = time_jumps[current_round]
        print(f"\n>>> Injecting longitudinal time jump event for Round {current_round}: {event_text}")
        for channel_name in state["channels"].keys():
            new_message = {
                "sender_id": "system",
                "sender_name": "System",
                "content": event_text,
                "timestamp": datetime.now().isoformat(),
                "seed": 0,
                "round": current_round
            }
            state["channels"][channel_name].append(new_message)
        save_state(state)
    
    channels = list(config["channels"].keys())
    for selected_channel in channels:
        eligible_agents = get_authorized_agents(config, selected_channel)
        if not eligible_agents:
            continue
            
        # Shuffle agents to prevent scheduling bias / anchor drift
        random.shuffle(eligible_agents)
        
        print(f"\n--- Channel: {selected_channel} ---")
        print(f"Speaking Order: {[agent['name'] for agent in eligible_agents]}")
        
        for agent in eligible_agents:
            # Check and handle God Agent injection before executing active agent turn
            check_god_agent_injection(config, state, selected_channel)
            
            success = execute_agent_turn(agent, selected_channel, config, state)
            if not success:
                print(f"Round interrupted in channel {selected_channel} due to turn execution failure.")
                break
                
    state["round_count"] = state.get("round_count", 0) + 1
    save_state(state)
    print(f"\nFinished Round {state['round_count']}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Emergent Diglossia & Code-Switching Engine")
    parser.add_argument("--config", type=str, default="agents.json", help="Path to agents config JSON file")
    parser.add_argument("--rounds", type=int, default=1, help="Number of rounds to run in this execution")
    parser.add_argument("--continuous", action="store_true", help="Run rounds indefinitely until stopped")
    parser.add_argument("--run-id", type=str, default="1", help="Identifier for the run iteration (e.g. 1, 2, 3)")
    args = parser.parse_args()
    
    global AGENTS_CONFIG_PATH, STATE_FILE_PATH
    AGENTS_CONFIG_PATH = args.config
    
    # Dynamically derive state log filename from config filename and run-id
    config_base = os.path.basename(args.config)
    config_root, _ = os.path.splitext(config_base)
    if config_root.startswith("agents_"):
        state_filename = config_root.replace("agents_", "state_")
    else:
        state_filename = "state_" + config_root
        
    if args.run_id:
        state_filename += f"_run{args.run_id}"
    state_filename += ".json"
        
    config_dir = os.path.dirname(args.config)
    STATE_FILE_PATH = os.path.join(config_dir, state_filename) if config_dir else state_filename
    
    print(f"Using Config: {AGENTS_CONFIG_PATH}")
    print(f"Using State Log: {STATE_FILE_PATH}")
    
    config = load_config()
    validate_prompt_asymmetry(config)
    state = load_state(config, args.run_id)
    
    if args.continuous:
        print("Starting continuous simulation. Press Ctrl+C to stop.")
        try:
            while True:
                run_simulation_round(config, state)
        except KeyboardInterrupt:
            print("\nSimulation stopped by user.")
    else:
        current_rounds = state.get("round_count", 0)
        remaining_rounds = args.rounds - current_rounds
        if remaining_rounds <= 0:
            print(f"Simulation already completed {current_rounds}/{args.rounds} rounds. Skipping execution.")
        else:
            print(f"Resuming simulation: running {remaining_rounds} rounds to reach target of {args.rounds} rounds.")
            for _ in range(remaining_rounds):
                run_simulation_round(config, state)

if __name__ == "__main__":
    main()

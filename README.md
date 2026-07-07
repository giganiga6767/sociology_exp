# Multi-Agent Sociolinguistic Simulation Framework

> A computational sociology framework simulating **Communication Accommodation Theory (CAT)** in regional-to-urban student cohorts, modeled after Bangalore JEE coaching center dynamics.

---

## Overview

This project simulates how **16-year-old students** from Tier-2 South Indian cities (e.g., Kadapa, Rajahmundry) linguistically adapt when placed in a cosmopolitan Bangalore JEE coaching environment alongside students who grew up speaking internet-native, Gen-Z English.

The simulation models **code-switching**, **lexical convergence**, and **identity-pressured register shifts** across parallel communication channels (a shared peer group chat and private family chats), using local LLMs running entirely on CPU.

### Theoretical Grounding

- **Communication Accommodation Theory (CAT)** — Giles (1973): agents converge or diverge linguistically based on social pressure, identity, and emotional state.
- **Diglossic Code-Switching** — Ferguson (1959): agents maintain separate linguistic registers for public vs. private channels.
- **Finite State Machine (FSM) Emotional Model**: each agent's emotional state gates how strongly they accommodate or resist peer linguistic norms.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        engine.py                                │
│   ┌─────────────────┐    ┌──────────────────┐    ┌───────────┐ │
│   │  Prompt Builder  │    │  Emotional FSM   │    │  XML      │ │
│   │  + Asymmetry     │───▶│  State Machine   │───▶│  Parser   │ │
│   │    Guard         │    │  (per agent)     │    │  + Fallbk │ │
│   └─────────────────┘    └──────────────────┘    └───────────┘ │
│              │                     │                    │       │
│              ▼                     ▼                    ▼       │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │             Ollama (phi3 local model, CPU)               │  │
│   └─────────────────────────────────────────────────────────┘  │
│              │                                                   │
│              ▼                                                   │
│   ┌─────────────────┐    ┌──────────────────┐                  │
│   │   State File    │───▶│   api.py         │                  │
│   │ (JSON, atomic   │    │   (FastAPI)       │                  │
│   │   write)        │    │   :8000           │                  │
│   └─────────────────┘    └──────────────────┘                  │
│                                    │                            │
└────────────────────────────────────┼────────────────────────────┘
                                     │
                                     ▼
               ┌──────────────────────────────────┐
               │     dashboard/ (Next.js)          │
               │     Real-time simulation viewer   │
               │     :3000                         │
               └──────────────────────────────────┘
```

---

## Repository Structure

```
sociology_experiment/
├── engine.py                      # Core orchestration engine
├── analytics.py                   # Gemini-powered LAR evaluator
├── slang_injector.py              # Dynamic slang vocabulary module
├── api.py                         # FastAPI backend exposing state + analytics
├── dashboard/                     # Next.js visual dashboard frontend
├── agents_run1_null.json          # Run 1: Null Control (no interventions)
├── agents_run2_ablated.json       # Run 2: Ablated (slang only, no emotions)
├── agents_run3_experimental.json  # Run 3: Full experiment (emotions + religion)
├── agents_run4_religion.json      # Run 4: 4-agent religion case study
├── run_all.sh                     # Full batch runner (3 conditions × 3 runs)
├── run_religion.sh                # Standalone religion case study runner
├── state_*.json                   # Auto-generated simulation state logs
├── analytics_*.json               # Auto-generated Gemini LAR evaluation results
└── .env                           # API keys (not committed)
```

---

## Experimental Conditions

The study uses a **3-condition, 3-run design** (9 total simulation runs):

| Run | Config File | Condition | Description |
|-----|-------------|-----------|-------------|
| **Run 1** | `agents_run1_null.json` | **Null Control** | No slang injection, no emotional FSM, no religion seed. Pure LLM baseline. |
| **Run 2** | `agents_run2_ablated.json` | **Ablated** | Dynamic slang injection active, but no emotional state machine. |
| **Run 3** | `agents_run3_experimental.json` | **Experimental** | Full system: emotional FSM + slang injection + religion seed topic. |
| *(Run 4)* | `agents_run4_religion.json` | *(Case Study)* | 4-agent religion-only case study (not part of main experimental design). |

---

## Ecological Realism & Anti-Slop Prompt Guardrails (Frozen Run 3)

All prompt configurations have been re-engineered to enforce authentic registers, eliminating corporate-speak, robotic politeness, and structural padding.

### 1. Zero-Tolerance "Template English" Restrictions
The following linguistic patterns, tokens, and AI-isms are strictly banned from agent system prompts:
* **Corporate/Motivational speak**: *let's tackle, hit the essentials, stay sharp, manage study-life balance, ready when you are, nitty-gritty, keep our heads straight, roll up our sleeves, win-win, curveball, grind, delve, leverage, navigate, foster, resilience, team*.
* **Robotic openers**: *Wow, Sure thing!, Absolutely!, Hey team!, Heads up everyone, Alright folks, Gotcha!, No worries though*.
* **Greeting Prefix Suppression**: Agents are forbidden from prefixing every message with redundant greetings (*hey*, *yo*, *bro*) once a conversation is active.
* **Imperfect WhatsApp English**: Prompts encourage natural, subject-dropping syntax (*"physics pending"*, *"chem not done"*, *"sir gave another sheet"*, *"sleep gone"*, *"mock was horrible"*, *"still pending"*).

### 2. Conversational Disagreement & Discontinued Planning
To prevent artificial consensus, prompts explicitly instruct agents to disagree, change topics, ignore messages, or say *"idk"* (e.g. *"nah"*, *"not worth it"*, *"our coaching already finished it"*, *"sir said ignore"*, *"I don't think so"*). Collective planning templates (*"let's revise"*, *"let's study together"*) are replaced with individualistic statements (*"I'm dead"*, *"Didn't finish"*, *"You guys do"*, *"I'll see tomorrow"*).

### 3. Cohort Persona & Cultural Grounding
* **Realistic Parents**: Parent messages are restricted to **under 20-25 words**, a maximum of one emoji, and ask only practical questions (*"Tinnava?"*, *"Mock ela ayyindi?"*, *"Don't skip dinner."*, *"Money enough?"*), with no motivational speeches.
* **Telugu Honorific Correction**: Tier-2 parents are forbidden from using the honorific *"Anna"* to address their children (which is culturally inaccurate). They address them by name, *"babu"*, or *"ra"*.
* **Character Fingerprints (Topic Preferences)**: Each student focuses on a distinct topic preference to drive natural conversational drift:
  * `student_t1` (Arjun): Money, family savings, and fees.
  * `student_t2` (Kiran): Homesickness, crying, and bad mess food.
  * `student_t3` (Vijay): Sleep deprivation, sleeping 4 hours, and crowded doubt sessions.
  * `student_c1` (Rhea): Marks, exam rankings, and parental expectations.
  * `student_c2` (Aarav): Phone distraction, screen time, and math modules length.
  * `student_c3` (Neha): Hostel laundry, roommates, and old friends isolation.

### 4. Topic Decay Guard
In `engine.py`, prompt formatting instructs agents to let stale topics decay and refrain from reviving old discussions from their long-term memory unless they are still active in the recent 10-message channel history.

### 5. Word-Count Symmetry
All system prompts are padded/truncated to **exactly 320 words** (hydrated) to satisfy the Prompt Asymmetry Guard. To avoid semantic leakage, padding pools are composed of cohort-appropriate, single-word tokens (*lite, scene, bro* for students; *rest, eat, safe* for parents).

### 6. Chronological Context Injector (Longitudinal Jumps)
To map a 6-month high-stakes coaching timeline across 25 rounds, the engine dynamically injects neutral system events at the start of specific rounds into all channels:
*   **Round 6 (1 Month)**: First major All-India mock test results drop; syllabus backlogs accumulate.
*   **Round 12 (3 Months)**: Festival season isolation; homesickness peak.
*   **Round 18 (5 Months)**: Intensive AITS test series begins; sleep deprivation and pressure.
*   **Round 23 (6 Months)**: Final exam crunch; burnout and panic momentum.

---

## Agent Cohorts

10 agents are split across two cohorts and three communication channels:

| Agent ID | Cohort | Role | Channel(s) |
|---|---|---|---|
| `student_c1`, `student_c2`, `student_c3` | **Cosmopolitan** (Bangalore-native) | Student | Global_Square + Cosmopolitan_Family |
| `student_t1`, `student_t2`, `student_t3` | **Tier-2 Regional** (Kadapa/Andhra) | Student | Global_Square + Tier2_Family |
| `parent_c1`, `parent_c2` | Cosmopolitan | Parent | Cosmopolitan_Family only |
| `parent_t1`, `parent_t2` | Tier-2 Regional | Parent | Tier2_Family only |

### Communication Channels

- **`Global_Square`** — Public peer group. All 6 students interact. Social pressure to accommodate is highest here.
- **`Tier2_Family`** — Private family channel. Tier-2 students and their parents. Native register expected; code-switching down is the hypothesis.
- **`Cosmopolitan_Family`** — Private family channel. Cosmopolitan students and their parents. Baseline cosmopolitan register.

---

## Emotional State Machine (FSM)

Each agent has an internal emotional state that modulates their linguistic register. States are defined per agent in the config JSON and can transition based on conversational triggers.

```
   composed ──────────────────────────────────────────────────────┐
      │                                                            │
      ▼  [peer dismissal / accent mockery]                         │
   anxious ──[prolonged pressure]──▶ identity_fragmented           │ [validation]
      │                                                            │
      ▼  [direct confrontation]                                    │
   defensive ──[escalation]──▶ hostile                             │
      │                                                            │
      ▼  [sustained isolation]                                     │
   withdrawn ──────────────────────────────────────────────────────┘
```

In the **Null Control** run, emotional states are absent. This allows the LAR metric to measure "pure" LLM structural priming as a baseline.

---

## Research Metrics & Debugging Telemetry

The framework computes several publication-ready quantitative and qualitative metrics to compare experimental conditions:

### 1. Lexical Accommodation Ratio (LAR)
LAR evaluates out-group register adaptation, computed using inter-rater reliability (3 Gemini passes):
```
For Tier-2 agents:
  LAR = cosmopolitan_term_count / (regional_term_count + cosmopolitan_term_count)

For Cosmopolitan agents:
  LAR = regional_term_count / (regional_term_count + cosmopolitan_term_count)
```
* **LAR → 1.0**: Full convergence toward the out-group register.
* **LAR → 0.0**: Complete in-group register maintenance (diglossic resistance).

### 2. Conversational Echo-Chamber Repetition Rates
To mathematically prove the existence of conversational loops in ablated conditions, the engine calculates:
* **Trigram Repetition Percentage**: The proportion of repeating three-word sequences across the entire dialogue history.
* **Repeated Openings**: The percentage of messages starting with the same top-3 double-word openers (measuring structural anchoring).

### 3. Shannon Entropy & Vocabulary Diversity
Per-round Shannon Entropy ($H$) evaluates vocabulary diversity and topic decay:
$$H = -\sum_{i} p_i \log_2 p_i$$
Where $p_i$ is the relative frequency of non-stop-word keywords. Decaying entropy indicates narrowing topic diversity (vocabulary echo-chambers).

### 4. Safety Guard & Quality Control Audit
Logs detailed breakdowns of safety retries inside `quality_control_audit.json`:
* `xml_tags`: XML validation violations.
* `role_leak`: Address leaks (parents using student slang, etc.).
* `preachy_leak`: Preachy/speech-like language blocks.
* `trigram_repetition`: Repetition trap triggers.
* `fallback_triggers`: Active safety fallbacks.

---

## Components

### `engine.py` — Simulation Engine

The core orchestrator. Key features:

- **`validate_prompt_asymmetry()`** — Prompt Asymmetry Guard: enforces ≤5% word-count deviation across all agent system prompts before any run. Raises `ValueError` if violated.
- **`fetch_seed_topic(run_id)`** — Fetches a real technology headline from the Indian News API (`saurav.tech/NewsAPI`). Falls back to Gemini generation if the API is offline. Each run uses a deterministic index into the article list to guarantee distinct seed topics across Run 1/2/3.
- **`build_prompt(agent, base_prompt, emotional_states)`** — Hydrates system prompt templates with the agent's current emotional state description.
- **`generate_turn(agent, channel_history, config, state)`** — Queries Ollama (phi3) locally. Uses `num_predict: 200` to cap token generation for CPU speed. Parses the `<response>` XML tag from output with a two-pass fallback parser.
- **`inject_seed_topic()`** — Injects Turn 0 as a "Project Manager" system message in `Global_Square` to kick off the conversation.
- **`save_state()`** — Atomic write via temp file + `os.replace()` to prevent JSON corruption during multi-turn runs.

### `slang_injector.py` — Dynamic Vocabulary Module

Queries the Gemini API to generate contextually appropriate slang for each `(cohort, emotional_state)` pair. Results are **in-memory cached** to avoid repeated API calls. Fails silently if the API key is missing (used in Run 2 and Run 3 only).

### `analytics.py` — LAR Evaluator

Feeds the entire simulation state JSON to Gemini as a structured analysis task. Runs `N` evaluation passes (default: 3) for **inter-rater reliability**. Aggregates results (average counts, union of term lists) and saves to:
- `analytics_results.json` — global cache for the FastAPI `/api/analytics` endpoint
- `analytics_<run_name>.json` — run-specific cache

### `api.py` — FastAPI Backend

Lightweight REST API serving the live simulation state and evaluation results to the dashboard.

| Endpoint | Description |
|---|---|
| `GET /api/state` | Returns the latest simulation state JSON. Auto-detects most recent `state_*.json` if default path is missing. |
| `GET /api/analytics` | Returns the Gemini LAR evaluation results. Returns 404 with instructions if analytics have not been run yet. |

### `dashboard/` — Next.js Visual Dashboard

Real-time frontend to monitor agent conversations across all 3 channels, track emotional state transitions, and view LAR bar charts. Runs on port `:3000` and queries the FastAPI backend on `:8000`.

---

## Setup & Prerequisites

### System Requirements
- Python 3.10+
- Node.js 18+ (for dashboard)
- [Ollama](https://ollama.com) installed with `phi3` model pulled
- ~4GB RAM minimum (phi3 runs on CPU)

### Installation

```bash
# 1. Enter the project directory
cd ~/sociology_experiment

# 2. Create and activate a Python virtual environment
python3 -m venv ~/ic_venv
source ~/ic_venv/bin/activate

# 3. Install Python dependencies
pip install requests fastapi uvicorn google-generativeai typing-extensions

# 4. Pull the local LLM
ollama pull phi3

# 5. Install dashboard dependencies
cd dashboard && npm install && cd ..

# 6. Set up your API key
echo 'GEMINI_API_KEY="your_key_here"' > .env
```

---

## Running the Simulation

### Step 1: Start background services

```bash
# Terminal 1: Start Ollama server
ollama serve

# Terminal 2: Start FastAPI backend
source ~/ic_venv/bin/activate && python3 api.py

# Terminal 3: Start the dashboard
cd dashboard && npm run dev
```

Open `http://localhost:3000` to view the live dashboard.

### Step 2: Run a simulation

```bash
# Quick test: Run 1 (Null Control) for 3 rounds
source ~/ic_venv/bin/activate
python3 engine.py --config agents_run1_null.json --rounds 3 --run-id 1

# Full experimental run: Run 3 for 20 rounds
python3 engine.py --config agents_run3_experimental.json --rounds 20 --run-id 1
```

### Step 3: Evaluate results

```bash
# Run Gemini-powered LAR evaluation (3 inter-rater passes)
python3 analytics.py --log state_run1_null_run1.json --eval-passes 3
```

Results are printed to the terminal and saved to `analytics_results.json`, which the dashboard reads automatically.

### Full automated batch run (all 9 simulations)

```bash
bash run_all.sh
```
> ⚠️ This runs 3 conditions × 3 runs × 20 rounds each (~24 hours on CPU).

---

## Turn Counts Reference

| Configuration | Agents | Turns/Round | Rounds | Total Turns |
|---|---|---|---|---|
| Run 1 (Null) | 10 | 16 | 3 (test) / 20 (full) | 48 / 320 |
| Run 2 (Ablated) | 10 | 16 | 20 × 2 runs | 640 |
| Run 3 (Experimental) | 10 | 16 | 20 × 2 runs | 640 |

**Turns per round breakdown:**
- `Global_Square`: 6 student turns
- `Tier2_Family`: 5 turns (3 students + 2 parents)
- `Cosmopolitan_Family`: 5 turns (3 students + 2 parents)

---

## Research Context

This project is designed as the computational backbone for a mixed-methods sociolinguistics paper validating **Communication Accommodation Theory** in regional-to-urban Indian student migration contexts.

The simulation provides a controlled synthetic dataset. For the full research paper, the LAR curves from Run 1 (null), Run 2 (ablated), and Run 3 (experimental) are compared against **qualitative human baseline data** collected via structured interviews with real Tier-2 regional students in Bangalore coaching cohorts.

The human validation interviews ask:
1. **Channel asymmetry**: Do you use native honorifics (da, maccha, anna) with family but suppress them with Bangalore peers?
2. **Accommodation timeline**: How many weeks before you started naturally adopting your cosmopolitan peers' vocabulary?
3. **Trigger point**: Was there a specific social event that made you consciously start modifying your speech register?

---

## Acknowledgements

Built with assistance from [Google Antigravity](https://antigravity.google) AI coding assistant.  
Local LLM inference via [Ollama](https://ollama.com) (phi3 model).  
Semantic evaluation via [Google Gemini](https://deepmind.google/gemini).

import os
import json
import urllib.request
import urllib.error

# In-memory cache for generated slang per cohort and state
_slang_cache = {}

def load_env():
    """Load variables from a local .env file if it exists."""
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    key, val = line.strip().split("=", 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")

def get_slang(agent_cohort, emotional_state):
    """
    Generate or return cached slang terms appropriate for the agent cohort and state.
    Fails silently: returns empty dict/list if API key is missing or model queries fail.
    """
    # Force lowercase for matching cache keys
    cohort = agent_cohort.lower()
    state = emotional_state.lower()
    cache_key = (cohort, state)
    
    if cache_key in _slang_cache:
        return _slang_cache[cache_key]
        
    load_env()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"cohort": cohort, "state": state, "slang": [], "usage_note": ""}
        
    prompt = f"""You are a slang generator for a sociolinguistics simulation.
Return ONLY a JSON object. No explanation. No markdown. No backticks.

Cohort: {cohort}
Emotional state: {state}

tier2 cohort = Telugu-English code-mixed, 16-year-old from Kadapa, 
first time away from home, WhatsApp register.
Terms like: da, maccha, anna, aithe, endi, ra, cheppu, adhe, antunnav

cosmo cohort = Gen-Z English-heavy, 16-year-old from Bangalore, 
grew up in this environment, internet-native register.
Terms like: fr, ngl, bro, cooked, based, no cap, lowkey, ratio, 
deadass, W, L, mid, slay

State modifiers:
- composed: natural everyday slang
- anxious: hedging, uncertain, trailing off
- defensive: sharper, more identity-assertive
- hostile: confrontational, clipped, dismissive  
- withdrawn: minimal, one word answers, silence signals
- identity_fragmented: erratic mix of both registers

Return exactly:
{{
  "cohort": "{cohort}",
  "state": "{state}",
  "slang": ["da", "maccha", "aithe", "anna", "ra"],
  "usage_note": "drop these naturally mid-sentence, not at the start"
}}"""

    # Structured request matching existing URL endpoints in engine
    # (calling gemini-3.5-flash standard developer REST API via urllib)
    url = f"https://generativetoolkit.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.3
        }
    }
    
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        # Open request with a timeout of 10s to prevent hang ups
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            text_out = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            parsed = json.loads(text_out)
            # Store in cache
            _slang_cache[cache_key] = parsed
            return parsed
    except Exception:
        # Fail silently
        return {"cohort": cohort, "state": state, "slang": [], "usage_note": ""}

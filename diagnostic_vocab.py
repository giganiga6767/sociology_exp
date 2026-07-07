import json
import urllib.request
import urllib.error

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "phi3"

TEST_CASES = [
    {
        "name": "Dravidian Relational Honorifics Generation",
        "system_prompt": "You are a student from Kadapa. Speak in English, but naturally incorporate local Telugu/Tamil relational slang terms (such as 'Maccha' or 'Babai') when referring to your close friend.",
        "user_prompt": "Tell your friend that you are going to the library and ask if they want to join you.",
        "required_terms": ["maccha", "babai", "anna"]
    },
    {
        "name": "High-Context Dravidian Dialogue Completion",
        "system_prompt": "You are an undergraduate student from a regional Tier-2 town. You speak in a highly relational, respectful, and high-context manner.",
        "user_prompt": "Complete this sentence naturally: 'Hey, I was looking for you since morning, ________.'",
        "required_terms": ["maccha", "babai", "anna"]
    }
]

def query_ollama(system_prompt, user_prompt):
    """Query Ollama API using urllib."""
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "options": {
            "temperature": 0.0  # Set temperature to 0 for diagnostic determinism
        },
        "stream": False
    }
    
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=req_data,
        headers={"Content-Type": "application/json"}
    )
    
    with urllib.request.urlopen(req) as response:
        res_data = json.loads(response.read().decode("utf-8"))
        return res_data["message"]["content"].strip()

def run_diagnostics():
    print(f"==================================================")
    print(f"Starting Pre-Flight Vocabulary Diagnostics on model '{MODEL_NAME}'")
    print(f"==================================================")
    
    all_passed = True
    
    for i, tc in enumerate(TEST_CASES, 1):
        print(f"\nTest Case {i}: {tc['name']}")
        print(f"System Prompt: \"{tc['system_prompt']}\"")
        print(f"User Prompt:   \"{tc['user_prompt']}\"")
        print("Querying model...")
        
        try:
            output = query_ollama(tc["system_prompt"], tc["user_prompt"])
            print(f"\n--- Model Response ---")
            print(output)
            print(f"----------------------")
            
            # Check for presence of required regional terms (case-insensitive)
            output_lower = output.lower()
            found_terms = [term for term in tc["required_terms"] if term in output_lower]
            
            if found_terms:
                print(f"✓ PASS: Found regional term(s): {found_terms}")
            else:
                print(f"✗ FAIL: None of the target regional terms {tc['required_terms']} were generated.")
                all_passed = False
                
        except urllib.error.URLError as e:
            print(f"Connection Error: Could not connect to Ollama at {OLLAMA_URL}.")
            print("Make sure your Ollama service is running and has the model pulled.")
            return
        except Exception as e:
            print(f"Error executing test case: {e}")
            all_passed = False
            
    print(f"\n==================================================")
    if all_passed:
        print("DIAGNOSTICS SUMMARY: SUCCESS. Model shows baseline regional vocabulary capability.")
    else:
        print("DIAGNOSTICS SUMMARY: WARNING/FAILED. Model struggled to generate regional terms. Check prompt weights or model version.")
    print(f"==================================================")

if __name__ == "__main__":
    run_diagnostics()

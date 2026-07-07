import os
import json
import argparse
import sys

try:
    import google.generativeai as genai
    import typing_extensions as typing
except ImportError:
    print("Error: Missing required packages. Please install them using:")
    print("  pip install google-generativeai typing-extensions")
    sys.exit(1)

# Configure typing structures for Gemini structured output
class AgentAnalysis(typing.TypedDict):
    agent_name: str
    channel_name: str
    regional_term_count: int
    cosmopolitan_term_count: int
    identified_regional_terms: list[str]
    identified_cosmo_terms: list[str]

class AnalysisResult(typing.TypedDict):
    evaluations: list[AgentAnalysis]

def load_env():
    """Load variables from a local .env file if it exists."""
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    key, val = line.strip().split("=", 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")

def analyze_state(log_path, eval_passes=3):
    if not os.path.exists(log_path):
        print(f"Error: Log file '{log_path}' does not exist.")
        sys.exit(1)
        
    load_env()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable is not set and no .env file found.")
        print("Please set it in your terminal before running this script, e.g.:")
        print("  export GEMINI_API_KEY='your_api_key_here'")
        sys.exit(1)
        
    genai.configure(api_key=api_key)
    
    with open(log_path, "r") as f:
        state = json.load(f)
        
    print(f"Loading simulation state log from: {log_path}")
    print(f"Total turns detected: {state.get('turn_count', 0)}")
    
    prompt = (
        "You are a strict, objective Sociolinguistic Evaluator. Analyze the provided multi-agent simulation log "
        "to evaluate the communication adaptation dynamics between agents of different cohorts (Tier-2 Regional vs Cosmopolitan).\n\n"
        "Your task is to identify:\n"
        "1. Tier-2 Regional Markers: traditional, localized, or relational Dravidian (Telugu/Tamil/Kannada) code-switching "
        "or regional honorifics (e.g., Maccha, Babai, Anna, Bava, Da, Ra, etc.) representing values of community and precedent.\n"
        "2. Cosmopolitan Tech Markers: high-churn, hyper-online Gen-Z slang or institutional cosmopolitan tech/internet jargon "
        "(e.g., cooked, based, brainrot, rizz, cap, bruh, mid, sus, etc.) representing values of digital optimization and speed.\n\n"
        "Generate a structured report summarizing the counts and listing the actual identified terms for each agent, "
        "grouped separately for each channel they participated in.\n\n"
        f"Simulation Log JSON Data:\n{json.dumps(state, indent=2)}"
    )
    
    print(f"Connecting to Gemini-3.5-Flash for {eval_passes} evaluation passes (Inter-Rater Reliability)...")
    evaluations_runs = []
    
    for i in range(eval_passes):
        print(f"  - Executing Pass {i + 1}/{eval_passes}...")
        try:
            model = genai.GenerativeModel("gemini-3.5-flash")
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=AnalysisResult,
                    temperature=0.2  # Slight temperature allows inter-rater variation
                )
            )
            run_results = json.loads(response.text)
            evaluations_runs.append(run_results.get("evaluations", []))
        except Exception as e:
            print(f"    Warning: Pass {i + 1} failed: {e}")
            
    if not evaluations_runs:
        print("Error: All evaluation passes failed.")
        sys.exit(1)

    # Aggregate counts (average) and list of terms (union)
    aggregated = {}
    for run in evaluations_runs:
        for item in run:
            key = (item["agent_name"], item["channel_name"])
            if key not in aggregated:
                aggregated[key] = {
                    "agent_name": item["agent_name"],
                    "channel_name": item["channel_name"],
                    "regional_term_counts": [],
                    "cosmopolitan_term_counts": [],
                    "identified_regional_terms": set(),
                    "identified_cosmo_terms": set()
                }
            agg = aggregated[key]
            agg["regional_term_counts"].append(item.get("regional_term_count", 0))
            agg["cosmopolitan_term_counts"].append(item.get("cosmopolitan_term_count", 0))
            agg["identified_regional_terms"].update(item.get("identified_regional_terms", []))
            agg["identified_cosmo_terms"].update(item.get("identified_cosmo_terms", []))

    final_evaluations = []
    for key, agg in aggregated.items():
        avg_reg = sum(agg["regional_term_counts"]) / len(agg["regional_term_counts"])
        avg_cos = sum(agg["cosmopolitan_term_counts"]) / len(agg["cosmopolitan_term_counts"])
        
        # Calculate formalized Lexical Accommodation Ratio (LAR)
        agent_name = agg["agent_name"]
        is_tier2 = " T" in agent_name or "student_t" in agent_name or "parent_t" in agent_name
        
        total_slang = avg_reg + avg_cos
        if total_slang > 0:
            lar = avg_cos / total_slang if is_tier2 else avg_reg / total_slang
        else:
            lar = 0.0
            
        final_item = {
            "agent_name": agg["agent_name"],
            "channel_name": agg["channel_name"],
            "regional_term_count": round(avg_reg),
            "cosmopolitan_term_count": round(avg_cos),
            "lexical_accommodation_ratio": round(lar, 4),
            "identified_regional_terms": sorted(list(agg["identified_regional_terms"])),
            "identified_cosmo_terms": sorted(list(agg["identified_cosmo_terms"]))
        }
        final_evaluations.append(final_item)

    import math
    from collections import Counter

    def compute_repetition_metrics(state_data):
        all_texts = []
        openings = []
        for channel, history in state_data.get("channels", {}).items():
            for msg in history:
                if msg.get("sender_id") == "system":
                    continue
                content = msg.get("content", "").strip()
                if content:
                    all_texts.append(content)
                    words = content.split()
                    if len(words) >= 2:
                        openings.append(" ".join(words[:2]).lower())
                    elif len(words) == 1:
                        openings.append(words[0].lower())
        
        trigrams_list = []
        for text in all_texts:
            words = text.lower().split()
            if len(words) >= 3:
                for i in range(len(words) - 2):
                    trigrams_list.append(tuple(words[i:i+3]))
                    
        total_trigrams = len(trigrams_list)
        if total_trigrams > 0:
            trigram_counts = Counter(trigrams_list)
            unique_trigrams = len(trigram_counts)
            rep_trigrams_pct = (total_trigrams - unique_trigrams) / total_trigrams
        else:
            rep_trigrams_pct = 0.0
            
        total_openings = len(openings)
        if total_openings > 0:
            opening_counts = Counter(openings)
            top_3_sum = sum(count for _, count in opening_counts.most_common(3))
            repeated_openings_pct = top_3_sum / total_openings
            top_openings = [f"'{o}' ({c})" for o, c in opening_counts.most_common(3)]
        else:
            repeated_openings_pct = 0.0
            top_openings = []
            
        return {
            "total_trigrams": total_trigrams,
            "repeated_trigrams_pct": round(rep_trigrams_pct, 4),
            "repeated_openings_pct": round(repeated_openings_pct, 4),
            "top_openings": top_openings
        }

    def compute_topic_diversity(state_data):
        round_messages = {}
        stop_words = {
            "the", "a", "and", "to", "is", "of", "in", "it", "that", "you", "he", "she", 
            "we", "they", "this", "but", "with", "for", "as", "on", "at", "by", "an", "be",
            "have", "are", "was", "were", "or", "from", "my", "your", "our", "their", "i", 
            "me", "us", "them", "him", "her", "so", "up", "out", "about", "who", "what", 
            "how", "why", "where", "when", "can", "will", "would", "should", "could", "do",
            "does", "did", "no", "yes", "not", "just", "get", "got", "go", "going", "take",
            "make", "see", "think", "know", "say", "said", "tell", "told", "want", "like", 
            "has", "had", "been", "here", "there", "about", "more", "some", "any", "all",
            "very", "now", "then", "also", "into", "than", "other", "only", "well", "look"
        }
        for channel, history in state_data.get("channels", {}).items():
            for msg in history:
                if msg.get("sender_id") == "system":
                    continue
                content = msg.get("content", "").strip()
                if content:
                    rnd = msg.get("round")
                    if rnd is None:
                        rnd = state_data.get("round_count", 1)
                    if rnd not in round_messages:
                        round_messages[rnd] = []
                    round_messages[rnd].append(content)
                    
        round_stats = {}
        for rnd, texts in round_messages.items():
            words = []
            for text in texts:
                import re
                cleaned = re.sub(r'[^\w\s]', '', text.lower())
                words.extend([w for w in cleaned.split() if w not in stop_words and len(w) > 2])
            total_words = len(words)
            unique_words = len(set(words))
            entropy = 0.0
            if total_words > 0:
                counts = Counter(words)
                for w, count in counts.items():
                    p = count / total_words
                    entropy -= p * math.log2(p)
            round_stats[str(rnd)] = {
                "total_keywords": total_words,
                "unique_keywords": unique_words,
                "entropy": round(entropy, 4)
            }
        return round_stats

    results = {
        "evaluations": final_evaluations,
        "repetition_metrics": compute_repetition_metrics(state),
        "topic_diversity_metrics": compute_topic_diversity(state)
    }
    
    # Save results to files
    try:
        # Cache globally for FastAPI default endpoint
        with open("analytics_results.json", "w") as rf:
            json.dump(results, rf, indent=2)
        # Cache run-specifically
        log_base = os.path.basename(log_path)
        log_root, _ = os.path.splitext(log_base)
        run_name = log_root.replace("state_", "")
        run_analytics_file = f"analytics_{run_name}.json"
        with open(run_analytics_file, "w") as arf:
            json.dump(results, arf, indent=2)
        print(f"Saved aggregated evaluations to analytics_results.json and {run_analytics_file}")
    except Exception as e:
        print(f"Error saving evaluation outputs: {e}")

    print("\n" + "=" * 135)
    print(f"{'AGENT NAME':<18} | {'CHANNEL':<22} | {'REG. COUNT':<10} | {'COSMO COUNT':<11} | {'LAR':<8} | {'REGIONAL TERMS':<25} | {'COSMO TERMS':<25}")
    print("=" * 135)
    
    for eval_item in final_evaluations:
        agent = eval_item.get("agent_name", "N/A")
        channel = eval_item.get("channel_name", "N/A")
        reg_count = eval_item.get("regional_term_count", 0)
        cos_count = eval_item.get("cosmopolitan_term_count", 0)
        lar = eval_item.get("lexical_accommodation_ratio", 0.0)
        reg_terms = ", ".join(eval_item.get("identified_regional_terms", []))
        cos_terms = ", ".join(eval_item.get("identified_cosmo_terms", []))
        
        # Truncate lists if they are too long for formatting
        if len(reg_terms) > 23:
            reg_terms = reg_terms[:20] + "..."
        if len(cos_terms) > 23:
            cos_terms = cos_terms[:20] + "..."
            
        print(f"{agent:<18} | {channel:<22} | {reg_count:<10} | {cos_count:<11} | {lar:<8.2%} | {reg_terms:<25} | {cos_terms:<25}")
    print("=" * 135 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gemini-Powered Sociolinguistic Simulation Log Evaluator")
    parser.add_argument("--log", type=str, required=True, help="Path to the JSON state file generated by the simulation")
    parser.add_argument("--eval-passes", type=int, default=3, help="Number of inter-rater evaluation passes to run for consensus")
    args = parser.parse_args()
    
    analyze_state(args.log, args.eval_passes)

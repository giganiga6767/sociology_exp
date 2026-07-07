#!/bin/bash

# Computational Sociology Simulation - Ablated Overnight Run (19 Rounds x 2 Passes)
# Config: agents_run2_ablated.json (10 agents, slang injector active, no emotional FSM)
# Timeline: 5-month longitudinal jumps injected at Rounds 6, 12, 18

source /home/niranjan/ic_venv/bin/activate

# Check if GEMINI_API_KEY is defined in environment or .env
if [ -z "$GEMINI_API_KEY" ]; then
    if [ -f ".env" ]; then
        # Parse from local .env
        export GEMINI_API_KEY=$(grep -v '^#' .env | grep -E '^GEMINI_API_KEY=' | head -n 1 | cut -d '=' -f 2- | tr -d '"'\')
    fi
fi
if [ -z "$GEMINI_API_KEY" ]; then
    echo "Warning: GEMINI_API_KEY is not set. Evaluations may fail."
fi

echo "=========================================================="
echo "Starting Ablated Run Simulation Suite (19 Rounds x 2 Passes)"
echo "Target: agents_run2_ablated.json"
echo "Start Time: $(date)"
echo "=========================================================="

# ----------------------------------------------------------
# PASS 1
# ----------------------------------------------------------
echo "----------------------------------------------------------"
echo "Starting PASS 1 / 2"
echo "----------------------------------------------------------"

# Clean up previous simulation state to start fresh
rm -f simulation_state.json

# Run simulation
python3 engine.py --config agents_run2_ablated.json --rounds 19 --run-id 1

# Check if state log was created
if [ -f "state_run2_ablated_run1.json" ]; then
    echo "PASS 1 simulation complete. Running Gemini LAR Evaluation..."
    python3 analytics.py --log state_run2_ablated_run1.json --eval-passes 3
else
    echo "Error: state_run2_ablated_run1.json not found. Skipping evaluation."
fi

echo "Pass 1 complete. Cooling down for 15 seconds..."
sleep 15

# ----------------------------------------------------------
# PASS 2
# ----------------------------------------------------------
echo "----------------------------------------------------------"
echo "Starting PASS 2 / 2"
echo "----------------------------------------------------------"

# Clean up state to prevent resume overlap
rm -f simulation_state.json

# Run simulation
python3 engine.py --config agents_run2_ablated.json --rounds 19 --run-id 2

# Check if state log was created
if [ -f "state_run2_ablated_run2.json" ]; then
    echo "PASS 2 simulation complete. Running Gemini LAR Evaluation..."
    python3 analytics.py --log state_run2_ablated_run2.json --eval-passes 3
else
    echo "Error: state_run2_ablated_run2.json not found. Skipping evaluation."
fi

# ----------------------------------------------------------
# COMBINATION & AGGREGATION
# ----------------------------------------------------------
echo "----------------------------------------------------------"
echo "Starting Results Aggregation and Document Compilation..."
echo "----------------------------------------------------------"

python3 compile_overnight_results.py

echo "=========================================================="
echo "Ablated Run Suite Complete! Check exp_results folder."
echo "End Time: $(date)"
echo "=========================================================="

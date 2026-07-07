#!/bin/bash

# Activate virtual environment
source /home/niranjan/ic_venv/bin/activate

echo "=========================================================="
echo "Starting Progressive Religion Simulation Suite (20 Rounds)"
echo "Total Runs: 3 (Run IDs 1 to 3)"
echo "=========================================================="

for run_id in 1 2 3
do
  echo "----------------------------------------------------------"
  echo "Running Religion Configuration | Run ID: $run_id"
  echo "Start Time: $(date)"
  echo "----------------------------------------------------------"
  
  # Run the simulation
  python3 engine.py --config agents_run4_religion.json --rounds 20 --run-id "$run_id"
  
  # Derive output state log path
  state_file="state_run4_religion_run${run_id}.json"
  
  if [ -f "$state_file" ]; then
    echo "Running Gemini-3.5-Flash Evaluation on: $state_file"
    python3 analytics.py --log "$state_file" --eval-passes 3
  else
    echo "Warning: State file $state_file not found."
  fi
  
  echo "Run complete. Cooling down for 10 seconds..."
  sleep 10
done

echo "=========================================================="
echo "Religion Runs & Evaluations Completed Successfully!"
echo "=========================================================="

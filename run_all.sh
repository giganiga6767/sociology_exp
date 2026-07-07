#!/bin/bash

# Activate virtual environment
source /home/niranjan/ic_venv/bin/activate

echo "=========================================================="
echo "Starting Computational Sociology Simulation Suite (20 Rounds)"
echo "Total Runs: 9 (3 Conditions x 3 Runs)"
echo "Estimated Duration: ~24 Hours"
echo "=========================================================="

# Define configurations
configs=("agents_run1_null.json" "agents_run2_ablated.json" "agents_run3_experimental.json")

# Loop through run IDs 1 to 3
for run_id in 1 2 3
do
  for config in "${configs[@]}"
  do
    echo "----------------------------------------------------------"
    echo "Running Configuration: $config | Run ID: $run_id"
    echo "Start Time: $(date)"
    echo "----------------------------------------------------------"
    
    # Run the simulation
    python3 engine.py --config "$config" --rounds 20 --run-id "$run_id"
    
    # Derive the expected state filename
    # E.g., agents_run1_null.json -> state_run1_null_run1.json
    config_base=$(basename "$config" .json)
    config_root=${config_base/agents_/}
    state_file="state_${config_root}_run${run_id}.json"
    
    # Run the evaluation immediately to sync results to the dashboard database
    if [ -f "$state_file" ]; then
      echo "Running Gemini-3.5-Flash Evaluation on: $state_file"
      python3 analytics.py --log "$state_file" --eval-passes 3
    else
      echo "Warning: State file $state_file not found. Skipping evaluation."
    fi
    
    echo "Run complete. Cooling down for 10 seconds..."
    sleep 10
  done
done

echo "=========================================================="
echo "All Simulation Runs & Evaluations Completed Successfully!"
echo "=========================================================="

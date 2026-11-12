#!/bin/bash

set -euo pipefail

cd /home/user

bash scripts/method.sh
bash scripts/evaluate_train.sh /home/user/experiment_results/core_claim
bash scripts/evaluate_test.sh /home/user/experiment_results/core_claim
python3 validate.py --compare

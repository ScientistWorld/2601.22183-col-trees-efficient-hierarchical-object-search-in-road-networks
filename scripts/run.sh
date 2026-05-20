#!/bin/bash

set -euo pipefail

cd /home/user

bash scripts/evaluate_train.sh /home/user/experiment_results
bash scripts/evaluate_test.sh /home/user/experiment_results

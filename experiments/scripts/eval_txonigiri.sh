#!/bin/bash

set -x
set -e

export PYTHONUNBUFFERED="True"
export CUDA_VISIBLE_DEVICES=0

python3 ./tools/eval_txonigiri.py --dataset_root ./datasets/txonigiri\
  --model trained_models/txonigiri/pose_model_178_0.03759706698358059.pth\
  --refine_model trained_checkpoints/linemod/pose_refine_model_493_0.006761023565178073.pth
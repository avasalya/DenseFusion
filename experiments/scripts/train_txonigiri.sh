#!/bin/bash

set -x
set -e

export PYTHONUNBUFFERED="True"
export CUDA_VISIBLE_DEVICES=0


# python3 ./tools/train.py --dataset txonigiri\
  # --dataset_root ./datasets/txonigiri\

python3 ./tools/train.py --dataset txonigiri\
  --dataset_root ./datasets/txonigiri\
  --resume_posenet /pose_model_237_0.011332584197517951.pth\
  --start_epoch 1

# python3 ./tools/train.py --dataset txonigiri\
#   --dataset_root ./datasets/txonigiri\
#   --resume_posenet /pose_model_178_0.03759_v1.pth\
#   --start_epoch 1
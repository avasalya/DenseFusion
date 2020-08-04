#!/bin/bash

set -x
set -e

export PYTHONUNBUFFERED="True"
export CUDA_VISIBLE_DEVICES=0,1,2,3


# python3 ./tools/train.py --dataset txonigiri\
#   --dataset_root ./datasets/txonigiri\
  

python3 ./tools/train.py --dataset txonigiri\
  --dataset_root ./datasets/txonigiri\
  --resume_posenet /pose_model_178_0.03759706698358059.pth\
  --start_epoch 200
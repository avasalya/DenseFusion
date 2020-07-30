#!/bin/bash

set -x
set -e

export PYTHONUNBUFFERED="True"
export CUDA_VISIBLE_DEVICES=0,1,2,3

python3 ./tools/train.py --dataset txonigiri\
  --dataset_root ./datasets/txonigiri
# Lint as: python3
# Copyright 2020 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Experiment factory methods."""

from official.core import registry
from official.modeling.hyperparams import config_definitions as cfg


_REGISTERED_CONFIGS = {}


def register_config_factory(name):
  """Register ExperimentConfig factory method."""
  return registry.register(_REGISTERED_CONFIGS, name)


def get_exp_config_creater(exp_name: str):
  """Looks up ExperimentConfig factory methods."""
  exp_creater = registry.lookup(_REGISTERED_CONFIGS, exp_name)
  return exp_creater


def get_exp_config(exp_name: str) -> cfg.ExperimentConfig:
  return get_exp_config_creater(exp_name)()

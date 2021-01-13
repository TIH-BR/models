# Copyright 2021 The TensorFlow Authors. All Rights Reserved.
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

"""Experimental MultiTask base class for multi-task training/evaluation."""
import abc
from typing import Dict, List, Optional, Text, Union

import tensorflow as tf
from official.core import base_task
from official.core import config_definitions
from official.core import task_factory
from official.modeling import optimization
from official.modeling.multitask import configs

OptimizationConfig = optimization.OptimizationConfig
RuntimeConfig = config_definitions.RuntimeConfig


class MultiTask(tf.Module, metaclass=abc.ABCMeta):
  """A multi-task class to manage multiple tasks."""

  def __init__(self,
               tasks: Union[Dict[Text, base_task.Task], List[base_task.Task]],
               task_mixing_steps: Optional[Dict[str, int]] = None,
               task_weights: Optional[Dict[str, float]] = None,
               task_eval_steps: Optional[Dict[str, int]] = None,
               name: Optional[str] = None):
    """MultiTask initialization.

    Args:
      tasks: a list or a flat dict of Task.
      task_mixing_steps: a dict of (task, mixing steps).
      task_weights: a dict of (task, loss weight).
      task_eval_steps: a dict of (task, eval steps).
      name: the instance name of a MultiTask object.
    """
    super().__init__(name=name)
    if isinstance(tasks, list):
      self._tasks = {}
      for task in tasks:
        if task.name in self._tasks:
          raise ValueError("Duplicated tasks found, task.name is %s" %
                           task.name)
        self._tasks[task.name] = task
    elif isinstance(tasks, dict):
      self._tasks = tasks
    else:
      raise ValueError("The tasks argument has an invalid type: %s" %
                       type(tasks))
    self._task_eval_steps = task_eval_steps or {}
    self._task_eval_steps = dict([
        (name, self._task_eval_steps.get(name, None)) for name in self.tasks
    ])
    self._task_mixing_steps = task_mixing_steps or {}
    self._task_mixing_steps = dict([
        (name, self._task_mixing_steps.get(name, 1)) for name in self.tasks
    ])
    self._task_weights = task_weights or {}
    self._task_weights = dict([
        (name, self._task_weights.get(name, None)) for name in self.tasks
    ])

  @classmethod
  def from_config(cls, config: configs.MultiTaskConfig, logging_dir=None):
    tasks = {}
    task_eval_steps = {}
    task_mixing_steps = {}
    task_weights = {}
    for task_routine in config.task_routines:
      task_name = task_routine.task_name
      tasks[task_name] = task_factory.get_task(
          task_routine.task_config, logging_dir=logging_dir)
      task_eval_steps[task_name] = task_routine.eval_steps
      task_mixing_steps[task_name] = task_routine.mixing_steps
      task_weights[task_name] = task_routine.task_weight
    return cls(
        tasks,
        task_mixing_steps=task_mixing_steps,
        task_eval_steps=task_eval_steps,
        task_weights=task_weights)

  @property
  def tasks(self):
    return self._tasks

  def task_eval_steps(self, task_name):
    return self._task_eval_steps[task_name]

  def task_mixing_steps(self, task_name):
    return self._task_mixing_steps[task_name]

  def task_weight(self, task_name):
    return self._task_weights[task_name]

  @classmethod
  def create_optimizer(cls,
                       optimizer_config: OptimizationConfig,
                       runtime_config: Optional[RuntimeConfig] = None):
    return base_task.Task.create_optimizer(
        optimizer_config=optimizer_config, runtime_config=runtime_config)

  def joint_train_step(self, task_inputs, multi_task_model, optimizer,
                       task_metrics):
    """The joint train step.

    Args:
      task_inputs: a dictionary of task names and per-task features.
      multi_task_model: a MultiTaskModel instance.
      optimizer: a tf.optimizers.Optimizer.
      task_metrics: a dictionary of task names and per-task metrics.
    Returns:
      A dictionary of losses, inculding per-task losses and their weighted sum.
    """
    losses = {}
    with tf.GradientTape() as tape:
      total_loss = 0.0
      for name, model in multi_task_model.sub_tasks.items():
        inputs = task_inputs[name]
        if isinstance(inputs, tuple) and len(inputs) == 2:
          features, labels = inputs
        elif isinstance(inputs, dict):
          features, labels = inputs, inputs
        else:
          raise ValueError("The iterator output is neither a tuple nor a "
                           "dictionary. It is not implemented to support "
                           "such outputs.")
        outputs = model(features, training=True)
        task_loss = self.tasks[name].build_losses(labels, outputs)
        task_weight = self.task_weight(name)
        total_loss += task_weight * task_loss
        losses[name] = task_loss
        self.tasks[name].process_metrics(task_metrics[name], labels, outputs)

        # Scales loss as the default gradients allreduce performs sum inside
        # the optimizer.
        scaled_loss = total_loss / tf.distribute.get_strategy(
        ).num_replicas_in_sync
    tvars = multi_task_model.trainable_variables
    grads = tape.gradient(scaled_loss, tvars)
    optimizer.apply_gradients(list(zip(grads, tvars)))
    losses["total_loss"] = total_loss
    return losses

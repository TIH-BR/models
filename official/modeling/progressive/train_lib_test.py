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
"""Tests for the progressive train_lib."""
import os

from absl import flags
from absl.testing import parameterized
import tensorflow as tf

from tensorflow.python.distribute import combinations
from tensorflow.python.distribute import strategy_combinations
from official.common import flags as tfm_flags
# pylint: disable=unused-import
from official.common import registry_imports
# pylint: enable=unused-import
from official.core import config_definitions as cfg
from official.core import task_factory
from official.modeling.hyperparams import params_dict
from official.modeling.progressive import train_lib
from official.modeling.progressive import trainer as prog_trainer_lib
from official.nlp.data import pretrain_dataloader
from official.nlp.tasks import progressive_masked_lm

FLAGS = flags.FLAGS

tfm_flags.define_flags()


class TrainTest(tf.test.TestCase, parameterized.TestCase):

  def setUp(self):
    super(TrainTest, self).setUp()
    self._test_config = {
        'trainer': {
            'checkpoint_interval': 10,
            'steps_per_loop': 10,
            'summary_interval': 10,
            'train_steps': 10,
            'validation_steps': 5,
            'validation_interval': 10,
            'continuous_eval_timeout': 1,
            'optimizer_config': {
                'optimizer': {
                    'type': 'sgd',
                },
                'learning_rate': {
                    'type': 'constant'
                }
            }
        },
    }

  @combinations.generate(
      combinations.combine(
          distribution_strategy=[
              strategy_combinations.default_strategy,
              strategy_combinations.cloud_tpu_strategy,
              strategy_combinations.one_device_strategy_gpu,
          ],
          mode='eager',
          flag_mode=['train', 'eval', 'train_and_eval'],
          run_post_eval=[True, False]))
  def test_end_to_end(self, distribution_strategy, flag_mode, run_post_eval):
    model_dir = self.get_temp_dir()
    experiment_config = cfg.ExperimentConfig(
        trainer=prog_trainer_lib.ProgressiveTrainerConfig(),
        task=progressive_masked_lm.ProgMaskedLMConfig(
            train_data=pretrain_dataloader.BertPretrainDataConfig(
                input_path='dummy'),
            validation_data=pretrain_dataloader.BertPretrainDataConfig(
                is_training=False,
                input_path='dummy')))
    experiment_config = params_dict.override_params_dict(
        experiment_config, self._test_config, is_strict=False)

    with distribution_strategy.scope():
      task = task_factory.get_task(experiment_config.task,
                                   logging_dir=model_dir)

    _, logs = train_lib.run_experiment(
        distribution_strategy=distribution_strategy,
        task=task,
        mode=flag_mode,
        params=experiment_config,
        model_dir=model_dir,
        run_post_eval=run_post_eval)

    if run_post_eval:
      self.assertNotEmpty(logs)
    else:
      self.assertEmpty(logs)

    if flag_mode == 'eval':
      return
    self.assertNotEmpty(
        tf.io.gfile.glob(os.path.join(model_dir, 'checkpoint')))
    # Tests continuous evaluation.
    _, logs = train_lib.run_experiment(
        distribution_strategy=distribution_strategy,
        task=task,
        mode='continuous_eval',
        params=experiment_config,
        model_dir=model_dir,
        run_post_eval=run_post_eval)
    print(logs)


if __name__ == '__main__':
  tf.test.main()

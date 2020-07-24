# Copyright 2019 The TensorFlow Authors. All Rights Reserved.
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
"""Classification network."""
# pylint: disable=g-classes-have-attributes
from __future__ import absolute_import
from __future__ import division
# from __future__ import google_type_annotations
from __future__ import print_function

import tensorflow as tf


@tf.keras.utils.register_keras_serializable(package='Text')
class TokenClassification(tf.keras.Model):
  """TokenClassification network head for BERT modeling.

  This network implements a simple token classifier head based on a dense layer.
  *Note* that the network is constructed by
  [Keras Functional API](https://keras.io/guides/functional_api/).

  Arguments:
    input_width: The innermost dimension of the input tensor to this network.
    num_classes: The number of classes that this network should classify to.
    activation: The activation, if any, for the dense layer in this network.
    initializer: The initializer for the dense layer in this network. Defaults
      to a Glorot uniform initializer.
    output: The output style for this network. Can be either 'logits' or
      'predictions'.
  """

  def __init__(self,
               input_width,
               num_classes,
               initializer='glorot_uniform',
               output='logits',
               **kwargs):
    self._self_setattr_tracking = False
    self._config_dict = {
        'input_width': input_width,
        'num_classes': num_classes,
        'initializer': initializer,
        'output': output,
    }

    sequence_data = tf.keras.layers.Input(
        shape=(None, input_width), name='sequence_data', dtype=tf.float32)

    self.logits = tf.keras.layers.Dense(
        num_classes,
        activation=None,
        kernel_initializer=initializer,
        name='predictions/transform/logits')(
            sequence_data)
    predictions = tf.keras.layers.Activation(tf.nn.log_softmax)(self.logits)

    if output == 'logits':
      output_tensors = self.logits
    elif output == 'predictions':
      output_tensors = predictions
    else:
      raise ValueError(
          ('Unknown `output` value "%s". `output` can be either "logits" or '
           '"predictions"') % output)

    super(TokenClassification, self).__init__(
        inputs=[sequence_data], outputs=output_tensors, **kwargs)

  def get_config(self):
    return self._config_dict

  @classmethod
  def from_config(cls, config, custom_objects=None):
    return cls(**config)

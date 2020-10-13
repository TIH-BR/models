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
"""Segmentation heads."""

# Import libraries
import tensorflow as tf

from official.modeling import tf_utils
from official.vision.beta.ops import spatial_transform_ops


@tf.keras.utils.register_keras_serializable(package='Vision')
class SegmentationHead(tf.keras.layers.Layer):
  """Segmentation head."""

  def __init__(self,
               num_classes,
               level,
               num_convs=2,
               num_filters=256,
               upsample_factor=1,
               activation='relu',
               use_sync_bn=False,
               norm_momentum=0.99,
               norm_epsilon=0.001,
               kernel_regularizer=None,
               bias_regularizer=None,
               **kwargs):
    """Initialize params to build segmentation head.

    Args:
      num_classes: `int` number of mask classification categories. The number of
        classes does not include background class.
      level: `int` or `str`, level to use to build segmentation head.
      num_convs: `int` number of stacked convolution before the last prediction
        layer.
      num_filters: `int` number to specify the number of filters used.
        Default is 256.
      upsample_factor: `int` number to specify the upsampling factor to generate
        finer mask. Default 1 means no upsampling is applied.
      activation: `string`, indicating which activation is used, e.g. 'relu',
        'swish', etc.
      use_sync_bn: `bool`, whether to use synchronized batch normalization
        across different replicas.
      norm_momentum: `float`, the momentum parameter of the normalization
        layers.
      norm_epsilon: `float`, the epsilon parameter of the normalization layers.
      kernel_regularizer: `tf.keras.regularizers.Regularizer` object for layer
        kernel.
      bias_regularizer: `tf.keras.regularizers.Regularizer` object for bias.
      **kwargs: other keyword arguments passed to Layer.
    """
    super(SegmentationHead, self).__init__(**kwargs)
    self._config_dict = {
        'num_classes': num_classes,
        'level': level,
        'num_convs': num_convs,
        'num_filters': num_filters,
        'upsample_factor': upsample_factor,
        'activation': activation,
        'use_sync_bn': use_sync_bn,
        'norm_momentum': norm_momentum,
        'norm_epsilon': norm_epsilon,
        'kernel_regularizer': kernel_regularizer,
        'bias_regularizer': bias_regularizer,
    }
    if tf.keras.backend.image_data_format() == 'channels_last':
      self._bn_axis = -1
    else:
      self._bn_axis = 1
    self._activation = tf_utils.get_activation(activation)

  def build(self, input_shape):
    """Creates the variables of the segmentation head."""
    conv_op = tf.keras.layers.Conv2D
    conv_kwargs = {
        'kernel_size': 3,
        'padding': 'same',
        'bias_initializer': tf.zeros_initializer(),
        'kernel_initializer': tf.keras.initializers.RandomNormal(stddev=0.01),
        'kernel_regularizer': self._config_dict['kernel_regularizer'],
    }
    bn_op = (tf.keras.layers.experimental.SyncBatchNormalization
             if self._config_dict['use_sync_bn']
             else tf.keras.layers.BatchNormalization)
    bn_kwargs = {
        'axis': self._bn_axis,
        'momentum': self._config_dict['norm_momentum'],
        'epsilon': self._config_dict['norm_epsilon'],
    }

    # Segmentation head layers.
    self._convs = []
    self._norms = []
    for i in range(self._config_dict['num_convs']):
      conv_name = 'segmentation_head_conv_{}'.format(i)
      self._convs.append(
          conv_op(
              name=conv_name,
              filters=self._config_dict['num_filters'],
              **conv_kwargs))
      norm_name = 'segmentation_head_norm_{}'.format(i)
      self._norms.append(bn_op(name=norm_name, **bn_kwargs))

    self._classifier = conv_op(
        name='segmentation_output',
        filters=self._config_dict['num_classes'],
        **conv_kwargs)

    super(SegmentationHead, self).build(input_shape)

  def call(self, features):
    """Forward pass of the segmentation head.

    Args:
      features: a dict of tensors
        - key: `str`, the level of the multilevel features.
        - values: `Tensor`, the feature map tensors, whose shape is
            [batch, height_l, width_l, channels].
    Returns:
      segmentation prediction mask: `Tensor`, the segmentation mask scores
        predicted from input feature.
    """
    x = features[str(self._config_dict['level'])]
    for conv, norm in zip(self._convs, self._norms):
      x = conv(x)
      x = norm(x)
      x = self._activation(x)
    x = spatial_transform_ops.nearest_upsampling(
        x, scale=self._config_dict['upsample_factor'])
    return self._classifier(x)

  def get_config(self):
    return self._config_dict

  @classmethod
  def from_config(cls, config):
    return cls(**config)


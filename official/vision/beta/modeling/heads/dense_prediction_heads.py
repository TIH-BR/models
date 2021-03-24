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

"""Contains definitions of dense prediction heads."""

# Import libraries
import numpy as np
import tensorflow as tf

from official.modeling import tf_utils


@tf.keras.utils.register_keras_serializable(package='Vision')
class RetinaNetHead(tf.keras.layers.Layer):
  """Creates a RetinaNet head."""

  def __init__(self,
               min_level,
               max_level,
               num_classes,
               num_anchors_per_location,
               num_convs=4,
               num_filters=256,
               use_separable_conv=False,
               activation='relu',
               use_sync_bn=False,
               norm_momentum=0.99,
               norm_epsilon=0.001,
               kernel_regularizer=None,
               bias_regularizer=None,
               **kwargs):
    """Initializes a RetinaNet head.

    Args:
      min_level: An `int` number of minimum feature level.
      max_level: An `int` number of maximum feature level.
      num_classes: An `int` number of classes to predict.
      num_anchors_per_location: An `int` number of number of anchors per pixel
        location.
      num_convs: An `int` number that represents the number of the intermediate
        conv layers before the prediction.
      num_filters: An `int` number that represents the number of filters of the
        intermediate conv layers.
      use_separable_conv: A `bool` that indicates whether the separable
        convolution layers is used.
      activation: A `str` that indicates which activation is used, e.g. 'relu',
        'swish', etc.
      use_sync_bn: A `bool` that indicates whether to use synchronized batch
        normalization across different replicas.
      norm_momentum: A `float` of normalization momentum for the moving average.
      norm_epsilon: A `float` added to variance to avoid dividing by zero.
      kernel_regularizer: A `tf.keras.regularizers.Regularizer` object for
        Conv2D. Default is None.
      bias_regularizer: A `tf.keras.regularizers.Regularizer` object for Conv2D.
      **kwargs: Additional keyword arguments to be passed.
    """
    super(RetinaNetHead, self).__init__(**kwargs)
    self._config_dict = {
        'min_level': min_level,
        'max_level': max_level,
        'num_classes': num_classes,
        'num_anchors_per_location': num_anchors_per_location,
        'num_convs': num_convs,
        'num_filters': num_filters,
        'use_separable_conv': use_separable_conv,
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
    """Creates the variables of the head."""
    conv_op = (tf.keras.layers.SeparableConv2D
               if self._config_dict['use_separable_conv']
               else tf.keras.layers.Conv2D)
    conv_kwargs = {
        'filters': self._config_dict['num_filters'],
        'kernel_size': 3,
        'padding': 'same',
        'bias_initializer': tf.zeros_initializer(),
        'bias_regularizer': self._config_dict['bias_regularizer'],
    }
    if not self._config_dict['use_separable_conv']:
      conv_kwargs.update({
          'kernel_initializer': tf.keras.initializers.RandomNormal(
              stddev=0.01),
          'kernel_regularizer': self._config_dict['kernel_regularizer'],
      })
    bn_op = (tf.keras.layers.experimental.SyncBatchNormalization
             if self._config_dict['use_sync_bn']
             else tf.keras.layers.BatchNormalization)
    bn_kwargs = {
        'axis': self._bn_axis,
        'momentum': self._config_dict['norm_momentum'],
        'epsilon': self._config_dict['norm_epsilon'],
    }

    # Class net.
    self._cls_convs = []
    self._cls_norms = []
    for level in range(
        self._config_dict['min_level'], self._config_dict['max_level'] + 1):
      this_level_cls_norms = []
      for i in range(self._config_dict['num_convs']):
        if level == self._config_dict['min_level']:
          cls_conv_name = 'classnet-conv_{}'.format(i)
          self._cls_convs.append(conv_op(name=cls_conv_name, **conv_kwargs))
        cls_norm_name = 'classnet-conv-norm_{}_{}'.format(level, i)
        this_level_cls_norms.append(bn_op(name=cls_norm_name, **bn_kwargs))
      self._cls_norms.append(this_level_cls_norms)

    classifier_kwargs = {
        'filters': (
            self._config_dict['num_classes'] *
            self._config_dict['num_anchors_per_location']),
        'kernel_size': 3,
        'padding': 'same',
        'bias_initializer': tf.constant_initializer(-np.log((1 - 0.01) / 0.01)),
        'bias_regularizer': self._config_dict['bias_regularizer'],
    }
    if not self._config_dict['use_separable_conv']:
      classifier_kwargs.update({
          'kernel_initializer': tf.keras.initializers.RandomNormal(stddev=1e-5),
          'kernel_regularizer': self._config_dict['kernel_regularizer'],
      })
    self._classifier = conv_op(name='scores', **classifier_kwargs)

    # Box net.
    self._box_convs = []
    self._box_norms = []
    for level in range(
        self._config_dict['min_level'], self._config_dict['max_level'] + 1):
      this_level_box_norms = []
      for i in range(self._config_dict['num_convs']):
        if level == self._config_dict['min_level']:
          box_conv_name = 'boxnet-conv_{}'.format(i)
          self._box_convs.append(conv_op(name=box_conv_name, **conv_kwargs))
        box_norm_name = 'boxnet-conv-norm_{}_{}'.format(level, i)
        this_level_box_norms.append(bn_op(name=box_norm_name, **bn_kwargs))
      self._box_norms.append(this_level_box_norms)

    box_regressor_kwargs = {
        'filters': 4 * self._config_dict['num_anchors_per_location'],
        'kernel_size': 3,
        'padding': 'same',
        'bias_initializer': tf.zeros_initializer(),
        'bias_regularizer': self._config_dict['bias_regularizer'],
    }
    if not self._config_dict['use_separable_conv']:
      box_regressor_kwargs.update({
          'kernel_initializer': tf.keras.initializers.RandomNormal(
              stddev=1e-5),
          'kernel_regularizer': self._config_dict['kernel_regularizer'],
      })
    self._box_regressor = conv_op(name='boxes', **box_regressor_kwargs)

    super(RetinaNetHead, self).build(input_shape)

  def call(self, features):
    """Forward pass of the RetinaNet head.

    Args:
      features: A `dict` of `tf.Tensor` where
        - key: A `str` of the level of the multilevel features.
        - values: A `tf.Tensor`, the feature map tensors, whose shape is
            [batch, height_l, width_l, channels].

    Returns:
      scores: A `dict` of `tf.Tensor` which includes scores of the predictions.
        - key: A `str` of the level of the multilevel predictions.
        - values: A `tf.Tensor` of the box scores predicted from a particular
            feature level, whose shape is
            [batch, height_l, width_l, num_classes * num_anchors_per_location].
      boxes: A `dict` of `tf.Tensor` which includes coordinates of the
        predictions.
        - key: A `str` of the level of the multilevel predictions.
        - values: A `tf.Tensor` of the box scores predicted from a particular
            feature level, whose shape is
            [batch, height_l, width_l, 4 * num_anchors_per_location].
    """
    scores = {}
    boxes = {}
    for i, level in enumerate(
        range(self._config_dict['min_level'],
              self._config_dict['max_level'] + 1)):
      this_level_features = features[str(level)]

      # class net.
      x = this_level_features
      for conv, norm in zip(self._cls_convs, self._cls_norms[i]):
        x = conv(x)
        x = norm(x)
        x = self._activation(x)
      scores[str(level)] = self._classifier(x)

      # box net.
      x = this_level_features
      for conv, norm in zip(self._box_convs, self._box_norms[i]):
        x = conv(x)
        x = norm(x)
        x = self._activation(x)
      boxes[str(level)] = self._box_regressor(x)
    return scores, boxes

  def get_config(self):
    return self._config_dict

  @classmethod
  def from_config(cls, config):
    return cls(**config)


@tf.keras.utils.register_keras_serializable(package='Vision')
class RPNHead(tf.keras.layers.Layer):
  """Creates a Region Proposal Network (RPN) head."""

  def __init__(self,
               min_level,
               max_level,
               num_anchors_per_location,
               num_convs=1,
               num_filters=256,
               use_separable_conv=False,
               activation='relu',
               use_sync_bn=False,
               norm_momentum=0.99,
               norm_epsilon=0.001,
               kernel_regularizer=None,
               bias_regularizer=None,
               **kwargs):
    """Initializes a Region Proposal Network head.

    Args:
      min_level: An `int` number of minimum feature level.
      max_level: An `int` number of maximum feature level.
      num_anchors_per_location: An `int` number of number of anchors per pixel
        location.
      num_convs: An `int` number that represents the number of the intermediate
        convolution layers before the prediction.
      num_filters: An `int` number that represents the number of filters of the
        intermediate convolution layers.
      use_separable_conv: A `bool` that indicates whether the separable
        convolution layers is used.
      activation: A `str` that indicates which activation is used, e.g. 'relu',
        'swish', etc.
      use_sync_bn: A `bool` that indicates whether to use synchronized batch
        normalization across different replicas.
      norm_momentum: A `float` of normalization momentum for the moving average.
      norm_epsilon: A `float` added to variance to avoid dividing by zero.
      kernel_regularizer: A `tf.keras.regularizers.Regularizer` object for
        Conv2D. Default is None.
      bias_regularizer: A `tf.keras.regularizers.Regularizer` object for Conv2D.
      **kwargs: Additional keyword arguments to be passed.
    """
    super(RPNHead, self).__init__(**kwargs)
    self._config_dict = {
        'min_level': min_level,
        'max_level': max_level,
        'num_anchors_per_location': num_anchors_per_location,
        'num_convs': num_convs,
        'num_filters': num_filters,
        'use_separable_conv': use_separable_conv,
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
    """Creates the variables of the head."""
    conv_op = (tf.keras.layers.SeparableConv2D
               if self._config_dict['use_separable_conv']
               else tf.keras.layers.Conv2D)
    conv_kwargs = {
        'filters': self._config_dict['num_filters'],
        'kernel_size': 3,
        'padding': 'same',
        'bias_initializer': tf.zeros_initializer(),
        'bias_regularizer': self._config_dict['bias_regularizer'],
    }
    if not self._config_dict['use_separable_conv']:
      conv_kwargs.update({
          'kernel_initializer': tf.keras.initializers.RandomNormal(
              stddev=0.01),
          'kernel_regularizer': self._config_dict['kernel_regularizer'],
      })
    bn_op = (tf.keras.layers.experimental.SyncBatchNormalization
             if self._config_dict['use_sync_bn']
             else tf.keras.layers.BatchNormalization)
    bn_kwargs = {
        'axis': self._bn_axis,
        'momentum': self._config_dict['norm_momentum'],
        'epsilon': self._config_dict['norm_epsilon'],
    }

    self._convs = []
    self._norms = []
    for level in range(
        self._config_dict['min_level'], self._config_dict['max_level'] + 1):
      this_level_norms = []
      for i in range(self._config_dict['num_convs']):
        if level == self._config_dict['min_level']:
          conv_name = 'rpn-conv_{}'.format(i)
          self._convs.append(conv_op(name=conv_name, **conv_kwargs))
        norm_name = 'rpn-conv-norm_{}_{}'.format(level, i)
        this_level_norms.append(bn_op(name=norm_name, **bn_kwargs))
      self._norms.append(this_level_norms)

    classifier_kwargs = {
        'filters': self._config_dict['num_anchors_per_location'],
        'kernel_size': 1,
        'padding': 'valid',
        'bias_initializer': tf.zeros_initializer(),
        'bias_regularizer': self._config_dict['bias_regularizer'],
    }
    if not self._config_dict['use_separable_conv']:
      classifier_kwargs.update({
          'kernel_initializer': tf.keras.initializers.RandomNormal(
              stddev=1e-5),
          'kernel_regularizer': self._config_dict['kernel_regularizer'],
      })
    self._classifier = conv_op(name='rpn-scores', **classifier_kwargs)

    box_regressor_kwargs = {
        'filters': 4 * self._config_dict['num_anchors_per_location'],
        'kernel_size': 1,
        'padding': 'valid',
        'bias_initializer': tf.zeros_initializer(),
        'bias_regularizer': self._config_dict['bias_regularizer'],
    }
    if not self._config_dict['use_separable_conv']:
      box_regressor_kwargs.update({
          'kernel_initializer': tf.keras.initializers.RandomNormal(
              stddev=1e-5),
          'kernel_regularizer': self._config_dict['kernel_regularizer'],
      })
    self._box_regressor = conv_op(name='rpn-boxes', **box_regressor_kwargs)

    super(RPNHead, self).build(input_shape)

  def call(self, features):
    """Forward pass of the RPN head.

    Args:
      features: A `dict` of `tf.Tensor` where
        - key: A `str` of the level of the multilevel features.
        - values: A `tf.Tensor`, the feature map tensors, whose shape is [batch,
          height_l, width_l, channels].

    Returns:
      scores: A `dict` of `tf.Tensor` which includes scores of the predictions.
        - key: A `str` of the level of the multilevel predictions.
        - values: A `tf.Tensor` of the box scores predicted from a particular
            feature level, whose shape is
            [batch, height_l, width_l, num_classes * num_anchors_per_location].
      boxes: A `dict` of `tf.Tensor` which includes coordinates of the
        predictions.
        - key: A `str` of the level of the multilevel predictions.
        - values: A `tf.Tensor` of the box scores predicted from a particular
            feature level, whose shape is
            [batch, height_l, width_l, 4 * num_anchors_per_location].
    """
    scores = {}
    boxes = {}
    for i, level in enumerate(
        range(self._config_dict['min_level'],
              self._config_dict['max_level'] + 1)):
      x = features[str(level)]
      for conv, norm in zip(self._convs, self._norms[i]):
        x = conv(x)
        x = norm(x)
        x = self._activation(x)
      scores[str(level)] = self._classifier(x)
      boxes[str(level)] = self._box_regressor(x)
    return scores, boxes

  def get_config(self):
    return self._config_dict

  @classmethod
  def from_config(cls, config):
    return cls(**config)

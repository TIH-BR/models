# Copyright 2017 The TensorFlow Authors. All Rights Reserved.
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

"""SSDFeatureExtractor for MobilenetV1 features."""

import tensorflow as tf

from object_detection.meta_architectures import ssd_meta_arch
from object_detection.models import feature_map_generators
from object_detection.utils import ops
from object_detection.utils import shape_utils
from nets import mobilenet_v1

slim = tf.contrib.slim


class SSDMobileNetV1FeatureExtractor(ssd_meta_arch.SSDFeatureExtractor):
  """SSD Feature Extractor using MobilenetV1 features."""

  def __init__(self,
               is_training,
               depth_multiplier,
               min_depth,
               pad_to_multiple,
               conv_hyperparams,
               batch_norm_trainable=True,
               reuse_weights=None,
               use_explicit_padding=False,
               use_depthwise=False,
               inplace_batchnorm_update=False):
    """MobileNetV1 Feature Extractor for SSD Models.

    Args:
      is_training: whether the network is in training mode.
      depth_multiplier: float depth multiplier for feature extractor.
      min_depth: minimum feature extractor depth.
      pad_to_multiple: the nearest multiple to zero pad the input height and
        width dimensions to.
      conv_hyperparams: tf slim arg_scope for conv2d and separable_conv2d ops.
      batch_norm_trainable: Whether to update batch norm parameters during
        training or not. When training with a small batch size
        (e.g. 1), it is desirable to disable batch norm update and use
        pretrained batch norm params.
      reuse_weights: Whether to reuse variables. Default is None.
      use_explicit_padding: Use 'VALID' padding for convolutions, but prepad
        inputs so that the output dimensions are the same as if 'SAME' padding
        were used.
      use_depthwise: Whether to use depthwise convolutions. Default is False.
      inplace_batchnorm_update: Whether to update batch_norm inplace during
        training. This is required for batch norm to work correctly on TPUs.
        When this is false, user must add a control dependency on
        tf.GraphKeys.UPDATE_OPS for train/loss op in order to update the batch
        norm moving average parameters.
    """
    super(SSDMobileNetV1FeatureExtractor, self).__init__(
        is_training, depth_multiplier, min_depth, pad_to_multiple,
        conv_hyperparams, batch_norm_trainable, reuse_weights,
        use_explicit_padding, use_depthwise, inplace_batchnorm_update)

  def preprocess(self, resized_inputs):
    """SSD preprocessing.

    Maps pixel values to the range [-1, 1].

    Args:
      resized_inputs: a [batch, height, width, channels] float tensor
        representing a batch of images.

    Returns:
      preprocessed_inputs: a [batch, height, width, channels] float tensor
        representing a batch of images.
    """
    return (2.0 / 255.0) * resized_inputs - 1.0

  def _extract_features(self, preprocessed_inputs):
    """Extract features from preprocessed inputs.

    Args:
      preprocessed_inputs: a [batch, height, width, channels] float tensor
        representing a batch of images.

    Returns:
      feature_maps: a list of tensors where the ith tensor has shape
        [batch, height_i, width_i, depth_i]
    """
    preprocessed_inputs = shape_utils.check_min_image_dim(
        33, preprocessed_inputs)

    feature_map_layout = {
        'from_layer': ['Conv2d_11_pointwise', 'Conv2d_13_pointwise', '', '',
                       '', ''],
        'layer_depth': [-1, -1, 512, 256, 256, 128],
        'use_explicit_padding': self._use_explicit_padding,
        'use_depthwise': self._use_depthwise,
    }

    with tf.variable_scope('MobilenetV1',
                           reuse=self._reuse_weights) as scope:
      with slim.arg_scope(
          mobilenet_v1.mobilenet_v1_arg_scope(
              is_training=(self._batch_norm_trainable and self._is_training))):
        # TODO(skligys): Enable fused batch norm once quantization supports it.
        with slim.arg_scope([slim.batch_norm], fused=False):
          _, image_features = mobilenet_v1.mobilenet_v1_base(
              ops.pad_to_multiple(preprocessed_inputs, self._pad_to_multiple),
              final_endpoint='Conv2d_13_pointwise',
              min_depth=self._min_depth,
              depth_multiplier=self._depth_multiplier,
              use_explicit_padding=self._use_explicit_padding,
              scope=scope)
      with slim.arg_scope(self._conv_hyperparams):
        # TODO(skligys): Enable fused batch norm once quantization supports it.
        with slim.arg_scope([slim.batch_norm], fused=False):
          feature_maps = feature_map_generators.multi_resolution_feature_maps(
              feature_map_layout=feature_map_layout,
              depth_multiplier=self._depth_multiplier,
              min_depth=self._min_depth,
              insert_1x1_conv=True,
              image_features=image_features)

    return feature_maps.values()

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

"""Embedded-friendly SSDFeatureExtractor for MobilenetV1 features."""

import tensorflow as tf

from object_detection.models import feature_map_generators
from object_detection.models import ssd_mobilenet_v1_feature_extractor
from object_detection.utils import ops
from nets import mobilenet_v1

slim = tf.contrib.slim


class EmbeddedSSDMobileNetV1FeatureExtractor(
    ssd_mobilenet_v1_feature_extractor.SSDMobileNetV1FeatureExtractor):
  """Embedded-friendly SSD Feature Extractor using MobilenetV1 features.

  This feature extractor is similar to SSD MobileNetV1 feature extractor, and
  it fixes input resolution to be 256x256, reduces the number of feature maps
  used for box prediction and ensures convolution kernel to be no larger
  than input tensor in spatial dimensions.

  This feature extractor requires support of the following ops if used in
  embedded devices:
  - Conv
  - DepthwiseConv
  - Relu6

  All conv/depthwiseconv use SAME padding, and no additional spatial padding is
  needed.
  """

  def __init__(self,
               is_training,
               depth_multiplier,
               min_depth,
               pad_to_multiple,
               conv_hyperparams_fn,
               reuse_weights=None,
               use_explicit_padding=False,
               use_depthwise=False):
    """MobileNetV1 Feature Extractor for Embedded-friendly SSD Models.

    Args:
      is_training: whether the network is in training mode.
      depth_multiplier: float depth multiplier for feature extractor.
      min_depth: minimum feature extractor depth.
      pad_to_multiple: the nearest multiple to zero pad the input height and
        width dimensions to. For EmbeddedSSD it must be set to 1.
      conv_hyperparams_fn: A function to construct tf slim arg_scope for conv2d
        and separable_conv2d ops.
      reuse_weights: Whether to reuse variables. Default is None.
      use_explicit_padding: Whether to use explicit padding when extracting
        features. Default is False.
      use_depthwise: Whether to use depthwise convolutions. Default is False.

    Raises:
      ValueError: upon invalid `pad_to_multiple` values.
    """
    if pad_to_multiple != 1:
      raise ValueError('Embedded-specific SSD only supports `pad_to_multiple` '
                       'of 1.')

    super(EmbeddedSSDMobileNetV1FeatureExtractor, self).__init__(
        is_training, depth_multiplier, min_depth, pad_to_multiple,
        conv_hyperparams_fn, reuse_weights, use_explicit_padding, use_depthwise)

  def extract_features(self, preprocessed_inputs):
    """Extract features from preprocessed inputs.

    Args:
      preprocessed_inputs: a [batch, height, width, channels] float tensor
        representing a batch of images.

    Returns:
      feature_maps: a list of tensors where the ith tensor has shape
        [batch, height_i, width_i, depth_i]

    Raises:
      ValueError: if image height or width are not 256 pixels.
    """
    image_shape = preprocessed_inputs.get_shape()
    image_shape.assert_has_rank(4)
    image_height = image_shape[1].value
    image_width = image_shape[2].value

    if image_height is None or image_width is None:
      shape_assert = tf.Assert(
          tf.logical_and(tf.equal(tf.shape(preprocessed_inputs)[1], 256),
                         tf.equal(tf.shape(preprocessed_inputs)[2], 256)),
          ['image size must be 256 in both height and width.'])
      with tf.control_dependencies([shape_assert]):
        preprocessed_inputs = tf.identity(preprocessed_inputs)
    elif image_height != 256 or image_width != 256:
      raise ValueError('image size must be = 256 in both height and width;'
                       ' image dim = %d,%d' % (image_height, image_width))

    feature_map_layout = {
        'from_layer': [
            'Conv2d_11_pointwise', 'Conv2d_13_pointwise', '', '', ''
        ],
        'layer_depth': [-1, -1, 512, 256, 256],
        'conv_kernel_size': [-1, -1, 3, 3, 2],
        'use_explicit_padding': self._use_explicit_padding,
        'use_depthwise': self._use_depthwise,
    }

    with slim.arg_scope(self._conv_hyperparams_fn()):
      with slim.arg_scope([slim.batch_norm], fused=False):
        with tf.variable_scope('MobilenetV1',
                               reuse=self._reuse_weights) as scope:
          _, image_features = mobilenet_v1.mobilenet_v1_base(
              ops.pad_to_multiple(preprocessed_inputs, self._pad_to_multiple),
              final_endpoint='Conv2d_13_pointwise',
              min_depth=self._min_depth,
              depth_multiplier=self._depth_multiplier,
              scope=scope)
          feature_maps = feature_map_generators.multi_resolution_feature_maps(
              feature_map_layout=feature_map_layout,
              depth_multiplier=self._depth_multiplier,
              min_depth=self._min_depth,
              insert_1x1_conv=True,
              image_features=image_features)

    return feature_maps.values()

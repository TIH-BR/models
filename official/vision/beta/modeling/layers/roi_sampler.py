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
"""ROI sampler."""

# Import libraries
import tensorflow as tf

from official.vision import keras_cv
from official.vision.beta.modeling.layers import box_sampler
from official.vision.beta.ops import box_ops


@tf.keras.utils.register_keras_serializable(package='Vision')
class ROISampler(tf.keras.layers.Layer):
  """Sample ROIs and assign targets to the sampled ROIs."""

  def __init__(self,
               mix_gt_boxes=True,
               num_sampled_rois=512,
               foreground_fraction=0.25,
               foreground_iou_threshold=0.5,
               background_iou_high_threshold=0.5,
               background_iou_low_threshold=0,
               **kwargs):
    """Initializes a ROI sampler.

    Args:
      mix_gt_boxes: bool, whether to mix the groundtruth boxes with proposed
        ROIs.
      num_sampled_rois: int, the number of sampled ROIs per image.
      foreground_fraction: float in [0, 1], what percentage of proposed ROIs
        should be sampled from the foreground boxes.
      foreground_iou_threshold: float, represent the IoU threshold for a box to
        be considered as positive (if >= `foreground_iou_threshold`).
      background_iou_high_threshold: float, represent the IoU threshold for a
        box to be considered as negative (if overlap in
        [`background_iou_low_threshold`, `background_iou_high_threshold`]).
      background_iou_low_threshold: float, represent the IoU threshold for a box
        to be considered as negative (if overlap in
        [`background_iou_low_threshold`, `background_iou_high_threshold`])
      **kwargs: other key word arguments passed to Layer.
    """
    self._config_dict = {
        'mix_gt_boxes': mix_gt_boxes,
        'num_sampled_rois': num_sampled_rois,
        'foreground_fraction': foreground_fraction,
        'foreground_iou_threshold': foreground_iou_threshold,
        'background_iou_high_threshold': background_iou_high_threshold,
        'background_iou_low_threshold': background_iou_low_threshold,
    }

    self._box_matcher = keras_cv.ops.BoxMatcher(
        thresholds=[
            background_iou_low_threshold, background_iou_high_threshold,
            foreground_iou_threshold
        ],
        indicators=[-3, -1, -2, 1])
    self._anchor_labeler = keras_cv.ops.AnchorLabeler()

    self._sampler = box_sampler.BoxSampler(
        num_sampled_rois, foreground_fraction)
    super(ROISampler, self).__init__(**kwargs)

  def call(self, boxes, gt_boxes, gt_classes):
    """Assigns the proposals with groundtruth classes and performs subsmpling.

    Given `proposed_boxes`, `gt_boxes`, and `gt_classes`, the function uses the
    following algorithm to generate the final `num_samples_per_image` RoIs.
      1. Calculates the IoU between each proposal box and each gt_boxes.
      2. Assigns each proposed box with a groundtruth class and box by choosing
         the largest IoU overlap.
      3. Samples `num_samples_per_image` boxes from all proposed boxes, and
         returns box_targets, class_targets, and RoIs.

    Args:
      boxes: a tensor of shape of [batch_size, N, 4]. N is the number of
        proposals before groundtruth assignment. The last dimension is the
        box coordinates w.r.t. the scaled images in [ymin, xmin, ymax, xmax]
        format.
      gt_boxes: a tensor of shape of [batch_size, MAX_NUM_INSTANCES, 4].
        The coordinates of gt_boxes are in the pixel coordinates of the scaled
        image. This tensor might have padding of values -1 indicating the
        invalid box coordinates.
      gt_classes: a tensor with a shape of [batch_size, MAX_NUM_INSTANCES]. This
        tensor might have paddings with values of -1 indicating the invalid
        classes.

    Returns:
      sampled_rois: a tensor of shape of [batch_size, K, 4], representing the
        coordinates of the sampled RoIs, where K is the number of the sampled
        RoIs, i.e. K = num_samples_per_image.
      sampled_gt_boxes: a tensor of shape of [batch_size, K, 4], storing the
        box coordinates of the matched groundtruth boxes of the samples RoIs.
      sampled_gt_classes: a tensor of shape of [batch_size, K], storing the
        classes of the matched groundtruth boxes of the sampled RoIs.
      sampled_gt_indices: a tensor of shape of [batch_size, K], storing the
        indices of the sampled groudntruth boxes in the original `gt_boxes`
        tensor, i.e.
        gt_boxes[sampled_gt_indices[:, i]] = sampled_gt_boxes[:, i].
    """
    if self._config_dict['mix_gt_boxes']:
      gt_boxes = tf.cast(gt_boxes, dtype=boxes.dtype)
      boxes = tf.concat([boxes, gt_boxes], axis=1)

    similarity_matrix = box_ops.bbox_overlap(boxes, gt_boxes)
    matched_gt_indices, match_indicators = self._box_matcher(similarity_matrix)
    positive_matches = tf.greater_equal(match_indicators, 0)
    negative_matches = tf.equal(match_indicators, -1)
    ignored_matches = tf.equal(match_indicators, -2)
    invalid_matches = tf.equal(match_indicators, -3)

    background_mask = tf.expand_dims(
        tf.logical_or(negative_matches, invalid_matches), -1)
    gt_classes = tf.expand_dims(gt_classes, axis=-1)
    matched_gt_classes = self._anchor_labeler(gt_classes, matched_gt_indices,
                                              background_mask)
    matched_gt_classes = tf.where(background_mask,
                                  tf.zeros_like(matched_gt_classes),
                                  matched_gt_classes)
    matched_gt_classes = tf.squeeze(matched_gt_classes, axis=-1)
    matched_gt_boxes = self._anchor_labeler(gt_boxes, matched_gt_indices,
                                            tf.tile(background_mask, [1, 1, 4]))
    matched_gt_boxes = tf.where(background_mask,
                                tf.zeros_like(matched_gt_boxes),
                                matched_gt_boxes)
    matched_gt_indices = tf.where(
        tf.squeeze(background_mask, -1), -tf.ones_like(matched_gt_indices),
        matched_gt_indices)

    sampled_indices = self._sampler(
        positive_matches, negative_matches, ignored_matches)

    sampled_rois, sampled_gt_boxes, sampled_gt_classes, sampled_gt_indices = (
        box_ops.gather_instances(
            sampled_indices,
            boxes,
            matched_gt_boxes,
            matched_gt_classes,
            matched_gt_indices))
    return (sampled_rois, sampled_gt_boxes, sampled_gt_classes,
            sampled_gt_indices)

  def get_config(self):
    return self._config_dict

  @classmethod
  def from_config(cls, config):
    return cls(**config)

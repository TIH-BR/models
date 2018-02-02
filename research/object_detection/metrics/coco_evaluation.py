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
"""Class for evaluating object detections with COCO metrics."""
import numpy as np
import tensorflow as tf

from object_detection.core import standard_fields
from object_detection.metrics import coco_tools
from object_detection.utils import object_detection_evaluation


class CocoDetectionEvaluator(object_detection_evaluation.DetectionEvaluator):
  """Class to evaluate COCO detection metrics."""

  def __init__(self, categories, all_metrics_per_category=False):
    """Constructor.

    Args:
      categories: A list of dicts, each of which has the following keys -
        'id': (required) an integer id uniquely identifying this category.
        'name': (required) string representing category name e.g., 'cat', 'dog'.
      all_metrics_per_category: Whether to include all the summary metrics for
        each category in per_category_ap. Be careful with setting it to true if
        you have more than handful of categories, because it will pollute
        your mldash.
    """
    super(CocoDetectionEvaluator, self).__init__(categories)
    # _image_ids is a dictionary that maps unique image ids to Booleans which
    # indicate whether a corresponding detection has been added.
    self._image_ids = {}
    self._groundtruth_list = []
    self._detection_boxes_list = []
    self._category_id_set = set([cat['id'] for cat in self._categories])
    self._annotation_id = 1
    self._metrics = None
    self._all_metrics_per_category = all_metrics_per_category

  def clear(self):
    """Clears the state to prepare for a fresh evaluation."""
    self._image_ids.clear()
    self._groundtruth_list = []
    self._detection_boxes_list = []

  def add_single_ground_truth_image_info(self,
                                         image_id,
                                         groundtruth_dict):
    """Adds groundtruth for a single image to be used for evaluation.

    If the image has already been added, a warning is logged, and groundtruth is
    ignored.

    Args:
      image_id: A unique string/integer identifier for the image.
      groundtruth_dict: A dictionary containing -
        InputDataFields.groundtruth_boxes: float32 numpy array of shape
          [num_boxes, 4] containing `num_boxes` groundtruth boxes of the format
          [ymin, xmin, ymax, xmax] in absolute image coordinates.
        InputDataFields.groundtruth_classes: integer numpy array of shape
          [num_boxes] containing 1-indexed groundtruth classes for the boxes.
    """
    if image_id in self._image_ids:
      tf.logging.warning('Ignoring ground truth with image id %s since it was '
                         'previously added', image_id)
      return

    self._groundtruth_list.extend(
        coco_tools.
        ExportSingleImageGroundtruthToCoco(
            image_id=image_id,
            next_annotation_id=self._annotation_id,
            category_id_set=self._category_id_set,
            groundtruth_boxes=groundtruth_dict[standard_fields.InputDataFields.
                                               groundtruth_boxes],
            groundtruth_classes=groundtruth_dict[standard_fields.
                                                 InputDataFields.
                                                 groundtruth_classes]))
    self._annotation_id += groundtruth_dict[standard_fields.InputDataFields.
                                            groundtruth_boxes].shape[0]
    self._image_ids[image_id] = False

  def add_single_detected_image_info(self,
                                     image_id,
                                     detections_dict):
    """Adds detections for a single image to be used for evaluation.

    If a detection has already been added for this image id, a warning is
    logged, and the detection is skipped.

    Args:
      image_id: A unique string/integer identifier for the image.
      detections_dict: A dictionary containing -
        DetectionResultFields.detection_boxes: float32 numpy array of shape
          [num_boxes, 4] containing `num_boxes` detection boxes of the format
          [ymin, xmin, ymax, xmax] in absolute image coordinates.
        DetectionResultFields.detection_scores: float32 numpy array of shape
          [num_boxes] containing detection scores for the boxes.
        DetectionResultFields.detection_classes: integer numpy array of shape
          [num_boxes] containing 1-indexed detection classes for the boxes.
        DetectionResultFields.detection_masks: optional uint8 numpy array of
          shape [num_boxes, image_height, image_width] containing instance
          masks for the boxes.

    Raises:
      ValueError: If groundtruth for the image_id is not available.
    """
    if image_id not in self._image_ids:
      raise ValueError('Missing groundtruth for image id: {}'.format(image_id))

    if self._image_ids[image_id]:
      tf.logging.warning('Ignoring detection with image id %s since it was '
                         'previously added', image_id)
      return

    self._detection_boxes_list.extend(
        coco_tools.ExportSingleImageDetectionBoxesToCoco(
            image_id=image_id,
            category_id_set=self._category_id_set,
            detection_boxes=detections_dict[standard_fields.
                                            DetectionResultFields
                                            .detection_boxes],
            detection_scores=detections_dict[standard_fields.
                                             DetectionResultFields.
                                             detection_scores],
            detection_classes=detections_dict[standard_fields.
                                              DetectionResultFields.
                                              detection_classes]))
    self._image_ids[image_id] = True

  def evaluate(self):
    """Evaluates the detection boxes and returns a dictionary of coco metrics.

    Returns:
      A dictionary holding -

      1. summary_metrics:
      'DetectionBoxes_Precision/mAP': mean average precision over classes
        averaged over IOU thresholds ranging from .5 to .95 with .05
        increments.
      'DetectionBoxes_Precision/mAP@.50IOU': mean average precision at 50% IOU
      'DetectionBoxes_Precision/mAP@.75IOU': mean average precision at 75% IOU
      'DetectionBoxes_Precision/mAP (small)': mean average precision for small
        objects (area < 32^2 pixels).
      'DetectionBoxes_Precision/mAP (medium)': mean average precision for
        medium sized objects (32^2 pixels < area < 96^2 pixels).
      'DetectionBoxes_Precision/mAP (large)': mean average precision for large
        objects (96^2 pixels < area < 10000^2 pixels).
      'DetectionBoxes_Recall/AR@1': average recall with 1 detection.
      'DetectionBoxes_Recall/AR@10': average recall with 10 detections.
      'DetectionBoxes_Recall/AR@100': average recall with 100 detections.
      'DetectionBoxes_Recall/AR@100 (small)': average recall for small objects
        with 100.
      'DetectionBoxes_Recall/AR@100 (medium)': average recall for medium objects
        with 100.
      'DetectionBoxes_Recall/AR@100 (large)': average recall for large objects
        with 100 detections.

      2. per_category_ap: category specific results with keys of the form:
      'Precision mAP ByCategory/category' (without the supercategory part if
      no supercategories exist). For backward compatibility
      'PerformanceByCategory' is included in the output regardless of
      all_metrics_per_category.
    """
    groundtruth_dict = {
        'annotations': self._groundtruth_list,
        'images': [{'id': image_id} for image_id in self._image_ids],
        'categories': self._categories
    }
    coco_wrapped_groundtruth = coco_tools.COCOWrapper(groundtruth_dict)
    coco_wrapped_detections = coco_wrapped_groundtruth.LoadAnnotations(
        self._detection_boxes_list)
    box_evaluator = coco_tools.COCOEvalWrapper(
        coco_wrapped_groundtruth, coco_wrapped_detections, agnostic_mode=False)
    box_metrics, box_per_category_ap = box_evaluator.ComputeMetrics(
        all_metrics_per_category=self._all_metrics_per_category)
    box_metrics.update(box_per_category_ap)
    box_metrics = {'DetectionBoxes_'+ key: value
                   for key, value in box_metrics.iteritems()}
    return box_metrics

  def get_estimator_eval_metric_ops(self, image_id, groundtruth_boxes,
                                    groundtruth_classes, detection_boxes,
                                    detection_scores, detection_classes):
    """Returns a dictionary of eval metric ops to use with `tf.EstimatorSpec`.

    Note that once value_op is called, the detections and groundtruth added via
    update_op are cleared.

    Args:
      image_id: Unique string/integer identifier for the image.
      groundtruth_boxes: float32 tensor of shape [num_boxes, 4] containing
        `num_boxes` groundtruth boxes of the format
        [ymin, xmin, ymax, xmax] in absolute image coordinates.
      groundtruth_classes: int32 tensor of shape [num_boxes] containing
        1-indexed groundtruth classes for the boxes.
      detection_boxes: float32 tensor of shape [num_boxes, 4] containing
        `num_boxes` detection boxes of the format [ymin, xmin, ymax, xmax]
        in absolute image coordinates.
      detection_scores: float32 tensor of shape [num_boxes] containing
        detection scores for the boxes.
      detection_classes: int32 tensor of shape [num_boxes] containing
        1-indexed detection classes for the boxes.

    Returns:
      a dictionary of metric names to tuple of value_op and update_op that can
      be used as eval metric ops in tf.EstimatorSpec. Note that all update ops
      must be run together and similarly all value ops must be run together to
      guarantee correct behaviour.
    """
    def update_op(
        image_id,
        groundtruth_boxes,
        groundtruth_classes,
        detection_boxes,
        detection_scores,
        detection_classes):
      self.add_single_ground_truth_image_info(
          image_id,
          {'groundtruth_boxes': groundtruth_boxes,
           'groundtruth_classes': groundtruth_classes})
      self.add_single_detected_image_info(
          image_id,
          {'detection_boxes': detection_boxes,
           'detection_scores': detection_scores,
           'detection_classes': detection_classes})

    update_op = tf.py_func(update_op, [image_id,
                                       groundtruth_boxes,
                                       groundtruth_classes,
                                       detection_boxes,
                                       detection_scores,
                                       detection_classes], [])
    metric_names = ['DetectionBoxes_Precision/mAP',
                    'DetectionBoxes_Precision/mAP@.50IOU',
                    'DetectionBoxes_Precision/mAP@.75IOU',
                    'DetectionBoxes_Precision/mAP (large)',
                    'DetectionBoxes_Precision/mAP (medium)',
                    'DetectionBoxes_Precision/mAP (small)',
                    'DetectionBoxes_Recall/AR@1',
                    'DetectionBoxes_Recall/AR@10',
                    'DetectionBoxes_Recall/AR@100',
                    'DetectionBoxes_Recall/AR@100 (large)',
                    'DetectionBoxes_Recall/AR@100 (medium)',
                    'DetectionBoxes_Recall/AR@100 (small)']
    for category_dict in self._categories:
      metric_names.append('DetectionBoxes_PerformanceByCategory/mAP/' +
                          category_dict['name'])

    def first_value_func():
      self._metrics = self.evaluate()
      self.clear()
      return np.float32(self._metrics[metric_names[0]])

    def value_func_factory(metric_name):
      def value_func():
        return np.float32(self._metrics[metric_name])
      return value_func

    first_value_op = tf.py_func(first_value_func, [], tf.float32)
    eval_metric_ops = {metric_names[0]: (first_value_op, update_op)}
    with tf.control_dependencies([first_value_op]):
      for metric_name in metric_names[1:]:
        eval_metric_ops[metric_name] = (tf.py_func(
            value_func_factory(metric_name), [], np.float32), update_op)
    return eval_metric_ops


def _check_mask_type_and_value(array_name, masks):
  """Checks whether mask dtype is uint8 anf the values are either 0 or 1."""
  if masks.dtype != np.uint8:
    raise ValueError('{} must be of type np.uint8. Found {}.'.format(
        array_name, masks.dtype))
  if np.any(np.logical_and(masks != 0, masks != 1)):
    raise ValueError('{} elements can only be either 0 or 1.'.format(
        array_name))


class CocoMaskEvaluator(object_detection_evaluation.DetectionEvaluator):
  """Class to evaluate COCO detection metrics."""

  def __init__(self, categories):
    """Constructor.

    Args:
      categories: A list of dicts, each of which has the following keys -
        'id': (required) an integer id uniquely identifying this category.
        'name': (required) string representing category name e.g., 'cat', 'dog'.
    """
    super(CocoMaskEvaluator, self).__init__(categories)
    self._image_id_to_mask_shape_map = {}
    self._image_ids_with_detections = set([])
    self._groundtruth_list = []
    self._detection_masks_list = []
    self._category_id_set = set([cat['id'] for cat in self._categories])
    self._annotation_id = 1

  def clear(self):
    """Clears the state to prepare for a fresh evaluation."""
    self._image_id_to_mask_shape_map.clear()
    self._image_ids_with_detections.clear()
    self._groundtruth_list = []
    self._detection_masks_list = []

  def add_single_ground_truth_image_info(self,
                                         image_id,
                                         groundtruth_dict):
    """Adds groundtruth for a single image to be used for evaluation.

    Args:
      image_id: A unique string/integer identifier for the image.
      groundtruth_dict: A dictionary containing -
        InputDataFields.groundtruth_boxes: float32 numpy array of shape
          [num_boxes, 4] containing `num_boxes` groundtruth boxes of the format
          [ymin, xmin, ymax, xmax] in absolute image coordinates.
        InputDataFields.groundtruth_classes: integer numpy array of shape
          [num_boxes] containing 1-indexed groundtruth classes for the boxes.
        InputDataFields.groundtruth_instance_masks: uint8 numpy array of shape
          [num_boxes, image_height, image_width] containing groundtruth masks
          corresponding to the boxes. The elements of the array must be in
          {0, 1}.
    """
    if image_id in self._image_id_to_mask_shape_map:
      tf.logging.warning('Ignoring ground truth with image id %s since it was '
                         'previously added', image_id)
      return

    groundtruth_instance_masks = groundtruth_dict[
        standard_fields.InputDataFields.groundtruth_instance_masks]
    _check_mask_type_and_value(standard_fields.InputDataFields.
                               groundtruth_instance_masks,
                               groundtruth_instance_masks)
    self._groundtruth_list.extend(
        coco_tools.
        ExportSingleImageGroundtruthToCoco(
            image_id=image_id,
            next_annotation_id=self._annotation_id,
            category_id_set=self._category_id_set,
            groundtruth_boxes=groundtruth_dict[standard_fields.InputDataFields.
                                               groundtruth_boxes],
            groundtruth_classes=groundtruth_dict[standard_fields.
                                                 InputDataFields.
                                                 groundtruth_classes],
            groundtruth_masks=groundtruth_instance_masks))
    self._annotation_id += groundtruth_dict[standard_fields.InputDataFields.
                                            groundtruth_boxes].shape[0]
    self._image_id_to_mask_shape_map[image_id] = groundtruth_dict[
        standard_fields.InputDataFields.groundtruth_instance_masks].shape

  def add_single_detected_image_info(self,
                                     image_id,
                                     detections_dict):
    """Adds detections for a single image to be used for evaluation.

    Args:
      image_id: A unique string/integer identifier for the image.
      detections_dict: A dictionary containing -
        DetectionResultFields.detection_scores: float32 numpy array of shape
          [num_boxes] containing detection scores for the boxes.
        DetectionResultFields.detection_classes: integer numpy array of shape
          [num_boxes] containing 1-indexed detection classes for the boxes.
        DetectionResultFields.detection_masks: optional uint8 numpy array of
          shape [num_boxes, image_height, image_width] containing instance
          masks corresponding to the boxes. The elements of the array must be
          in {0, 1}.

    Raises:
      ValueError: If groundtruth for the image_id is not available or if
        spatial shapes of groundtruth_instance_masks and detection_masks are
        incompatible.
    """
    if image_id not in self._image_id_to_mask_shape_map:
      raise ValueError('Missing groundtruth for image id: {}'.format(image_id))

    if image_id in self._image_ids_with_detections:
      tf.logging.warning('Ignoring detection with image id %s since it was '
                         'previously added', image_id)
      return

    groundtruth_masks_shape = self._image_id_to_mask_shape_map[image_id]
    detection_masks = detections_dict[standard_fields.DetectionResultFields.
                                      detection_masks]
    if groundtruth_masks_shape[1:] != detection_masks.shape[1:]:
      raise ValueError('Spatial shape of groundtruth masks and detection masks '
                       'are incompatible: {} vs {}'.format(
                           groundtruth_masks_shape,
                           detection_masks.shape))
    _check_mask_type_and_value(standard_fields.DetectionResultFields.
                               detection_masks,
                               detection_masks)
    self._detection_masks_list.extend(
        coco_tools.ExportSingleImageDetectionMasksToCoco(
            image_id=image_id,
            category_id_set=self._category_id_set,
            detection_masks=detection_masks,
            detection_scores=detections_dict[standard_fields.
                                             DetectionResultFields.
                                             detection_scores],
            detection_classes=detections_dict[standard_fields.
                                              DetectionResultFields.
                                              detection_classes]))
    self._image_ids_with_detections.update([image_id])

  def evaluate(self):
    """Evaluates the detection masks and returns a dictionary of coco metrics.

    Returns:
      A dictionary holding -

      1. summary_metrics:
      'Precision/mAP': mean average precision over classes averaged over IOU
        thresholds ranging from .5 to .95 with .05 increments
      'Precision/mAP@.50IOU': mean average precision at 50% IOU
      'Precision/mAP@.75IOU': mean average precision at 75% IOU
      'Precision/mAP (small)': mean average precision for small objects
                      (area < 32^2 pixels)
      'Precision/mAP (medium)': mean average precision for medium sized
                      objects (32^2 pixels < area < 96^2 pixels)
      'Precision/mAP (large)': mean average precision for large objects
                      (96^2 pixels < area < 10000^2 pixels)
      'Recall/AR@1': average recall with 1 detection
      'Recall/AR@10': average recall with 10 detections
      'Recall/AR@100': average recall with 100 detections
      'Recall/AR@100 (small)': average recall for small objects with 100
        detections
      'Recall/AR@100 (medium)': average recall for medium objects with 100
        detections
      'Recall/AR@100 (large)': average recall for large objects with 100
        detections

      2. per_category_ap: category specific results with keys of the form:
      'Precision mAP ByCategory/category' (without the supercategory part if
      no supercategories exist). For backward compatibility
      'PerformanceByCategory' is included in the output regardless of
      all_metrics_per_category.
    """
    groundtruth_dict = {
        'annotations': self._groundtruth_list,
        'images': [{'id': image_id, 'height': shape[1], 'width': shape[2]}
                   for image_id, shape in self._image_id_to_mask_shape_map.
                   iteritems()],
        'categories': self._categories
    }
    coco_wrapped_groundtruth = coco_tools.COCOWrapper(
        groundtruth_dict, detection_type='segmentation')
    coco_wrapped_detection_masks = coco_wrapped_groundtruth.LoadAnnotations(
        self._detection_masks_list)
    mask_evaluator = coco_tools.COCOEvalWrapper(
        coco_wrapped_groundtruth, coco_wrapped_detection_masks,
        agnostic_mode=False, iou_type='segm')
    mask_metrics, mask_per_category_ap = mask_evaluator.ComputeMetrics()
    mask_metrics.update(mask_per_category_ap)
    mask_metrics = {'DetectionMasks_'+ key: value
                    for key, value in mask_metrics.iteritems()}
    return mask_metrics

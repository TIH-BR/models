"""Tests for ssd resnet v1 FPN feature extractors."""
import abc
import numpy as np

from object_detection.models import ssd_feature_extractor_test


class SSDResnetFeatureExtractorTestBase(
    ssd_feature_extractor_test.SsdFeatureExtractorTestBase):
  """Helper test class for SSD Resnet v1 FPN feature extractors."""

  @abc.abstractmethod
  def _scope_name(self):
    pass

  def test_extract_features_returns_correct_shapes_256(self):
    image_height = 256
    image_width = 256
    depth_multiplier = 1.0
    pad_to_multiple = 1
    expected_feature_map_shape = [(2, 32, 32, 256), (2, 16, 16, 256),
                                  (2, 8, 8, 256), (2, 4, 4, 256),
                                  (2, 2, 2, 256)]
    self.check_extract_features_returns_correct_shape(
        2, image_height, image_width, depth_multiplier, pad_to_multiple,
        expected_feature_map_shape)

  def test_extract_features_returns_correct_shapes_with_dynamic_inputs(self):
    image_height = 256
    image_width = 256
    depth_multiplier = 1.0
    pad_to_multiple = 1
    expected_feature_map_shape = [(2, 32, 32, 256), (2, 16, 16, 256),
                                  (2, 8, 8, 256), (2, 4, 4, 256),
                                  (2, 2, 2, 256)]
    self.check_extract_features_returns_correct_shapes_with_dynamic_inputs(
        2, image_height, image_width, depth_multiplier, pad_to_multiple,
        expected_feature_map_shape)

  def test_extract_features_returns_correct_shapes_with_pad_to_multiple(self):
    image_height = 254
    image_width = 254
    depth_multiplier = 1.0
    pad_to_multiple = 32
    expected_feature_map_shape = [(2, 32, 32, 256), (2, 16, 16, 256),
                                  (2, 8, 8, 256), (2, 4, 4, 256),
                                  (2, 2, 2, 256)]

    self.check_extract_features_returns_correct_shape(
        2, image_height, image_width, depth_multiplier, pad_to_multiple,
        expected_feature_map_shape)

  def test_extract_features_raises_error_with_invalid_image_size(self):
    image_height = 32
    image_width = 32
    depth_multiplier = 1.0
    pad_to_multiple = 1
    self.check_extract_features_raises_error_with_invalid_image_size(
        image_height, image_width, depth_multiplier, pad_to_multiple)

  def test_preprocess_returns_correct_value_range(self):
    image_height = 128
    image_width = 128
    depth_multiplier = 1
    pad_to_multiple = 1
    test_image = np.random.rand(4, image_height, image_width, 3)
    feature_extractor = self._create_feature_extractor(depth_multiplier,
                                                       pad_to_multiple)
    preprocessed_image = feature_extractor.preprocess(test_image)
    self.assertAllClose(preprocessed_image,
                        test_image - [[123.68, 116.779, 103.939]])

  def test_variables_only_created_in_scope(self):
    depth_multiplier = 1
    pad_to_multiple = 1
    self.check_feature_extractor_variables_under_scope(
        depth_multiplier, pad_to_multiple, self._scope_name())

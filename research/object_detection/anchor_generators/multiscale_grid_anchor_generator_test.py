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

"""Tests for anchor_generators.multiscale_grid_anchor_generator_test.py."""
import numpy as np
import tensorflow as tf

from object_detection.anchor_generators import multiscale_grid_anchor_generator as mg
from object_detection.utils import test_case


class MultiscaleGridAnchorGeneratorTest(test_case.TestCase):

  def test_construct_single_anchor(self):
    min_level = 5
    max_level = 5
    anchor_scale = 4.0
    aspect_ratios = [1.0]
    scales_per_octave = 1
    im_height = 64
    im_width = 64
    feature_map_shape_list = [(2, 2)]
    exp_anchor_corners = [[-48, -48, 80, 80],
                          [-48, -16, 80, 112],
                          [-16, -48, 112, 80],
                          [-16, -16, 112, 112]]
    anchor_generator = mg.MultiscaleGridAnchorGenerator(
        min_level, max_level, anchor_scale, aspect_ratios, scales_per_octave)
    anchors = anchor_generator.generate(feature_map_shape_list,
                                        im_height, im_width)
    anchor_corners = anchors.get()

    with self.test_session():
      anchor_corners_out = anchor_corners.eval()
      self.assertAllClose(anchor_corners_out, exp_anchor_corners)

  def test_construct_single_anchor_with_odd_input_dimension(self):

    def graph_fn():
      min_level = 5
      max_level = 5
      anchor_scale = 4.0
      aspect_ratios = [1.0]
      scales_per_octave = 1
      im_height = 65
      im_width = 65
      feature_map_shape_list = [(3, 3)]
      anchor_generator = mg.MultiscaleGridAnchorGenerator(
          min_level, max_level, anchor_scale, aspect_ratios, scales_per_octave)
      anchors = anchor_generator.generate(feature_map_shape_list, im_height,
                                          im_width)
      anchor_corners = anchors.get()
      return (anchor_corners,)
    anchor_corners_out = self.execute(graph_fn, [])
    exp_anchor_corners = [[-64, -64, 64, 64],
                          [-64, -32, 64, 96],
                          [-64, 0, 64, 128],
                          [-32, -64, 96, 64],
                          [-32, -32, 96, 96],
                          [-32, 0, 96, 128],
                          [0, -64, 128, 64],
                          [0, -32, 128, 96],
                          [0, 0, 128, 128]]
    self.assertAllClose(anchor_corners_out, exp_anchor_corners)

  def test_construct_single_anchor_on_two_feature_maps(self):

    def graph_fn():
      min_level = 5
      max_level = 6
      anchor_scale = 4.0
      aspect_ratios = [1.0]
      scales_per_octave = 1
      im_height = 64
      im_width = 64
      feature_map_shape_list = [(2, 2), (1, 1)]
      anchor_generator = mg.MultiscaleGridAnchorGenerator(
          min_level, max_level, anchor_scale, aspect_ratios, scales_per_octave)
      anchors = anchor_generator.generate(feature_map_shape_list, im_height,
                                          im_width)
      anchor_corners = anchors.get()
      return (anchor_corners,)

    anchor_corners_out = self.execute(graph_fn, [])
    exp_anchor_corners = [[-48, -48, 80, 80],
                          [-48, -16, 80, 112],
                          [-16, -48, 112, 80],
                          [-16, -16, 112, 112],
                          [-96, -96, 160, 160]]
    self.assertAllClose(anchor_corners_out, exp_anchor_corners)

  def test_construct_single_anchor_with_two_scales_per_octave(self):

    def graph_fn():
      min_level = 6
      max_level = 6
      anchor_scale = 4.0
      aspect_ratios = [1.0]
      scales_per_octave = 2
      im_height = 64
      im_width = 64
      feature_map_shape_list = [(1, 1), (1, 1)]

      anchor_generator = mg.MultiscaleGridAnchorGenerator(
          min_level, max_level, anchor_scale, aspect_ratios, scales_per_octave)
      anchors = anchor_generator.generate(feature_map_shape_list, im_height,
                                          im_width)
      anchor_corners = anchors.get()
      return (anchor_corners,)
    # There are 4 set of anchors in this configuration. The order is:
    # [[2**0.0 intermediate scale + 1.0 aspect],
    #  [2**0.5 intermediate scale + 1.0 aspect]]
    exp_anchor_corners = [[-96., -96., 160., 160.],
                          [-149.0193, -149.0193, 213.0193, 213.0193]]
    anchor_corners_out = self.execute(graph_fn, [])
    self.assertAllClose(anchor_corners_out, exp_anchor_corners)

  def test_construct_single_anchor_with_two_scales_per_octave_and_aspect(self):
    def graph_fn():
      min_level = 6
      max_level = 6
      anchor_scale = 4.0
      aspect_ratios = [1.0, 2.0]
      scales_per_octave = 2
      im_height = 64
      im_width = 64
      feature_map_shape_list = [(1, 1), (1, 1), (1, 1), (1, 1)]
      anchor_generator = mg.MultiscaleGridAnchorGenerator(
          min_level, max_level, anchor_scale, aspect_ratios, scales_per_octave)
      anchors = anchor_generator.generate(feature_map_shape_list, im_height,
                                          im_width)
      anchor_corners = anchors.get()
      return anchor_corners
    # There are 4 set of anchors in this configuration. The order is:
    # [[2**0.0 intermediate scale + 1.0 aspect],
    #  [2**0.5 intermediate scale + 1.0 aspect],
    #  [2**0.0 intermediate scale + 2.0 aspect],
    #  [2**0.5 intermediate scale + 2.0 aspect]]
    exp_anchor_corners = [[-96., -96., 160., 160.],
                          [-149.0193, -149.0193, 213.0193, 213.0193],
                          [-58.50967, -149.0193, 122.50967, 213.0193],
                          [-96., -224., 160., 288.]]
    anchor_corners_out = self.execute(graph_fn, [])
    self.assertAllClose(anchor_corners_out, exp_anchor_corners)

  def test_construct_single_anchors_on_feature_maps_with_dynamic_shape(self):

    def graph_fn(feature_map1_height, feature_map1_width, feature_map2_height,
                 feature_map2_width):
      min_level = 5
      max_level = 6
      anchor_scale = 4.0
      aspect_ratios = [1.0]
      scales_per_octave = 1
      im_height = 64
      im_width = 64
      feature_map_shape_list = [(feature_map1_height, feature_map1_width),
                                (feature_map2_height, feature_map2_width)]
      anchor_generator = mg.MultiscaleGridAnchorGenerator(
          min_level, max_level, anchor_scale, aspect_ratios, scales_per_octave)
      anchors = anchor_generator.generate(feature_map_shape_list, im_height,
                                          im_width)
      anchor_corners = anchors.get()
      return (anchor_corners,)

    anchor_corners_out = self.execute_cpu(graph_fn, [
        np.array(2, dtype=np.int32),
        np.array(2, dtype=np.int32),
        np.array(1, dtype=np.int32),
        np.array(1, dtype=np.int32)
    ])
    exp_anchor_corners = [[-48, -48, 80, 80],
                          [-48, -16, 80, 112],
                          [-16, -48, 112, 80],
                          [-16, -16, 112, 112],
                          [-96, -96, 160, 160]]
    self.assertAllClose(anchor_corners_out, exp_anchor_corners)


if __name__ == '__main__':
  tf.test.main()

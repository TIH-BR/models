/* Copyright 2020 The TensorFlow Authors. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
==============================================================================*/
#ifndef TENSORFLOW_MODELS_SEQUENCE_PROJECTION_TFLITE_OPS_SEQUENCE_STRING_PROJECTION_H_
#define TENSORFLOW_MODELS_SEQUENCE_PROJECTION_TFLITE_OPS_SEQUENCE_STRING_PROJECTION_H_
#include "tensorflow/lite/kernels/register.h"

namespace tflite {
namespace ops {
namespace custom {

extern const char kSequenceStringProjection[];

TfLiteRegistration* Register_SEQUENCE_STRING_PROJECTION();

extern const char kSequenceStringProjectionV2[];

TfLiteRegistration* Register_SEQUENCE_STRING_PROJECTION_V2();
}  // namespace custom
}  // namespace ops
}  // namespace tflite

#endif  // TENSORFLOW_MODELS_SEQUENCE_PROJECTION_TFLITE_OPS_SEQUENCE_STRING_PROJECTION_H_

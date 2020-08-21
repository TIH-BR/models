# Lint as: python3
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
"""Transformer Encoders.

Includes configurations and factory methods.
"""
from typing import Optional

from absl import logging
import dataclasses
import gin
import tensorflow as tf

from official.modeling import hyperparams
from official.modeling import tf_utils
from official.nlp.modeling import layers
from official.nlp.modeling import networks
from official.nlp.projects.mobilebert import modeling


@dataclasses.dataclass
class BertEncoderConfig(hyperparams.Config):
  """BERT encoder configuration."""
  vocab_size: int = 30522
  hidden_size: int = 768
  num_layers: int = 12
  num_attention_heads: int = 12
  hidden_activation: str = "gelu"
  intermediate_size: int = 3072
  dropout_rate: float = 0.1
  attention_dropout_rate: float = 0.1
  max_position_embeddings: int = 512
  type_vocab_size: int = 2
  initializer_range: float = 0.02
  embedding_size: Optional[int] = None


@dataclasses.dataclass
class MobileBertEncoderConfig(hyperparams.Config):
  """MobileBERT encoder configuration.

  Attributes:
    word_vocab_size: number of words in the vocabulary.
    word_embed_size: word embedding size.
    type_vocab_size: number of word types.
    max_sequence_length: maximum length of input sequence.
    num_blocks: number of transformer block in the encoder model.
    hidden_size: the hidden size for the transformer block.
    num_attention_heads: number of attention heads in the transformer block.
    intermediate_size: the size of the "intermediate" (a.k.a., feed
      forward) layer.
    intermediate_act_fn: the non-linear activation function to apply
      to the output of the intermediate/feed-forward layer.
    hidden_dropout_prob: dropout probability for the hidden layers.
    attention_probs_dropout_prob: dropout probability of the attention
      probabilities.
    intra_bottleneck_size: the size of bottleneck.
    initializer_range: The stddev of the truncated_normal_initializer for
        initializing all weight matrices.
    key_query_shared_bottleneck: whether to share linear transformation for
      keys and queries.
    num_feedforward_networks: number of stacked feed-forward networks.
    normalization_type: the type of normalization_type, only 'no_norm' and
      'layer_norm' are supported. 'no_norm' represents the element-wise linear
      transformation for the student model, as suggested by the original
      MobileBERT paper. 'layer_norm' is used for the teacher model.
    classifier_activation: if using the tanh activation for the final
      representation of the [CLS] token in fine-tuning.
    return_all_layers: if return all layer outputs.
    return_attention_score: if return attention scores for each layer.
  """
  word_vocab_size: int = 30522
  word_embed_size: int = 128
  type_vocab_size: int = 2
  max_sequence_length: int = 512
  num_blocks: int = 24
  hidden_size: int = 512
  num_attention_heads: int = 4
  intermediate_size: int = 4096
  intermediate_act_fn: str = "gelu"
  hidden_dropout_prob: float = 0.1
  attention_probs_dropout_prob: float = 0.1
  intra_bottleneck_size: int = 1024
  initializer_range: float = 0.02
  key_query_shared_bottleneck: bool = False
  num_feedforward_networks: int = 1
  normalization_type: str = "layer_norm"
  classifier_activation: bool = True
  return_all_layers: bool = False
  return_attention_score: bool = False


@dataclasses.dataclass
class EncoderConfig(hyperparams.OneOfConfig):
  """Encoder configuration."""
  type: Optional[str] = "bert"
  bert: BertEncoderConfig = BertEncoderConfig()
  mobilebert: MobileBertEncoderConfig = MobileBertEncoderConfig()


ENCODER_CLS = {
    "bert": networks.TransformerEncoder,
    "mobilebert": modeling.MobileBERTEncoder,
}


@gin.configurable
def build_encoder(config: EncoderConfig,
                  embedding_layer: Optional[layers.OnDeviceEmbedding] = None,
                  encoder_cls=None,
                  bypass_config: bool = False):
  """Instantiate a Transformer encoder network from EncoderConfig.

  Args:
    config: the one-of encoder config, which provides encoder parameters of a
      chosen encoder.
    embedding_layer: an external embedding layer passed to the encoder.
    encoder_cls: an external encoder cls not included in the supported encoders,
      usually used by gin.configurable.
    bypass_config: whether to ignore config instance to create the object with
      `encoder_cls`.

  Returns:
    An encoder instance.
  """
  encoder_type = config.type
  encoder_cfg = config.get()
  encoder_cls = encoder_cls or ENCODER_CLS[encoder_type]
  logging.info("Encoder class: %s to build...", encoder_cls.__name__)
  if bypass_config:
    return encoder_cls()
  if encoder_cls.__name__ == "EncoderScaffold":
    embedding_cfg = dict(
        vocab_size=encoder_cfg.vocab_size,
        type_vocab_size=encoder_cfg.type_vocab_size,
        hidden_size=encoder_cfg.hidden_size,
        max_seq_length=encoder_cfg.max_position_embeddings,
        initializer=tf.keras.initializers.TruncatedNormal(
            stddev=encoder_cfg.initializer_range),
        dropout_rate=encoder_cfg.dropout_rate,
    )
    hidden_cfg = dict(
        num_attention_heads=encoder_cfg.num_attention_heads,
        intermediate_size=encoder_cfg.intermediate_size,
        intermediate_activation=tf_utils.get_activation(
            encoder_cfg.hidden_activation),
        dropout_rate=encoder_cfg.dropout_rate,
        attention_dropout_rate=encoder_cfg.attention_dropout_rate,
        kernel_initializer=tf.keras.initializers.TruncatedNormal(
            stddev=encoder_cfg.initializer_range),
    )
    kwargs = dict(
        embedding_cfg=embedding_cfg,
        hidden_cfg=hidden_cfg,
        num_hidden_instances=encoder_cfg.num_layers,
        pooled_output_dim=encoder_cfg.hidden_size,
        pooler_layer_initializer=tf.keras.initializers.TruncatedNormal(
            stddev=encoder_cfg.initializer_range))
    return encoder_cls(**kwargs)

  if encoder_type == "mobilebert":
    return encoder_cls(
        word_vocab_size=encoder_cfg.word_vocab_size,
        word_embed_size=encoder_cfg.word_embed_size,
        type_vocab_size=encoder_cfg.type_vocab_size,
        max_sequence_length=encoder_cfg.max_sequence_length,
        num_blocks=encoder_cfg.num_blocks,
        hidden_size=encoder_cfg.hidden_size,
        num_attention_heads=encoder_cfg.num_attention_heads,
        intermediate_size=encoder_cfg.intermediate_size,
        intermediate_act_fn=encoder_cfg.intermediate_act_fn,
        hidden_dropout_prob=encoder_cfg.hidden_dropout_prob,
        attention_probs_dropout_prob=encoder_cfg.attention_probs_dropout_prob,
        intra_bottleneck_size=encoder_cfg.intra_bottleneck_size,
        key_query_shared_bottleneck=encoder_cfg.key_query_shared_bottleneck,
        num_feedforward_networks=encoder_cfg.num_feedforward_networks,
        normalization_type=encoder_cfg.normalization_type,
        classifier_activation=encoder_cfg.classifier_activation,
        return_all_layers=encoder_cfg.return_all_layers,
        return_attention_score=encoder_cfg.return_attention_score)

  # Uses the default BERTEncoder configuration schema to create the encoder.
  # If it does not match, please add a switch branch by the encoder type.
  return encoder_cls(
      vocab_size=encoder_cfg.vocab_size,
      hidden_size=encoder_cfg.hidden_size,
      num_layers=encoder_cfg.num_layers,
      num_attention_heads=encoder_cfg.num_attention_heads,
      intermediate_size=encoder_cfg.intermediate_size,
      activation=tf_utils.get_activation(encoder_cfg.hidden_activation),
      dropout_rate=encoder_cfg.dropout_rate,
      attention_dropout_rate=encoder_cfg.attention_dropout_rate,
      max_sequence_length=encoder_cfg.max_position_embeddings,
      type_vocab_size=encoder_cfg.type_vocab_size,
      initializer=tf.keras.initializers.TruncatedNormal(
          stddev=encoder_cfg.initializer_range),
      embedding_width=encoder_cfg.embedding_size,
      embedding_layer=embedding_layer)

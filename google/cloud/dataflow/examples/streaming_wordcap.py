# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A streaming string-capitalization workflow.

Important: streaming pipeline support in Python Dataflow is in development
and is not yet available for use.
"""

from __future__ import absolute_import

import argparse
import logging
import sys

import google.cloud.dataflow as df


def run(argv=sys.argv[1:]):
  """Build and run the pipeline."""

  parser = argparse.ArgumentParser()
  parser.add_argument(
      '--input_topic', dest='input_topic', required=True,
      help='Input PubSub topic of the form "/topics/<PROJECT>/<TOPIC>".')
  parser.add_argument(
      '--output_topic', dest='output_topic', required=True,
      help='Output PubSub topic of the form "/topics/<PROJECT>/<TOPIC>".')
  known_args, pipeline_args = parser.parse_known_args(argv)

  p = df.Pipeline(argv=pipeline_args)

  # Read the text file[pattern] into a PCollection.
  lines = p | df.io.Read(
      'read', df.io.PubSubSource(known_args.input_topic))

  # Capitalize the characters in each line.
  transformed = (lines
                 | (df.Map('capitalize', lambda x: x.upper())))

  # Write to PubSub.
  # pylint: disable=expression-not-assigned
  transformed | df.io.Write(
      'pubsub_write', df.io.PubSubSink(known_args.output_topic))

  p.run()


if __name__ == '__main__':
  logging.getLogger().setLevel(logging.INFO)
  run()

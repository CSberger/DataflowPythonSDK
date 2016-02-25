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

"""Test for the top wikipedia sessions example."""

import collections
import json
import logging
import unittest


import google.cloud.dataflow as df
from google.cloud.dataflow.examples.complete import top_wikipedia_sessions


def contains_in_any_order(value, expected):
  vs = collections.Counter(value)
  es = collections.Counter(expected)
  if vs != es:
    raise ValueError(
        'extra: %s, missing: %s' % (vs - es, es - vs))
  return True


class ComputeTopSessionsTest(unittest.TestCase):

  EDITS = [
      json.dumps({'timestamp': 0.0, 'contributor_username': 'user1'}),
      json.dumps({'timestamp': 0.001, 'contributor_username': 'user1'}),
      json.dumps({'timestamp': 0.002, 'contributor_username': 'user1'}),
      json.dumps({'timestamp': 0.0, 'contributor_username': 'user2'}),
      json.dumps({'timestamp': 0.001, 'contributor_username': 'user2'}),
      json.dumps({'timestamp': 3.601, 'contributor_username': 'user2'}),
      json.dumps({'timestamp': 3.602, 'contributor_username': 'user2'}),
      json.dumps(
          {'timestamp': 2 * 3600.0, 'contributor_username': 'user2'}),
      json.dumps(
          {'timestamp': 35 * 24 * 3.600, 'contributor_username': 'user3'})
  ]

  EXPECTED = [
      'user1 : [0.0, 3600.002) : 3 : [0.0, 2592000.0)',
      'user2 : [0.0, 3603.602) : 4 : [0.0, 2592000.0)',
      'user2 : [7200.0, 10800.0) : 1 : [0.0, 2592000.0)',
      'user3 : [3024.0, 6624.0) : 1 : [0.0, 2592000.0)',
  ]

  def test_compute_top_sessions(self):
    p = df.Pipeline('DirectPipelineRunner')
    edits = p | df.Create('create', self.EDITS)
    result = edits | top_wikipedia_sessions.ComputeTopSessions(1.0)

    result_set = set(result.get())
    logging.info('Computed result: %s', result_set)
    assert contains_in_any_order(result_set, self.EXPECTED)


if __name__ == '__main__':
  unittest.main()
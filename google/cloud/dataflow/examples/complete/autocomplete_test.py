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

"""Test for the wordcount example."""

import collections
import logging
import re
import tempfile
import unittest


import google.cloud.dataflow as df
from google.cloud.dataflow.examples.complete import autocomplete
from google.cloud.dataflow.pvalue import AsIter
from google.cloud.dataflow.utils import options

# TODO(robertwb): Move to testing utilities.


def assert_that(pcoll, matcher):
  """Asserts that the give PCollection satisfies the constraints of the matcher
  in a way that is runnable locally or on a remote service.
  """
  singleton = pcoll.pipeline | df.Create('create_singleton', [None])

  def check_matcher(_, side_value):
    assert matcher(side_value)
    return []
  singleton | df.FlatMap(check_matcher, AsIter(pcoll))


def contains_in_any_order(expected):
  def matcher(value):
    vs = collections.Counter(value)
    es = collections.Counter(expected)
    if vs != es:
      raise ValueError(
          'extra: %s, missing: %s' % (vs - es, es - vs))
    return True
  return matcher


class WordCountTest(unittest.TestCase):

  WORDS = ['this', 'this', 'that', 'to', 'to', 'to']

  def test_top_prefixes(self):
    p = df.Pipeline('DirectPipelineRunner')
    words = p | df.Create('create', self.WORDS)
    result = words | autocomplete.TopPerPrefix('test', 5)
    # values must be hashable for now
    result = result | df.Map(lambda (k, vs): (k, tuple(vs)))
    assert_that(result, contains_in_any_order(
        [
            ('t', ((3, 'to'), (2, 'this'), (1, 'that'))),
            ('to', ((3, 'to'), )),
            ('th', ((2, 'this'), (1, 'that'))),
            ('thi', ((2, 'this'), )),
            ('this', ((2, 'this'), )),
            ('tha', ((1, 'that'), )),
            ('that', ((1, 'that'), )),
        ]))
    p.run()

if __name__ == '__main__':
  unittest.main()

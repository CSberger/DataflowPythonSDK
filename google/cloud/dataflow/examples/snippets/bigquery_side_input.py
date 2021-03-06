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

"""A Dataflow job using a BigQuery source as a side input to a ParDo operation.

The workflow will read a table that has a 'month' field (among others) and will
write the values for the field to a text sink.
"""

import logging

import google.cloud.dataflow as df
from google.cloud.dataflow.utils.options import add_option
from google.cloud.dataflow.utils.options import get_options


def run(options=None):
  p = df.Pipeline(options=get_options(options))

  (p  # pylint: disable=expression-not-assigned
   | df.Create('one element', ['ignored'])
   | df.FlatMap(
       'filter month',
       lambda _, rows: [row['month'] for row in rows],
       df.pvalue.AsIter(
           p | df.io.Read('read table', df.io.BigQuerySource(p.options.input))))
   | df.io.Write('write file', df.io.TextFileSink(p.options.output)))

  # Actually run the pipeline (all operations above are deferred).
  p.run()


if __name__ == '__main__':
  logging.getLogger().setLevel(logging.INFO)
  add_option('--input', dest='input', required=True)
  add_option('--output', dest='output', required=True)
  run()

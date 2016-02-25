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

"""An example workflow that demonstrates filters and other features.

  - Reading and writing data from BigQuery.
  - Manipulating BigQuery rows (as Python dicts) in memory.
  - Global aggregates.
  - Filtering PCollections using both user-specified parameters
    as well as global aggregates computed during pipeline execution.
"""

from __future__ import absolute_import

import logging

import google.cloud.dataflow as df
from google.cloud.dataflow.pvalue import AsSingleton
from google.cloud.dataflow.utils.options import add_option
from google.cloud.dataflow.utils.options import get_options


def filter_cold_days(input_data, month_filter):
  """Workflow computing rows in a specific month with low temperatures.

  Args:
    input_data: a PCollection of dictionaries representing table rows. Each
      dictionary must have the keys ['year', 'month', 'day', and 'mean_temp'].
    month_filter: an int representing the month for which colder-than-average
      days should be returned.

  Returns:
    A PCollection of dictionaries with the same keys described above. Each
      row represents a day in the specified month where temperatures were
      colder than the global mean temperature in the entire dataset.
  """

  # Project to only the desired fields from a complete input row.
  # E.g., SELECT f1, f2, f3, ... FROM InputTable.
  projection_fields = ['year', 'month', 'day', 'mean_temp']
  fields_of_interest = (
      input_data
      | df.Map('projected',
               lambda row: {f: row[f] for f in projection_fields}))

  # Compute the global mean temperature.
  global_mean = AsSingleton(
      fields_of_interest
      | df.Map('extract mean', lambda row: row['mean_temp'])
      | df.combiners.Mean.Globally('global mean'))

  # Filter to the rows representing days in the month of interest
  # in which the mean daily temperature is below the global mean.
  return (
      fields_of_interest
      | df.Filter('desired month', lambda row: row['month'] == month_filter)
      | df.Filter('below mean',
                  lambda row, mean: row['mean_temp'] < mean, global_mean))


def run(options=None):
  """Constructs and runs the example filtering pipeline."""
  p = df.Pipeline(options=get_options(options))

  input_data = p | df.io.Read('input', df.io.BigQuerySource(p.options.input))

  # pylint: disable=expression-not-assigned
  (filter_cold_days(input_data, p.options.month_filter)
   | df.io.Write('save to BQ', df.io.BigQuerySink(
       p.options.output,
       schema='year:INTEGER,month:INTEGER,day:INTEGER,mean_temp:FLOAT',
       create_disposition=df.io.BigQueryDisposition.CREATE_IF_NEEDED,
       write_disposition=df.io.BigQueryDisposition.WRITE_TRUNCATE)))

  # Actually run the pipeline (all operations above are deferred).
  p.run()


add_option(
    '--input', dest='input', help='BigQuery table to read from.',
    default='clouddataflow-readonly:samples.weather_stations')
add_option(
    '--output', dest='output', required=True,
    help='BigQuery table to write to.')
add_option(
    '--month_filter', dest='month_filter', default=7,
    help='Numeric value of month to filter on.')


if __name__ == '__main__':
  logging.getLogger().setLevel(logging.INFO)
  run()
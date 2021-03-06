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

"""Tests for worker logging utilities."""

import json
import logging
import sys
import threading
import unittest

from google.cloud.dataflow.worker import logger


class PerThreadLoggingContextTest(unittest.TestCase):

  def thread_check_attribute(self, name):
    self.assertFalse(hasattr(logger.per_thread_worker_data, name))
    with logger.PerThreadLoggingContext(xyz='thread-value'):
      self.assertEqual(
          getattr(logger.per_thread_worker_data, name), 'thread-value')
    self.assertFalse(hasattr(logger.per_thread_worker_data, name))

  def test_no_positional_args(self):
    with self.assertRaises(ValueError) as exn:
      with logger.PerThreadLoggingContext('something'):
        pass
    self.assertEqual(
        exn.exception.message,
        'PerThreadLoggingContext expects only keyword arguments.')

  def test_per_thread_attribute(self):
    self.assertFalse(hasattr(logger.per_thread_worker_data, 'xyz'))
    with logger.PerThreadLoggingContext(xyz='value'):
      self.assertEqual(logger.per_thread_worker_data.xyz, 'value')
      thread = threading.Thread(
          target=self.thread_check_attribute, args=('xyz',))
      thread.start()
      thread.join()
      self.assertEqual(logger.per_thread_worker_data.xyz, 'value')
    self.assertFalse(hasattr(logger.per_thread_worker_data, 'xyz'))

  def test_set_when_undefined(self):
    self.assertFalse(hasattr(logger.per_thread_worker_data, 'xyz'))
    with logger.PerThreadLoggingContext(xyz='value'):
      self.assertEqual(logger.per_thread_worker_data.xyz, 'value')
    self.assertFalse(hasattr(logger.per_thread_worker_data, 'xyz'))

  def test_set_when_already_defined(self):
    self.assertFalse(hasattr(logger.per_thread_worker_data, 'xyz'))
    with logger.PerThreadLoggingContext(xyz='value'):
      self.assertEqual(logger.per_thread_worker_data.xyz, 'value')
      with logger.PerThreadLoggingContext(xyz='value2'):
        self.assertEqual(logger.per_thread_worker_data.xyz, 'value2')
      self.assertEqual(logger.per_thread_worker_data.xyz, 'value')
    self.assertFalse(hasattr(logger.per_thread_worker_data, 'xyz'))


class JsonLogFormatterTest(unittest.TestCase):

  SAMPLE_RECORD = {
      'created': 123456.789, 'msecs': 789.654321,
      'msg': '%s:%d:%.2f', 'args': ('xyz', 4, 3.14),
      'levelname': 'WARNING',
      'process': 'pid', 'thread': 'tid',
      'name': 'name', 'filename': 'file', 'funcName': 'func',
      'exc_info': None}

  SAMPLE_OUTPUT = {
      'timestamp': {'seconds': 123456, 'nanos': 789654321},
      'severity': 'WARN', 'message': 'xyz:4:3.14', 'thread': 'pid:tid',
      'job': 'jobid', 'worker': 'workerid', 'logger': 'name:file:func'}

  def create_log_record(self, **kwargs):

    class Record(object):

      def __init__(self, **kwargs):
        for k, v in kwargs.iteritems():
          setattr(self, k, v)

    return Record(**kwargs)

  def test_basic_record(self):
    formatter = logger.JsonLogFormatter(job_id='jobid', worker_id='workerid')
    record = self.create_log_record(**self.SAMPLE_RECORD)
    self.assertEqual(json.loads(formatter.format(record)), self.SAMPLE_OUTPUT)

  def test_record_with_per_thread_info(self):
    with logger.PerThreadLoggingContext(
        work_item_id='workitem', stage_name='stage', step_name='step'):
      formatter = logger.JsonLogFormatter(job_id='jobid', worker_id='workerid')
      record = self.create_log_record(**self.SAMPLE_RECORD)
      log_output = json.loads(formatter.format(record))
    expected_output = dict(self.SAMPLE_OUTPUT)
    expected_output.update(
        {'work': 'workitem', 'stage': 'stage', 'step': 'step'})
    self.assertEqual(log_output, expected_output)

  def test_exception_record(self):
    formatter = logger.JsonLogFormatter(job_id='jobid', worker_id='workerid')
    try:
      raise ValueError('Something')
    except ValueError:
      attribs = dict(self.SAMPLE_RECORD)
      attribs.update({'exc_info': sys.exc_info()})
      record = self.create_log_record(**attribs)
    log_output = json.loads(formatter.format(record))
    # Check if exception type, its message, and stack trace information are in.
    exn_output = log_output.pop('exception')
    self.assertNotEqual(exn_output.find('ValueError: Something'), -1)
    self.assertNotEqual(exn_output.find('logger_test.py'), -1)
    self.assertEqual(log_output, self.SAMPLE_OUTPUT)

if __name__ == '__main__':
  logging.getLogger().setLevel(logging.INFO)
  unittest.main()


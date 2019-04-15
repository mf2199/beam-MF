#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Unittest for GCP Bigtable Split testing."""
from __future__ import absolute_import
from __future__ import division

import logging
import sys
import unittest

import mock

from beam_bigtable import BigtableSource
#from apache_beam.io.gcp.bigtableio import _BigTableSource as BigTableSource

# Protect against environments where bigquery library is not available.
# pylint: disable=wrong-import-order, wrong-import-position
try:
  from google.cloud.bigtable import Client
  from google.cloud.bigtable.table import Table
  from google.cloud.bigtable.row_data import PartialRowData
  from google.cloud.bigtable_v2.types import SampleRowKeysResponse
  from google.cloud.bigtable.row_set import RowRange
  from google.cloud.bigtable.row_set import RowSet
except ImportError:
  Client = None
  Table = None

KEYS_1 = [b'beam_key0672496', b'beam_key1582279', b'beam_key22',
          b'beam_key2874203', b'beam_key3475534', b'beam_key4440786',
          b'beam_key51', b'beam_key56', b'beam_key65', b'beam_key7389168',
          b'beam_key8105103', b'beam_key9007992', b'']

SIZE_768M = 805306368

@unittest.skipIf(Table is None, 'GCP Bigtable dependencies are not installed')
@unittest.skipIf(Client is None, 'GCP Bigtable dependencies are not installed')
class BigtableSourceTest(unittest.TestCase):
  def setUp(self):
    self.project_id = 'project_id'
    self.instance_id = 'instance_id'
    self.table_id = 'table_id'

    if not hasattr(self, 'client'):
      self.client = Client(project=self.project_id, admin=True)
      self.instance = self.client.instance(self.instance_id)
      self.table = self.instance.table(self.table_id)

  def sample_row_keys(self):
    for i, key in enumerate(KEYS_1):
      sample_row = SampleRowKeysResponse()
      sample_row.row_key = key
      sample_row.offset_bytes = (i+1)*SIZE_768M
      yield sample_row

  @mock.patch.object(BigtableSource, 'get_sample_row_keys')
  def test_estimate_size(self, mock_my_method):
    mock_my_method.return_value = self.sample_row_keys()
    bigtable = BigtableSource(self.project_id, self.instance_id, self.table_id)
    self.assertEqual(bigtable.estimate_size(), 10468982784)
    self.assertTrue(mock_my_method)

  # Range Tracker
  @mock.patch.object(BigtableSource, 'get_sample_row_keys')
  def test_get_range_tracker(self, mock_my_method):
    mock_my_method.return_value = self.sample_row_keys()
    self.bigtable = BigtableSource(self.project_id, self.instance_id, self.table_id)
    start_position = b'beam_key0672496'
    stop_position = b'beam_key1582279'
    range_tracker = self.bigtable.get_range_tracker(start_position, stop_position)

    self.assertEqual(range_tracker.start_position(), start_position)
    self.assertEqual(range_tracker.stop_position(), stop_position)

  @mock.patch.object(BigtableSource, 'get_sample_row_keys')
  def test_split_four_hundred_bytes(self, mock_my_method):
    mock_my_method.return_value = self.sample_row_keys()
    bigtable = BigtableSource(self.project_id, self.instance_id,
                              self.table_id)
    desired_bundle_size = SIZE_768M
    split = bigtable.split()
    split_list = list(split)
    count = len(split_list)
    size = 10468982784
    count_size = size/desired_bundle_size
    # The split takes the first bundle
    # and last bundle and didn't split it.
    count_size = count_size - 1
    self.assertEqual(count, int(count_size))

  def __read_list(self):
    for i in range(672496, 672500):
      key = 'beam_key'+str(i)
      if sys.version_info < (3, 0):
        key = bytes(key)
      else:
        key = bytes(key, 'utf8')
      yield PartialRowData(key)

  def __read_list_rebalancing(self):
    for i in range(35000, 1214999):
      prefix = 'beam_key'
      key = prefix + "%07d" % i
      if sys.version_info < (3, 0):
        key = bytes(key)
      else:
        key = bytes(key, 'utf8')
      yield PartialRowData(key)

  @mock.patch.object(Table, 'read_rows')
  def test_read(self, mock_read_rows):
    mock_read_rows.return_value = self.__read_list()
    bigtable = BigtableSource(self.project_id, self.instance_id, self.table_id)
    read = list(bigtable.read(bigtable.get_range_tracker(b'', b'')))
    new_read = read
    self.assertEqual(len(new_read), 4)
    for i in read:
      self.assertIsInstance(i, PartialRowData)
      self.assertNotEqual(i.row_key, b'')

  @mock.patch.object(BigtableSource, 'get_sample_row_keys')
  def test_row_set_split(self, mock_sample_row_keys):
    mock_sample_row_keys.return_value = self.sample_row_keys()
    row_set = RowSet()

    row_range1 = RowRange(b'beam_key0672496', b'beam_key1582279')
    row_range2 = RowRange(b'beam_key1582279', b'beam_key22')
    row_range3 = RowRange(b'beam_key22', b'beam_key2874203')
    row_range4 = RowRange(b'beam_key2874203', b'beam_key3475534')
    row_range5 = RowRange(b'beam_key3475534', b'beam_key4440786')
    row_range6 = RowRange(b'beam_key4440786', b'beam_key51')
    row_range7 = RowRange(b'beam_key51', b'beam_key56')
    row_range8 = RowRange(b'beam_key56', b'beam_key65')

    row_set.add_row_range(row_range1)
    row_set.add_row_range(row_range2)
    row_set.add_row_range(row_range3)
    row_set.add_row_range(row_range4)
    row_set.add_row_range(row_range5)
    row_set.add_row_range(row_range5)
    row_set.add_row_range(row_range6)
    row_set.add_row_range(row_range7)
    row_set.add_row_range(row_range8)

    bigtable = BigtableSource(self.project_id, self.instance_id, self.table_id)
    self.assertEqual(len(list(bigtable.split())), 12)

  @mock.patch.object(BigtableSource, 'get_sample_row_keys')
  def test_row_set_overlap_serial(self, mock_sample_row_keys):
    mock_sample_row_keys.return_value = self.sample_row_keys()
    row_set = RowSet()

    row_range1 = RowRange(b'beam_key0672496', b'beam_key1582279')
    row_range2 = RowRange(b'beam_key1582279', b'beam_key22')
    row_range3 = RowRange(b'beam_key22', b'beam_key2874203')
    row_range4 = RowRange(b'beam_key2874203', b'beam_key3475534')
    row_range5 = RowRange(b'beam_key3475534', b'beam_key4440786')
    row_range6 = RowRange(b'beam_key4440786', b'beam_key51')
    row_range7 = RowRange(b'beam_key51', b'beam_key56')
    row_range8 = RowRange(b'beam_key56', b'beam_key65')

    row_set.add_row_range(row_range1)
    row_set.add_row_range(row_range2)
    row_set.add_row_range(row_range3)
    row_set.add_row_range(row_range4)
    row_set.add_row_range(row_range5)
    row_set.add_row_range(row_range5)
    row_set.add_row_range(row_range6)
    row_set.add_row_range(row_range7)
    row_set.add_row_range(row_range8)

    bigtable = BigtableSource(self.project_id, self.instance_id, self.table_id)
    # The code links the ranges into one because they are continuous.
    # But, using the split, we split that one bigger range into the eight
    # bundles.
    self.assertEqual(len(list(bigtable.split())), 12)

  @mock.patch.object(BigtableSource, 'get_sample_row_keys')
  @mock.patch.object(Table, 'read_rows')
  def test_read_small_table(self, mock_read_rows, mock_sample_row_keys):
    def mocking_sample_row_keys():
      sample_row = SampleRowKeysResponse()
      sample_row.row_key = b''
      sample_row.offset_bytes = SIZE_768M
      return [sample_row]

    def mocking_read_rows(): # 12.2 KB
      # beam_key0000000
      # beam_key0000009
      for i in range(0, 10):
        prefix = 'beam_key'
        key = prefix + "%07d" % i
        if sys.version_info < (3, 0):
          key = bytes(key)
        else:
          key = bytes(key, 'utf8')
        yield PartialRowData(key)

    mock_sample_row_keys.return_value = mocking_sample_row_keys()
    mock_read_rows.return_value = mocking_read_rows()
    bigtable = BigtableSource(self.project_id, self.instance_id, self.table_id)

    for split_bundle in bigtable.split():
      range_tracker = bigtable.get_range_tracker(split_bundle.start_position, split_bundle.stop_position)
      read = list(bigtable.read(range_tracker))
      self.assertEqual(len(read), 10)

      for row_item in read:
        self.assertIsInstance(row_item, PartialRowData)

  @mock.patch.object(BigtableSource, 'get_sample_row_keys')
  @mock.patch.object(Table, 'read_rows')
  def test_read_2_gb_table(self, mock_read_rows, mock_sample_row_keys):
    def mocking_sample_row_keys():
      keys = [b'beam_key0952711', b'beam_key2', b'beam_key2797065',
              b'beam_key3518235', b'beam_key41', b'beam_key4730550',
              b'beam_key54', b'beam_key6404724', b'beam_key7123742',
              b'beam_key7683967', b'beam_key83', b'beam_key8892594',
              b'beam_key943', b'']

      for i, key in enumerate(keys):
        sample_row = SampleRowKeysResponse()
        sample_row.row_key = key
        sample_row.offset_bytes = (i+1) * 805306368
        yield sample_row

    def mocking_read_rows(**kwargs): # 12.2 KB
      ranges_dict = {
          '': (0, 1),
          'beam_key0952711': (952711, 952712),
          'beam_key2': (2000000, 2000001),
          'beam_key2797065': (2797065, 2797066),
          'beam_key3518235': (3518235, 3518236),
          'beam_key41': (4100000, 4100001),
          'beam_key4730550': (4730550, 4730551),
          'beam_key54': (5400000, 5400001),
          'beam_key6404724': (6404724, 6404725),
          'beam_key7123742': (7123742, 7123743),
          'beam_key7683967': (7683967, 7683968),
          'beam_key83': (8300000, 8300001),
          'beam_key8892594': (8892594, 8892595),
          'beam_key943': (9430000, 9430001),
      }

      current_range = ranges_dict[kwargs['start_key']]
      for i in range(current_range[0], current_range[1]):
        key = "beam_key%07d" % i
        key = bytes(key) if sys.version_info < (3, 0) else bytes(key, 'utf8')
        yield PartialRowData(key)

    mock_sample_row_keys.return_value = mocking_sample_row_keys()
    mock_read_rows.side_effect = mocking_read_rows

    bigtable = BigtableSource(self.project_id, self.instance_id, self.table_id)
    add = []

    for split_element in bigtable.split():
      range_tracker = bigtable.get_range_tracker(split_element.start_position, split_element.stop_position)
      add.append(len(list(bigtable.read(range_tracker))))

    self.assertEqual(sum(add), 14) # Create One Row for each Bundle in the read_rows method.


if __name__ == '__main__':
  logging.getLogger().setLevel(logging.INFO)
  unittest.main()

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

"""PValue, PCollection: one node of a dataflow graph.

A node of a dataflow processing graph is a PValue. Currently, there is only
one type: PCollection (a potentially very large set of arbitrary values).
Once created, a PValue belongs to a pipeline and has an associated
transform (of type PTransform), which describes how the value will be
produced when the pipeline gets executed.
"""

from __future__ import absolute_import

from google.cloud.dataflow import error
from google.cloud.dataflow import typehints


class PValue(object):
  """Base class for PCollection.

  A PValue has the following main characteristics:
    (1) Belongs to a pipeline. Added during object initialization.
    (2) Has a transform that can compute the value if executed.
    (3) Has a value which is meaningful if the transform was executed.
  """

  def __init__(self, **kwargs):
    """Initializes a PValue with all arguments hidden behind keyword arguments.

    Args:
      **kwargs: keyword arguments.

    Raises:
      ValueError: if the expected keyword arguments (pipeline, transform,
        and optionally tag) are not present.

    The method expects a pipeline and a transform keyword argument. However in
    order to give a signal to users that they should not create these PValues
    directly we obfuscate the arguments.
    """
    if 'pipeline' not in kwargs or 'transform' not in kwargs:
      raise ValueError(
          'Missing required arguments (pipeline and transform): %s'
          % kwargs.keys)
    self.pipeline = kwargs.pop('pipeline')
    # TODO(silviuc): Remove usage of the transform argument from all call sites.
    # It is not used anymore and has been replaced with the producer attribute.
    kwargs.pop('transform')
    self.tag = kwargs.pop('tag', None)
    self.element_type = kwargs.pop('element_type', None)
    if kwargs:
      raise ValueError('Unexpected keyword arguments: %s' % kwargs.keys())
    self.pipeline._add_pvalue(self)
    # The AppliedPTransform instance for the application of the PTransform
    # generating this PValue. The field gets initialized when a transform
    # gets applied.
    self.producer = None

  def __str__(self):
    return '<%s>' % self._str_internal()

  def __repr__(self):
    return '<%s at %s>' % (self._str_internal(), hex(id(self)))

  def _str_internal(self):
    return '%s transform=%s' % (
        self.__class__.__name__,
        self.producer.transform if self.producer else 'n/a')

  def apply(self, *args, **kwargs):
    """Applies a transform or callable to a PValue.

    Args:
      *args: positional arguments.
      **kwargs: keyword arguments.

    The method will insert the pvalue as the next argument following an
    optional first label and a transform/callable object. It will call the
    pipeline.apply() method with this modified argument list.
    """
    if isinstance(args[0], str):
      # TODO(robertwb): Make sure labels are properly passed during
      # ptransform construction and drop this argument.
      args = args[1:]
    arglist = list(args)
    arglist.insert(1, self)
    return self.pipeline.apply(*arglist, **kwargs)

  def __or__(self, ptransform):
    return self.pipeline.apply(ptransform, self)


class PCollection(PValue):
  """A multiple values (potentially huge) container."""

  def __init__(self, **kwargs):
    """Initializes a PCollection. Do not call directly."""
    super(PCollection, self).__init__(**kwargs)

  @property
  def windowing(self):
    if not hasattr(self, '_windowing'):
      self._windowing = self.producer.transform.get_windowing(
          self.producer.inputs)
    return self._windowing

  def _get_un_windowed_value(self, values):
    """Converts an iterable of WindowedValue(s) into underlying values."""
    for v in values:
      yield v.value

  # TODO(silviuc): Remove uses of this method and delete it.
  def _get_values(self):

    def _get_internal(self, runner=None):
      """Materializes a PValue by executing its subtree of transforms."""

      runner = runner or self.pipeline.runner
      if not runner:
        raise error.RunnerError(
            'get() cannot find a runner to execute pipeline.')
      runner.run(self.pipeline, node=self)
      # Internally all values are WindowedValue(s) and we want to return only
      # the underlying value or values depending on the type of the PValue.
      return self._get_un_windowed_value(runner.get_pvalue(self))

    return list(_get_internal(self))


class PBegin(PValue):
  """A pipeline begin marker used as input to create/read transforms.

  The class is used internally to represent inputs to Create and Read
  transforms. This allows us to have transforms that uniformly take PValue(s)
  as inputs.
  """
  pass


class DoOutputsTuple(object):
  """An object grouping the multiple outputs of a ParDo or FlatMap transform."""

  def __init__(self, pipeline, transform, tags, main_tag):
    self._pipeline = pipeline
    self._tags = tags
    self._main_tag = main_tag
    self._transform = transform
    # The ApplyPTransform instance for the application of the multi FlatMap
    # generating this value. The field gets initialized when a transform
    # gets applied.
    self.producer = None
    # Dictionary of PCollections already associated with tags.
    self._pcolls = {}

  def __str__(self):
    return '<%s>' % self._str_internal()

  def __repr__(self):
    return '<%s at %s>' % (self._str_internal(), hex(id(self)))

  def _str_internal(self):
    return '%s main_tag=%s tags=%s transform=%s' % (
        self.__class__.__name__, self._main_tag, self._tags, self._transform)

  def __iter__(self):
    """Iterates over tags returning for each call a (tag, pvalue) pair."""
    if self._main_tag is not None:
      yield self[self._main_tag]
    for tag in self._tags:
      yield self[tag]

  def __getattr__(self, tag):
    return self[tag]

  def __getitem__(self, tag):
    # Accept int tags so that we can look at Partition tags with the
    # same ints that we used in the partition function.
    # TODO(gildea): Consider requiring string-based tags everywhere.
    # This will require a partition function that does not return ints.
    if isinstance(tag, int):
      tag = str(tag)
    if tag == self._main_tag:
      tag = None
    elif self._tags and tag not in self._tags:
      raise ValueError(
          'Tag %s is neither the main tag %s nor any of the side tags %s' % (
              tag, self._main_tag, self._tags))
    # Check if we accessed this tag before.
    if tag in self._pcolls:
      return self._pcolls[tag]
    if tag is not None:
      self._transform.side_output_tags.add(tag)
    pcoll = PCollection(
        pipeline=self._pipeline,
        transform=self._transform,
        tag=tag)
    # Transfer the producer from the DoOutputsTuple to the resulting
    # PCollection.
    pcoll.producer = self.producer
    self._pcolls[tag] = pcoll
    return pcoll

  def _get_values(self):
    return ExplicitDoOutputsTuple(self)


class ExplicitDoOutputsTuple(DoOutputsTuple):
  def __init__(self, deferred):
    super(ExplicitDoOutputsTuple, self).__init__(
        None, None, deferred._tags, deferred._main_tag)
    self._deferred = deferred

  def __getitem__(self, tag):
    pcoll = self._deferred[tag]
    return pcoll._get_un_windowed_value(
        self._deferred._pipeline.runner.get_pvalue(pcoll))


class SideOutputValue(object):
  """An object representing a tagged value.

  ParDo, Map, and FlatMap transforms can emit values on multiple outputs which
  are distinguished by string tags. The DoFn will return plain values
  if it wants to emit on the main output and SideOutputValue objects
  if it wants to emit a value on a specific tagged output.
  """

  def __init__(self, tag, value):
    if not isinstance(tag, basestring):
      raise TypeError(
          'Attempting to create a SideOutputValue with non-string tag %s' % tag)
    self.tag = tag
    self.value = value


class AsSideInput(object):
  """Marker specifying that a PCollection will be used as a side input."""

  @property
  def element_type(self):
    return typehints.Any


class AsSingleton(AsSideInput):
  """Marker specifying that an entire PCollection is to be used as a side input.

  When a PCollection is supplied as a side input to a PTransform, it is
  necessary to indicate whether the entire PCollection should be made available
  as a PTransform side argument (in the form of an iterable), or whether just
  one value should be pulled from the PCollection and supplied as the side
  argument (as an ordinary value).

  Wrapping a PCollection side input argument to a PTransform in this container
  (e.g., data.apply('label', MyPTransform(), AsSingleton(my_side_input) )
  selects the latter behavor.

  (Note: This marker is agnostic to whether the PValue it wraps is a
  PCollection. Although PCollections are the only PValues available now, there
  may be additional PValue types for which AsIter and AsSingleton are useful
  markers.
  """
  _NO_DEFAULT = object()

  def __init__(self, pvalue, default_value = _NO_DEFAULT):
    self.pvalue = pvalue
    self.default_value = default_value

  def __repr__(self):
    return 'AsSingleton(%s)' % self.pvalue

  @property
  def element_type(self):
    return self.pvalue.element_type


class AsIter(AsSideInput):
  """Marker specifying that an entire PCollection is to be used as a side input.

  When a PCollection is supplied as a side input to a PTransform, it is
  necessary to indicate whether the entire PCollection should be made available
  as a PTransform side argument (in the form of an iterable), or whether just
  one value should be pulled from the PCollection and supplied as the side
  argument (as an ordinary value).

  Wrapping a PCollection side input argument to a PTransform in this container
  (e.g., data.apply('label', MyPTransform(), AsIter(my_side_input) ) selects the
  former behavor.

  (Note: This marker is agnostic to whether the PValue it wraps is a
  PCollection. Although PCollection is the only PValue available now, there
  may be additional PValue types for which AsIter and AsSingleton are useful
  markers.
  """

  def __init__(self, pvalue):
    self.pvalue = pvalue

  def __repr__(self):
    return 'AsIter(%s)' % self.pvalue

  @property
  def element_type(self):
    return typehints.Iterable[self.pvalue.element_type]


def AsList(pcoll, label='AsList'):  # pylint: disable=invalid-name
  """Convenience function packaging an entire PCollection as a side input list.

  Intended for use in side-argument specification---the same places where
  AsSingleton and AsIter are used. Unlike those wrapper classes, AsList (as
  implemented) is a function that schedules a Combiner to condense pcoll into a
  single list, then wraps the resulting one-element PCollection in AsSingleton.

  Args:
    pcoll: Input pcollection.
    label: Label to be specified if several AsList's are used in the pipeline at
      same depth level.

  Returns:
    An AsList-wrapper around a PCollection whose one element is a list
    containing all elements in pcoll.
  """
  # Local import is required due to dependency loop; even though the
  # implementation of this function requires concepts defined in modules that
  # depend on pvalue, it lives in this module to reduce user workload.
  # TODO(silviuc): read directly on the worker
  from google.cloud.dataflow.transforms import combiners  # pylint: disable=g-import-not-at-top
  return AsSingleton(pcoll | combiners.ToList(label))


def AsDict(pcoll, label='AsDict'):  # pylint: disable=invalid-name
  """Convenience function packaging an entire PCollection as a side input dict.

  Intended for use in side-argument specification---the same places where
  AsSingleton and AsIter are used. Unlike those wrapper classes, AsDict (as
  implemented) is a function that schedules a Combiner to condense pcoll into a
  single dict, then wraps the resulting one-element PCollection in AsSingleton.

  Args:
    pcoll: Input pcollection. All elements should be key-value pairs (i.e.
       2-tuples) with unique keys.
    label: Label to be specified if several AsDict's are used in the pipeline at
      same depth level.

  Returns:
    An AsDict-wrapper around a PCollection whose one element is a dict with
      entries for uniquely-keyed pairs in pcoll.
  """
  # Local import is required due to dependency loop; even though the
  # implementation of this function requires concepts defined in modules that
  # depend on pvalue, it lives in this module to reduce user workload.
  from google.cloud.dataflow.transforms import combiners  # pylint: disable=g-import-not-at-top
  return AsSingleton(pcoll | combiners.ToDict(label))


class EmptySideInput(object):
  """Value indicating when a singleton side input was empty.

  If a PCollection was furnished as a singleton side input to a PTransform, and
  that PCollection was empty, then this value is supplied to the DoFn in the
  place where a value from a non-empty PCollection would have gone. This alerts
  the DoFn that the side input PCollection was empty. Users may want to check
  whether side input values are EmptySideInput, but they will very likely never
  want to create new instances of this class themselves.
  """
  pass

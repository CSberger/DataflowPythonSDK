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

"""Pipeline options obtained from command line parsing.

TODO(silviuc): Should rename this module to pipeline_options.
"""

import argparse

# Raw (unparsed) options. They are also added by other modules that want to
# contribute modules other than the ones defined in this file. See add_option(),
# below.
OPTIONS = []


class PipelineOptions(object):
  """Pipeline options class used as container for command line options.

  The class is essentially a wrapper over the standard argparse Python module
  (see https://docs.python.org/3/library/argparse.html).  To define one option
  or a group of options you subclass from PipelineOptions:

    class XyzOptions(PipelineOptions):

      @classmethod
      def _add_argparse_args(cls, parser):
        parser.add_argument('--abc', default='start')
        parser.add_argument('--xyz', default='end')

  The arguments for the add_argument() method are exactly the ones
  described in the argparse public documentation.

  Pipeline objects require an options object during initialization.
  This is obtained simply by initializing an options class as defined above:

    p = Pipeline(options=XyzOptions())
    if p.options.xyz == 'end':
      raise ValueError('Option xyz has an invalid value.')

  By default the options classes will use command line arguments to initialize
  the options.
  """

  def __init__(self, flags=None, **kwargs):
    """Initialize an options class.

    The initializer will traverse all subclasses, add all their argparse
    arguments and then parse the command line specified by flags or by default
    the one obtained from sys.argv.

    The subclasses are not expected to require a redefinition of __init__.

    Args:
      flags: An iterable of command line arguments to be used. If not specified
        then sys.argv will be used as input for parsing arguments.

      **kwargs: Add overrides for arguments passed in flags.
    """
    self._flags = flags
    self._all_options = kwargs
    parser = argparse.ArgumentParser()
    for cls in type(self).mro():
      if cls == PipelineOptions:
        break
      elif '_add_argparse_args' in cls.__dict__:
        cls._add_argparse_args(parser)
    # The _visible_options attribute will contain only those options from the
    # flags (i.e., command line) that can be recognized. The _all_options
    # field contains additional overrides.
    self._visible_options, _ = parser.parse_known_args(flags)

  @classmethod
  def _add_argparse_args(cls, parser):
    # Override this in subclasses to provide options.
    pass

  def view_as(self, cls):
    view = cls(self._flags)
    view._all_options = self._all_options
    return view

  def _visible_option_list(self):
    return sorted(option
                  for option in dir(self._visible_options) if option[0] != '_')

  def __dir__(self):
    return sorted(dir(type(self)) + self.__dict__.keys() +
                  self._visible_option_list())

  def __getattr__(self, name):
    if name in self._visible_option_list():
      return self._all_options.get(name, getattr(self._visible_options, name))
    else:
      raise AttributeError("'%s' object has no attribute '%s'" %
                           (type(self).__name__, name))

  def __setattr__(self, name, value):
    if name in ('_flags', '_all_options', '_visible_options'):
      super(PipelineOptions, self).__setattr__(name, value)
    elif name in self._visible_option_list():
      self._all_options[name] = value
    else:
      raise AttributeError("'%s' object has no attribute '%s'" %
                           (type(self).__name__, name))

  def __str__(self):
    return '%s(%s)' % (type(self).__name__,
                       ', '.join('%s=%s' % (option, getattr(self, option))
                                 for option in self._visible_option_list()))


class StandardOptions(PipelineOptions):

  @classmethod
  def _add_argparse_args(cls, parser):
    parser.add_argument(
        '--runner',
        default='DirectPipelineRunner',
        help=('Pipeline runner used to execute the workflow. Valid values are '
              'DirectPipelineRunner, DataflowPipelineRunner, '
              'and BlockingDataflowPipelineRunner.'))
    # Whether this is a streaming job.
    # TODO(ccy): This should be an option on the pipeline runner.
    parser.add_argument('--is_streaming',
                        default=False,
                        help='Whether the job is a streaming job.')


class TypeOptions(PipelineOptions):

  @classmethod
  def _add_argparse_args(cls, parser):
    # TODO(laolu): Add a type inferencing option here once implemented.
    parser.add_argument('--type_check_strictness',
                        default='DEFAULT_TO_ANY',
                        choices=['ALL_REQUIRED', 'DEFAULT_TO_ANY'],
                        help='The level of exhaustive manual type-hint '
                        'annotation required')
    parser.add_argument('--no_pipeline_type_check',
                        dest='pipeline_type_check',
                        action='store_false',
                        help='Disable type checking at pipeline construction '
                        'time')
    parser.add_argument('--pipeline_type_check',
                        action='store_true',
                        help='Enable type checking at pipeline construction '
                        'time')
    parser.add_argument('--runtime_type_check',
                        default=False,
                        action='store_true',
                        help='Enable type checking at pipeline execution '
                        'time. NOTE: only supported with the '
                        'DirectPipelineRunner')


class GoogleCloudOptions(PipelineOptions):

  @classmethod
  def _add_argparse_args(cls, parser):
    parser.add_argument(
        '--dataflow_endpoint',
        default='https://dataflow.googleapis.com',
        help=
        ('The URL for the Dataflow API. If not set, the default public URL '
         'will be used.'))
    # Remote execution must check that this option is not None.
    parser.add_argument('--project',
                        default=None,
                        help='Name of the Cloud project owning the Dataflow '
                        'job.')
    # Remote execution must check that this option is not None.
    parser.add_argument('--job_name',
                        default=None,
                        help='Name of the Cloud Dataflow job.')
    # Remote execution must check that this option is not None.
    parser.add_argument('--staging_location',
                        default=None,
                        help='GCS path for staging code packages needed by '
                        'workers.')
    # Remote execution must check that this option is not None.
    parser.add_argument('--temp_location',
                        default=None,
                        help='GCS path for saving temporary workflow jobs.')
    # Options for using service account credentials.
    parser.add_argument('--service_account_name',
                        default=None,
                        help='Name of the service account for Google APIs.')
    parser.add_argument('--service_account_key_file',
                        default=None,
                        help='Path to a file containing the P12 service '
                        'credentials.')
    parser.add_argument('--no_auth', dest='no_auth', type=bool, default=False)


# Command line options controlling the worker pool configuration.
# TODO(silviuc): Update description when autoscaling options are in.
class WorkerOptions(PipelineOptions):

  @classmethod
  def _add_argparse_args(cls, parser):
    parser.add_argument(
        '--num_workers',
        type=int,
        default=None,
        help=
        ('Number of workers to use when executing the Dataflow job. If not '
         'set, the Dataflow service will use a reasonable default.'))
    parser.add_argument(
        '--machine_type',
        default=None,
        help=('Machine type to create Dataflow worker VMs as. See '
              'https://cloud.google.com/compute/docs/machine-types '
              'for a list of valid options. If not set, '
              'the Dataflow service will choose a reasonable '
              'default.'))
    parser.add_argument(
        '--disk_size_gb',
        type=int,
        default=None,
        help=
        ('Remote worker disk size, in gigabytes, or 0 to use the default size. '
         'If not set, the Dataflow service will use a reasonable default.'))
    parser.add_argument(
        '--disk_type',
        default=None,
        help=('Specifies what type of persistent disk should be used.'))
    parser.add_argument(
        '--disk_source_image',
        default=None,
        help=
        ('Disk source image to use by VMs for jobs. See '
         'https://developers.google.com/compute/docs/images for further '
         'details. If not set, the Dataflow service will use a reasonable '
         'default.'))
    parser.add_argument(
        '--zone',
        default=None,
        help=(
            'GCE availability zone for launching workers. Default is up to the '
            'Dataflow service.'))
    parser.add_argument(
        '--network',
        default=None,
        help=(
            'GCE network for launching workers. Default is up to the Dataflow '
            'service.'))
    parser.add_argument(
        '--teardown_policy',
        choices=['TEARDOWN_ALWAYS', 'TEARDOWN_NEVER', 'TEARDOWN_ON_SUCCESS'],
        default=None,
        help=
        ('The teardown policy for the VMs. By default this is left unset and '
         'the service sets the default policy.'))


class DebugOptions(PipelineOptions):

  @classmethod
  def _add_argparse_args(cls, parser):
    parser.add_argument('--dataflow_job_file',
                        default=None,
                        help='Debug file to write the workflow specification.')


class SetupOptions(PipelineOptions):

  @classmethod
  def _add_argparse_args(cls, parser):
    # Options for installing dependencies in the worker.
    parser.add_argument(
        '--requirements_file',
        default=None,
        help=
        ('Path to a requirements file containing package dependencies. '
         'Typically it is produced by a pip freeze command. More details: '
         'https://pip.pypa.io/en/latest/reference/pip_freeze.html. If '
         'specified, the worker will install the required dependenciesi before'
         ' running any custom code. Typically the file is named '
         'requirements.txt.'))
    parser.add_argument(
        '--setup_file',
        default=None,
        help=
        ('Path to a setup Python file containing package dependencies. If '
         'specified, the file\'s containing folder is assumed to have the '
         'structure required for a setuptools setup package. The file must be '
         'named setup.py. More details: '
         'https://pythonhosted.org/setuptools/setuptools.html During job '
         'submission a source distribution will be built and the worker will '
         'install the resulting package before running any custom code.'))
    parser.add_argument(
        '--save_main_session',
        default=True,
        action='store_true',
        help=
        ('Save the main session state so that pickled functions and classes '
         'defined in __main__ (e.g. interactive session) can be unpickled. '
         'Some workflows do not need the session state if for instance all '
         'their functions/classes are defined in proper modules (not __main__)'
         ' and the modules are importable in the worker. '))
    parser.add_argument('--no_save_main_session',
                        dest='save_main_session',
                        action='store_false')
    parser.add_argument(
        '--sdk_location',
        default='default',
        help=
        ('GCS folder or local directory containing the Dataflow SDK for Python '
         'tar file. Workflow submissions will copy an SDK tarball from here. '
         'If this is a GCS folder, the corresponding SDK version will be added '
         'to the tar file name. Otherwise (used only for testing the SDK), '
         'this is the name of a local directory. If the string "default", '
         'a standard SDK location is used. If empty, no SDK is copied.'))
    parser.add_argument(
        '--extra_package',
        dest='extra_packages',
        action='append',
        default=None,
        help=
        ('Local path to a Python package file. The file is expected to be a '
         'compressed tarball with the suffix \'.tar.gz\' which can be '
         'installed using the easy_install command of the standard setuptools '
         'package. Multiple --extra_package options can be specified if more '
         'than one package is needed. During job submission the files will be '
         'staged in the staging area (--staging_location option) and the '
         'workers will install them in same order they were specified on the '
         'command line.'))

# TODO(silviuc): Add autoscaling related options:
# --autoscaling_algorithm, --max_num_workers.

# TODO(silviuc): Add --files_to_stage option.
# This could potentially replace the --requirements_file and --setup_file.

# TODO(silviuc): Non-standard options. Keep them? If yes, add help too!
# Remote execution must check that this option is not None.


class OptionsContext(object):
  """Set default pipeline options for pipelines created in this block.

  This is particularly useful for pipelines implicitly created with the

      [python list] | PTransform

  construct.

  Can also be used as a decorator.
  """
  overrides = []

  def __init__(self, **options):
    self.options = options

  def __enter__(self):
    self.overrides.append(self.options)

  def __exit__(self, *exn_info):
    self.overrides.pop()

  def __call__(self, f, *args, **kwargs):

    def wrapper(*args, **kwargs):
      with self:
        f(*args, **kwargs)

    return wrapper

  @classmethod
  def augment_options(cls, options):
    for override in cls.overrides:
      for name, value in override.items():
        setattr(options, name, value)
    return options

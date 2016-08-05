# coding=utf-8
# Copyright 2016 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import os
import subprocess
from contextlib import contextmanager

from pants.backend.python.tasks.python_task import PythonTask
from pants.base.exceptions import TaskError
from pants.binaries.binary_util import BinaryUtil
from pants.fs.archive import ZIP
from pants.util.contextutil import environment_as, temporary_dir


class MypyPythonTask(PythonTask):
  """Add additonal steps to OSS PythonCheckStyleTask."""

  _PYTHON_SOURCE_EXTENSION = '.py'

  def __init__(self, *args, **kwargs):
    super(MypyPythonTask, self).__init__(*args, **kwargs)
    self.options = self.get_options()

  @classmethod
  def register_options(cls, register):
    super(MypyPythonTask, cls).register_options(register)
    register('--version', advanced=True, fingerprint=True, default='0.4.3', help='Mypy Version')

  @contextmanager
  def get_mypy_script(self):
    binary_util = BinaryUtil.Factory.create()
    pex_path = binary_util.select_script('scripts/mypy', self.get_options().version, 'mypy')

    yield pex_path

  def execute(self):
    """Run isort on all found source files."""

    # We need to do PEX_IGNORE_RCFILES because /etc/pexrc can override your interpreter version.
    mypy_path = ':'.join(self.get_options().pythonpath)
    with environment_as(
        PEX_IGNORE_RCFILES = '1',
        MYPYPATH=mypy_path,
    ):
      print()
      failures = 0
      # Before running the pex we should check that there is a python3 interpreter on the system.
      # If there isn't we should throw a reasonable error.
      with self.get_mypy_script() as mypy_script:
        for source in self.calculate_sources(self.context.targets()):
          cmd = ['python3', mypy_script, '-s', '--py2', source]
          failures += subprocess.call(cmd)

      if failures != 0:
        raise TaskError()

  def calculate_sources(self, targets):
    """Generate a set of source files from the given targets."""
    sources = set()
    for target in targets:
      sources.update(
        source for source in target.sources_relative_to_buildroot()
        if source.endswith(self._PYTHON_SOURCE_EXTENSION)
      )
    return sources

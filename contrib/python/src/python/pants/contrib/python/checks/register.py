# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

from pants.contrib.python.checks.tasks.checkstyle.checker import PythonCheckStyleTask
from pants.contrib.python.checks.tasks.mypy.mypy_task import MypyPythonTask
from pants.contrib.python.checks.tasks.python_eval import PythonEval
from pants.goal.goal import Goal
from pants.goal.task_registrar import TaskRegistrar as task


def register_goals():
  task(name='python-eval', action=PythonEval).install('compile')
  task(name='pythonstyle', action=PythonCheckStyleTask).install('compile')

  Goal.register('type-check', 'Type checking.')
  task(name='mypy', action=MypyPythonTask).install('type-check')

# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import tokenize

from pants.backend.python.tasks.checkstyle.checker import PythonCheckStyleTask
from pants.backend.python.tasks.checkstyle.common import CheckstylePlugin


# TODO(wickman) Update this to sanitize line continuation styling as we have
# disabled it from pep8.py due to mismatched indentation styles.
class Indentation(CheckstylePlugin):
  """Enforce proper indentation."""
  INDENT_LEVEL = 2  # the one true way

  def nits(self):
    indents = []

    for token in self.python_file.tokens:
      token_type, token_text, token_start = token[0:3]
      if token_type is tokenize.INDENT:
        last_indent = len(indents[-1]) if indents else 0
        current_indent = len(token_text)
        if current_indent - last_indent != self.INDENT_LEVEL:
          yield self.error('T100',
              'Indentation of %d instead of %d' % (current_indent - last_indent, self.INDENT_LEVEL),
              token_start[0])
        indents.append(token_text)
      elif token_type is tokenize.DEDENT:
        indents.pop()

class IndentationCheck(PythonCheckStyleTask):
  def __init__(self, *args, **kwargs):
    super(IndentationCheck, self).__init__(*args, **kwargs)
    self._checker = Indentation
    self._name = 'Indentation'

  @classmethod
  def register_options(cls, register):
    super(IndentationCheck, cls).register_options(register)
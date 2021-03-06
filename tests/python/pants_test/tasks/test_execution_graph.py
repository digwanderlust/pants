# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import unittest

from pants.backend.jvm.tasks.jvm_compile.execution_graph import (ExecutionFailure, ExecutionGraph,
                                                                 Job, JobExistsError,
                                                                 NoRootJobError, UnknownJobError)


class ImmediatelyExecutingPool(object):
  def submit_async_work(self, work):
    work.func(*work.args_tuples[0])


class PrintLogger(object):
  def error(self, msg):
    print(msg)

  def debug(self, msg):
    print(msg)


def passing_fn():
  pass


def raising_fn():
  raise Exception("I'm an error")


class ExecutionGraphTest(unittest.TestCase):
  def setUp(self):
    self.jobs_run = []

  def execute(self, exec_graph):
    exec_graph.execute(ImmediatelyExecutingPool(), PrintLogger())

  def job(self, name, fn, dependencies, on_success=None, on_failure=None):
    def recording_fn():
      self.jobs_run.append(name)
      fn()

    return Job(name, recording_fn, dependencies, on_success, on_failure)

  def test_single_job(self):
    exec_graph = ExecutionGraph([self.job("A", passing_fn, [])])

    self.execute(exec_graph)

    self.assertEqual(self.jobs_run, ["A"])

  def test_single_dependency(self):
    exec_graph = ExecutionGraph([self.job("A", passing_fn, ["B"]),
                                 self.job("B", passing_fn, [])])
    self.execute(exec_graph)

    self.assertEqual(self.jobs_run, ["B", "A"])


  def test_simple_binary_tree(self):
    exec_graph = ExecutionGraph([self.job("A", passing_fn, ["B", "C"]),
                                 self.job("B", passing_fn, []),
                                 self.job("C", passing_fn, [])])
    self.execute(exec_graph)

    self.assertEqual(self.jobs_run, ["B", "C", "A"])

  def test_simple_linear_dependencies(self):
    exec_graph = ExecutionGraph([self.job("A", passing_fn, ["B"]),
                                 self.job("B", passing_fn, ["C"]),
                                 self.job("C", passing_fn, [])])

    self.execute(exec_graph)

    self.assertEqual(self.jobs_run, ["C", "B", "A"])

  def test_simple_unconnected(self):
    exec_graph = ExecutionGraph([self.job("A", passing_fn, []),
                                 self.job("B", passing_fn, []),
    ])

    self.execute(exec_graph)

    self.assertEqual(self.jobs_run, ["A", "B"])

  def test_simple_unconnected_tree(self):
    exec_graph = ExecutionGraph([self.job("A", passing_fn, ["B"]),
                                 self.job("B", passing_fn, []),
                                 self.job("C", passing_fn, []),
    ])

    self.execute(exec_graph)

    self.assertEqual(self.jobs_run, ["B", "C", "A"])


  def test_dependee_depends_on_dependency_of_its_dependency(self):
    exec_graph = ExecutionGraph([self.job("A", passing_fn, ["B", "C"]),
                                 self.job("B", passing_fn, ["C"]),
                                 self.job("C", passing_fn, []),
    ])

    self.execute(exec_graph)

    self.assertEqual(["C", "B", "A"], self.jobs_run)

  def test_one_failure_raises_exception(self):
    exec_graph = ExecutionGraph([self.job("A", raising_fn, [])])
    with self.assertRaises(ExecutionFailure) as cm:
      self.execute(exec_graph)

    self.assertEqual("Failed jobs: A", str(cm.exception))

  def test_failure_of_dependency_does_not_run_dependents(self):
    exec_graph = ExecutionGraph([self.job("A", passing_fn, ["F"]),
                                 self.job("F", raising_fn, [])])
    with self.assertRaises(ExecutionFailure) as cm:
      self.execute(exec_graph)

    self.assertEqual(["F"], self.jobs_run)
    self.assertEqual("Failed jobs: F", str(cm.exception))

  def test_failure_of_dependency_does_not_run_second_order_dependents(self):
    exec_graph = ExecutionGraph([self.job("A", passing_fn, ["B"]),
                                 self.job("B", passing_fn, ["F"]),
                                 self.job("F", raising_fn, [])])
    with self.assertRaises(ExecutionFailure) as cm:
      self.execute(exec_graph)

    self.assertEqual(["F"], self.jobs_run)
    self.assertEqual("Failed jobs: F", str(cm.exception))

  def test_failure_of_one_leg_of_tree_does_not_cancel_other(self):
    # TODO do we want this behavior, or do we want to fail fast on the first failed job?
    exec_graph = ExecutionGraph([self.job("B", passing_fn, []),
                                 self.job("F", raising_fn, ["B"]),
                                 self.job("A", passing_fn, ["B"])])
    with self.assertRaises(ExecutionFailure) as cm:
      self.execute(exec_graph)

    self.assertEqual(["B", "F", "A"], self.jobs_run)
    self.assertEqual("Failed jobs: F", str(cm.exception))

  def test_failure_of_disconnected_job_does_not_cancel_non_dependents(self):
    exec_graph = ExecutionGraph([self.job("A", passing_fn, []),
                                 self.job("F", raising_fn, [])])
    with self.assertRaises(ExecutionFailure):
      self.execute(exec_graph)

    self.assertEqual(["A", "F"], self.jobs_run)

  def test_cycle_in_graph_causes_failure(self):
    with self.assertRaises(NoRootJobError) as cm:
      ExecutionGraph([self.job("A", passing_fn, ["B"]),
                      self.job("B", passing_fn, ["A"])])

    self.assertEqual(
      "Unexecutable graph: All scheduled jobs have dependencies. "
      "There must be a circular dependency.",
      str(cm.exception))

  def test_non_existent_dependency_causes_failure(self):
    with self.assertRaises(UnknownJobError) as cm:
      ExecutionGraph([self.job("A", passing_fn, []),
                      self.job("B", passing_fn, ["Z"])])

    self.assertEqual("Unexecutable graph: Undefined dependencies u'Z'", str(cm.exception))

  def test_on_success_callback_raises_error(self):
    exec_graph = ExecutionGraph([self.job("A", passing_fn, [], on_success=raising_fn)])

    with self.assertRaises(ExecutionFailure) as cm:
      self.execute(exec_graph)

    self.assertEqual("Error in on_success for A: I'm an error", str(cm.exception))

  def test_on_failure_callback_raises_error(self):
    exec_graph = ExecutionGraph([self.job("A", raising_fn, [], on_failure=raising_fn)])

    with self.assertRaises(ExecutionFailure) as cm:
      self.execute(exec_graph)

    self.assertEqual("Error in on_failure for A: I'm an error", str(cm.exception))


  def test_same_key_scheduled_twice_is_error(self):
    with self.assertRaises(JobExistsError) as cm:
      ExecutionGraph([self.job("Same", passing_fn, []),
                      self.job("Same", passing_fn, [])])

    self.assertEqual("Unexecutable graph: Job already scheduled u'Same'", str(cm.exception))

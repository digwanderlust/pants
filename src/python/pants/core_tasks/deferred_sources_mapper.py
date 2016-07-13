# coding=utf-8
# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import logging
import os

from pants.base.build_environment import get_buildroot
from pants.base.deprecated import warn_or_error
from pants.base.exceptions import TargetDefinitionException
from pants.build_graph.address import Address
from pants.build_graph.address_lookup_error import AddressLookupError
from pants.build_graph.from_target import from_target_deprecation_hint
from pants.build_graph.remote_sources import RemoteSources
from pants.source.payload_fields import DeferredSourcesField
from pants.source.wrapped_globs import Files
from pants.task.task import Task


logger = logging.getLogger(__name__)


class DeferredSourcesMapper(Task):
  """Map DeferredSourcesFields to files that produce the product 'unpacked_archives'.

  If you want a task to be able to map sources like this, make it require the 'deferred_sources'
  product.
  """

  class SourcesTargetLookupError(AddressLookupError):
    """Raised when the referenced target cannot be found in the build graph"""
    pass

  class NoUnpackedSourcesError(AddressLookupError):
    """Raised when there are no files found unpacked from the archive"""
    pass

  @classmethod
  def product_types(cls):
    """
    Declare product produced by this task

    deferred_sources does not have any data associated with it. Downstream tasks can
    depend on it just make sure that this task completes first.
    :return:
    """
    return ['deferred_sources']

  @classmethod
  def prepare(cls, options, round_manager):
    round_manager.require_data('unpacked_archives')

  @classmethod
  def register_options(cls, register):
    register('--allow-from-target', default=True, type=bool,
             help='Allows usage of `from_target` in BUILD files. If false, usages of `from_target` '
                  'will cause errors to be thrown. This will allow individual repositories to '
                  'disable the use of `from_target` in advance of its deprecation.')

  def map_deferred_sources(self):
    """Inject sources into targets that set their sources to from_target() objects."""
    deferred_sources_fields = []
    def find_deferred_sources_fields(target):
      for name, payload_field in target.payload.fields:
        if isinstance(payload_field, DeferredSourcesField):
          if not self.get_options().allow_from_target:
            raise TargetDefinitionException(target, from_target_deprecation_hint)
          warn_or_error(
              removal_version='1.3.0',
              deprecated_entity_description='DeferredSourcesField',
              hint=from_target_deprecation_hint,
          )
          deferred_sources_fields.append((target, name, payload_field))
    addresses = [target.address for target in self.context.targets()]
    self.context.build_graph.walk_transitive_dependency_graph(addresses,
                                                              find_deferred_sources_fields)

    unpacked_sources = self.context.products.get_data('unpacked_archives')
    for (target, name, payload_field) in deferred_sources_fields:
      sources_target = self.context.build_graph.get_target(payload_field.address)
      if not sources_target:
        raise self.SourcesTargetLookupError(
          "Couldn't find {sources_spec} referenced from {target} field {name} in build graph"
          .format(sources_spec=payload_field.address.spec, target=target.address.spec, name=name))
      if not sources_target in unpacked_sources:
        raise self.NoUnpackedSourcesError(
          "Target {sources_spec} referenced from {target} field {name} did not unpack any sources"
          .format(spec=sources_target.address.spec, target=target.address.spec, name=name))
      sources, rel_unpack_dir = unpacked_sources[sources_target]
      # We have no idea if rel_unpack_dir matches any of our source root patterns, so
      # we explicitly register it here.
      self.context.source_roots.add_source_root(rel_unpack_dir)
      payload_field.populate(sources, rel_unpack_dir)

  def process_remote_sources(self):
    """Create synthetic targets with populated sources from remote_sources targets."""
    unpacked_sources = self.context.products.get_data('unpacked_archives')
    remote_sources_targets = self.context.targets(predicate=lambda t: isinstance(t, RemoteSources))
    for target in remote_sources_targets:
      sources, rel_unpack_dir = unpacked_sources[target.sources_target]
      synthetic_target = self.context.add_new_target(
        address=Address(os.path.relpath(self.workdir, get_buildroot()), target.id),
        target_type=target.destination_target_type,
        dependencies=target.dependencies,
        sources=Files.create_fileset_with_spec(rel_unpack_dir, *sources),
        derived_from=target,
        **target.destination_target_args
      )
      for dependent in self.context.build_graph.dependents_of(target.address):
        self.context.build_graph.inject_dependency(dependent, synthetic_target.address)

  def execute(self):
    self.map_deferred_sources()
    self.process_remote_sources()

# mypy: ignore-errors

from __future__ import annotations

import importlib

import dagster as dg
import pytest
from kedro.framework.project import pipelines
from kedro.framework.session import KedroSession
from kedro.framework.startup import bootstrap_project
from kedro.pipeline import Pipeline
from kedro.pipeline.node import Node

from kedro_dagster.catalog import CatalogTranslator
from kedro_dagster.nodes import NodeTranslator
from kedro_dagster.utils import format_node_name, is_nothing_asset_name, unformat_asset_name


def _get_node_producing_output(pipeline: Pipeline, dataset_name: str) -> Node:
    for n in pipeline.nodes:
        if dataset_name in n.outputs:
            return n
    raise AssertionError(f"No node produces dataset '{dataset_name}' in pipeline")


class TestNodeTranslatorOps:
    """Tests for basic op creation and resource wiring."""

    @pytest.mark.parametrize("env", ["base", "local"])
    def test_create_op_wires_resources(self, env, request):
        """Ensure create_op wires required IO-manager resources for file-backed datasets."""
        options = request.getfixturevalue(f"kedro_project_exec_filebacked_{env}")
        project_path = options.project_path
        package_name = options.package_name

        bootstrap_project(project_path)
        session = KedroSession.create(project_path=project_path, env=env)
        context = session.load_context()

        project_module = importlib.import_module("kedro.framework.project")
        project_module.configure_project(package_name)

        pipeline = project_module.pipelines.get("__default__")

        catalog_translator = CatalogTranslator(
            catalog=context.catalog,
            pipelines=[pipeline],
            hook_manager=context._hook_manager,
            env=env,
        )
        named_io_managers, asset_partitions = catalog_translator.to_dagster()

        node_translator = NodeTranslator(
            pipelines=[pipeline],
            catalog=context.catalog,
            hook_manager=context._hook_manager,
            asset_partitions=asset_partitions,
            named_resources=named_io_managers,
            env=env,
            run_id=session.session_id,
        )

        node = _get_node_producing_output(pipeline, "output2_ds")
        op = node_translator.create_op(node)
        assert isinstance(op, dg.OpDefinition)

        assert f"{env}__output2_ds_io_manager" in op.required_resource_keys

    @pytest.mark.parametrize("env", ["base", "local"])
    def test_partition_tags_and_name_suffix(self, env, request):
        """Ensure op name suffix and tags include provided partition keys."""
        options = request.getfixturevalue(f"kedro_project_exec_filebacked_output2_memory_{env}")
        project_path = options.project_path
        package_name = options.package_name

        bootstrap_project(project_path)
        session = KedroSession.create(project_path=project_path, env=env)
        context = session.load_context()

        project_module = importlib.import_module("kedro.framework.project")
        project_module.configure_project(package_name)

        pipeline = project_module.pipelines.get("__default__")

        node_translator = NodeTranslator(
            pipelines=[pipeline],
            catalog=context.catalog,
            hook_manager=context._hook_manager,
            asset_partitions={},
            named_resources={},
            env=env,
            run_id=session.session_id,
        )

        node = _get_node_producing_output(pipeline, "output2_ds")
        partition_keys = {
            "upstream_partition_key": "input_ds|a",
            "downstream_partition_key": "output2_ds|a",
        }
        op = node_translator.create_op(node, partition_keys=partition_keys)

        assert "__a" in op.name
        assert op.tags.get("upstream_partition_key") == "input_ds|a"
        assert op.tags.get("downstream_partition_key") == "output2_ds|a"

    @pytest.mark.parametrize("env", ["base", "local"])
    def test_handles_no_output_node(self, env, request):
        """Create an op for a no-output node without an asset and only the after-hook output."""
        options = request.getfixturevalue(f"kedro_project_no_outputs_node_{env}")
        project_path = options.project_path
        package_name = options.package_name

        bootstrap_project(project_path)
        session = KedroSession.create(project_path=project_path, env=env)
        context = session.load_context()

        project_module = importlib.import_module("kedro.framework.project")
        project_module.configure_project(package_name)

        pipeline = project_module.pipelines.get("__default__")

        catalog_translator = CatalogTranslator(
            catalog=context.catalog,
            pipelines=[pipeline],
            hook_manager=context._hook_manager,
            env=env,
        )
        named_io_managers, asset_partitions = catalog_translator.to_dagster()

        node_translator = NodeTranslator(
            pipelines=[pipeline],
            catalog=context.catalog,
            hook_manager=context._hook_manager,
            asset_partitions=asset_partitions,
            named_resources=named_io_managers,
            env=env,
            run_id=session.session_id,
        )

        no_out_node = next((n for n in pipeline.nodes if n.name == "sink"), None)

        named_op_factories, named_assets = node_translator.to_dagster()
        op_key = f"{format_node_name(no_out_node.name)}_graph"
        assert op_key in named_op_factories
        assert format_node_name(no_out_node.name) not in named_assets

        op = node_translator.create_op(no_out_node)
        out_keys = list(op.outs.keys())
        assert len(out_keys) == 1 and out_keys[0].endswith("_after_pipeline_run_hook_input")


class TestNodeTranslatorMultiIO:
    """Tests for nodes with multiple inputs and outputs."""

    @pytest.mark.parametrize(
        "kedro_project_multi_in_out_env",
        [
            ("multiple_inputs", "base"),
            ("multiple_inputs", "local"),
            ("multiple_outputs_tuple", "base"),
            ("multiple_outputs_tuple", "local"),
            ("multiple_outputs_dict", "base"),
            ("multiple_outputs_dict", "local"),
        ],
        indirect=True,
    )
    def test_handles_multiple_inputs_and_outputs(self, kedro_project_multi_in_out_env):
        """Translate nodes with multiple inputs/outputs into a valid Dagster op."""
        options = kedro_project_multi_in_out_env
        project_path = options.project_path
        env = options.env

        bootstrap_project(project_path)
        session = KedroSession.create(project_path=project_path, env=env)
        context = session.load_context()

        pipeline = pipelines.get("__default__")

        catalog_translator = CatalogTranslator(
            catalog=context.catalog,
            pipelines=[pipeline],
            hook_manager=context._hook_manager,
            env=env,
        )
        named_io_managers, asset_partitions = catalog_translator.to_dagster()

        node_translator = NodeTranslator(
            pipelines=[pipeline],
            catalog=context.catalog,
            hook_manager=context._hook_manager,
            asset_partitions=asset_partitions,
            named_resources=named_io_managers,
            env=env,
            run_id=session.session_id,
        )

        node_multi_inputs = next((n for n in pipeline.nodes if len(n.inputs) > 1), None)
        node_multi_outputs = next((n for n in pipeline.nodes if len(n.outputs) > 1), None)

        if node_multi_inputs is not None:
            op = node_translator.create_op(node_multi_inputs)
            assert isinstance(op, dg.OpDefinition)
            assert set(op.ins.keys()) == {"a_cleaned", "b_cleaned"}
            assert set(op.outs.keys()) == {"sum", "add_ab_after_pipeline_run_hook_input"}

        elif node_multi_outputs is not None:
            op = node_translator.create_op(node_multi_outputs)
            assert isinstance(op, dg.OpDefinition)

            if node_multi_outputs.name == "split":
                expected_ins = {"input_numbers"}
                expected_outs = {"even_numbers", "odd_numbers", "split_after_pipeline_run_hook_input"}
            elif node_multi_outputs.name == "fanout":
                expected_ins = {"input_value"}
                expected_outs = {"value_copy", "value_double", "fanout_after_pipeline_run_hook_input"}
            else:
                pytest.fail(f"Unexpected multi-output node name: {node_multi_outputs.name}")

            assert set(op.ins.keys()) == expected_ins
            assert set(op.outs.keys()) == expected_outs

        else:
            pytest.fail("No multi-input or multi-output node found in pipeline")


class TestNodeTranslatorNothing:
    """Tests for Nothing dataset handling."""

    @pytest.mark.parametrize("env", ["base", "local"])
    def test_handles_nothing_datasets(self, env, request):
        """Handle Nothing datasets by exposing signaling ins/outs on generated ops."""
        options = request.getfixturevalue(f"kedro_project_nothing_assets_{env}")
        project_path = options.project_path

        bootstrap_project(project_path)
        session = KedroSession.create(project_path=project_path, env=env)
        context = session.load_context()

        pipeline = pipelines.get("__default__")

        catalog_translator = CatalogTranslator(
            catalog=context.catalog,
            pipelines=[pipeline],
            hook_manager=context._hook_manager,
            env=env,
        )
        named_io_managers, asset_partitions = catalog_translator.to_dagster()

        node_translator = NodeTranslator(
            pipelines=[pipeline],
            catalog=context.catalog,
            hook_manager=context._hook_manager,
            asset_partitions=asset_partitions,
            named_resources=named_io_managers,
            env=env,
            run_id=session.session_id,
        )

        def _has_nothing_output(n):
            return any(is_nothing_asset_name(context.catalog, ds) for ds in n.outputs)

        def _has_nothing_input(n):
            return any(is_nothing_asset_name(context.catalog, ds) for ds in n.inputs)

        produce_node = next((n for n in pipeline.nodes if _has_nothing_output(n)), None)
        gated_node = next((n for n in pipeline.nodes if _has_nothing_input(n)), None)

        op_produce = node_translator.create_op(produce_node)
        op_gated = node_translator.create_op(gated_node)

        try:
            datasets_from_catalog = context.catalog.list()
        except AttributeError:
            datasets_from_catalog = context.catalog.filter()
        assert any(is_nothing_asset_name(context.catalog, name) for name in datasets_from_catalog)

        assert any(
            is_nothing_asset_name(context.catalog, unformat_asset_name(asset_name)) for asset_name in op_produce.outs
        )
        assert any(
            is_nothing_asset_name(context.catalog, unformat_asset_name(asset_name)) for asset_name in op_gated.ins
        )

        assert "start_signal" in op_produce.outs
        assert op_produce.outs["start_signal"].dagster_type.is_nothing is True

        assert "start_signal" in op_gated.ins
        assert op_gated.ins["start_signal"].dagster_type.is_nothing is True


class TestNodeTranslatorGroupName:
    """Tests for asset group_name metadata handling."""

    @pytest.mark.parametrize("env", ["base", "local"])
    def test_out_asset_params_includes_group_name(self, env, request):
        """Test that _get_out_asset_params returns group_name when requested."""
        options = request.getfixturevalue(f"kedro_project_group_name_metadata_{env}")
        project_path = options.project_path
        package_name = options.package_name

        bootstrap_project(project_path)
        session = KedroSession.create(project_path=project_path, env=env)
        context = session.load_context()

        project_module = importlib.import_module("kedro.framework.project")
        project_module.configure_project(package_name)

        pipeline = project_module.pipelines.get("__default__")

        catalog_translator = CatalogTranslator(
            catalog=context.catalog,
            pipelines=[pipeline],
            hook_manager=context._hook_manager,
            env=env,
        )
        named_io_managers, asset_partitions = catalog_translator.to_dagster()

        node_translator = NodeTranslator(
            pipelines=[pipeline],
            catalog=context.catalog,
            hook_manager=context._hook_manager,
            asset_partitions=asset_partitions,
            named_resources=named_io_managers,
            env=env,
            run_id=session.session_id,
        )

        node = next(n for n in pipeline.nodes if n.name == "node1")

        out_params = node_translator._get_out_asset_params(
            dataset_name="output_custom_group",
            asset_name="output_custom_group",
            node=node,
            return_group_name=True,
        )

        assert "group_name" in out_params, "group_name should be in params when return_group_name=True"
        assert out_params["group_name"] == "custom_output_group", (
            f"Expected group_name 'custom_output_group', got '{out_params['group_name']}'"
        )

        out_params_no_group = node_translator._get_out_asset_params(
            dataset_name="output_custom_group",
            asset_name="output_custom_group",
            node=node,
            return_group_name=False,
        )

        assert "group_name" not in out_params_no_group, (
            "group_name should not be in params when return_group_name=False"
        )

    @pytest.mark.parametrize("env", ["base", "local"])
    def test_group_name_removed_from_asset_metadata(self, env, request):
        """Test that group_name is removed from metadata dict and not duplicated."""
        options = request.getfixturevalue(f"kedro_project_group_name_metadata_{env}")
        project_path = options.project_path
        package_name = options.package_name

        bootstrap_project(project_path)
        session = KedroSession.create(project_path=project_path, env=env)
        context = session.load_context()

        project_module = importlib.import_module("kedro.framework.project")
        project_module.configure_project(package_name)

        pipeline = project_module.pipelines.get("__default__")

        catalog_translator = CatalogTranslator(
            catalog=context.catalog,
            pipelines=[pipeline],
            hook_manager=context._hook_manager,
            env=env,
        )
        named_io_managers, asset_partitions = catalog_translator.to_dagster()

        node_translator = NodeTranslator(
            pipelines=[pipeline],
            catalog=context.catalog,
            hook_manager=context._hook_manager,
            asset_partitions=asset_partitions,
            named_resources=named_io_managers,
            env=env,
            run_id=session.session_id,
        )

        _, named_assets = node_translator.to_dagster()

        node1_asset = named_assets.get("node1")
        assert node1_asset is not None, f"Asset node1 not found. Available: {list(named_assets.keys())}"

        for spec in node1_asset.specs:
            if "output_custom_group" in spec.key.path:
                if spec.metadata:
                    assert "group_name" not in spec.metadata, (
                        "group_name should be removed from metadata dict and set as attribute"
                    )

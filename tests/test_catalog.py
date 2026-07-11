# mypy: ignore-errors

from __future__ import annotations

import datetime
import importlib
from pathlib import Path
from typing import NewType

import dagster as dg
import pandas as pd
import pytest
import yaml
from kedro.framework.project import pipelines
from kedro.framework.session import KedroSession
from kedro.framework.startup import bootstrap_project
from kedro.io import AbstractDataset, DataCatalog
from kedro.pipeline import Pipeline, node

from kedro_dagster.catalog import CatalogTranslator, _get_dataset_preview_metadata
from kedro_dagster.utils import format_dataset_name, get_dataset_from_catalog

# Local mirrors of Kedro's preview NewType aliases (kedro_datasets._typing). Only
# the annotation name matters for dispatch, so we avoid importing a private module.
TablePreview = NewType("TablePreview", dict)
ImagePreview = NewType("ImagePreview", str)
JSONPreview = NewType("JSONPreview", str)


class PreviewDataset(AbstractDataset):
    """Dataset test double exposing Kedro's preview interface."""

    def __init__(self):
        self._data = None

    def _load(self):
        return self._data

    def _save(self, data):
        self._data = data

    def _describe(self):
        return {}

    def preview(self) -> TablePreview:
        return self._data.head(2).to_dict(orient="split")


class _TypedPreviewDataset(AbstractDataset):
    """Preview test double with a configurable value, type annotation and metadata."""

    _return_type = None

    def __init__(self, value, metadata=None, raise_on_preview=False):
        self._value = value
        self.metadata = metadata
        self._raise_on_preview = raise_on_preview

    def _load(self):
        return self._value

    def _save(self, data):
        self._value = data

    def _describe(self):
        return {}

    def preview(self, **kwargs):
        if self._raise_on_preview:
            raise AssertionError("preview() should not be called when disabled")
        return self._value


class _ImagePreviewDataset(_TypedPreviewDataset):
    def preview(self, **kwargs) -> ImagePreview:
        return super().preview(**kwargs)


class _JSONPreviewDataset(_TypedPreviewDataset):
    def preview(self, **kwargs) -> JSONPreview:
        return super().preview(**kwargs)


class _TablePreviewDataset(_TypedPreviewDataset):
    def preview(self, **kwargs) -> TablePreview:
        return super().preview(**kwargs)


class TestDatasetPreviewMetadata:
    """Unit tests for preview-type dispatch and the large-dataset opt-out."""

    def test_image_preview_renders_as_data_uri(self):
        value = "aGVsbG8="  # base64 payload
        metadata = _get_dataset_preview_metadata(_ImagePreviewDataset(value))
        md = metadata["kedro_dataset_preview"]
        assert isinstance(md, dg.MarkdownMetadataValue)
        assert f"data:image/png;base64,{value}" in md.md_str

    def test_json_preview_is_parsed_into_structured_metadata(self):
        metadata = _get_dataset_preview_metadata(_JSONPreviewDataset('{"a": 1, "b": [2, 3]}'))
        md = metadata["kedro_dataset_preview"]
        assert isinstance(md, dg.JsonMetadataValue)
        assert md.data == {"a": 1, "b": [2, 3]}

    def test_table_preview_coerces_non_serialisable_values(self):
        table = {"columns": ["d"], "data": [[datetime.date(2026, 7, 12)]]}
        metadata = _get_dataset_preview_metadata(_TablePreviewDataset(table))
        md = metadata["kedro_dataset_preview"]
        assert isinstance(md, dg.JsonMetadataValue)
        assert md.data["data"] == [["2026-07-12"]]

    def test_preview_can_be_disabled_via_metadata(self):
        dataset = _ImagePreviewDataset("x", metadata={"kedro-viz": {"preview": False}}, raise_on_preview=True)
        assert _get_dataset_preview_metadata(dataset) == {}

    def test_preview_args_are_forwarded(self):
        captured = {}

        class _Dataset(_TypedPreviewDataset):
            def preview(self, **kwargs) -> TablePreview:
                captured.update(kwargs)
                return {"columns": ["a"], "data": [[1]]}

        dataset = _Dataset({}, metadata={"kedro-viz": {"preview_args": {"nrows": 3}}})
        _get_dataset_preview_metadata(dataset)
        assert captured == {"nrows": 3}


class TestCatalogTranslatorScenarios:
    """Tests for CatalogTranslator across diverse scenarios and dataset types."""

    @pytest.mark.parametrize(
        "env_fixture",
        [
            "kedro_project_exec_filebacked_base",
            "kedro_project_partitioned_intermediate_output2_local",
            "kedro_project_partitioned_static_mapping_base",
            "kedro_project_multiple_inputs_local",
            "kedro_project_multiple_outputs_tuple_base",
            "kedro_project_multiple_outputs_dict_local",
            "kedro_project_no_outputs_node_base",
            "kedro_project_nothing_assets_local",
        ],
    )
    def test_covers_scenarios(self, request, env_fixture):
        """Test CatalogTranslator across diverse scenarios and assert core invariants."""
        options = request.getfixturevalue(env_fixture)
        project_path = options.project_path
        env = options.env

        bootstrap_project(project_path)
        session = KedroSession.create(project_path=project_path, env=env)
        context = session.load_context()

        pipeline = pipelines.get("__default__")
        translator = CatalogTranslator(
            catalog=context.catalog,
            pipelines=[pipeline],
            hook_manager=context._hook_manager,
            env=env,
        )

        named_io_managers, asset_partitions = translator.to_dagster()

        assert isinstance(named_io_managers, dict)
        assert isinstance(asset_partitions, dict)

        with open(project_path / "conf" / env / "catalog.yml", encoding="utf-8") as f:
            options_catalog = yaml.safe_load(f)

        for ds_name, ds_cfg in options_catalog.items():
            ds_type = ds_cfg.get("type")
            asset_name = format_dataset_name(ds_name)
            if ds_type == "pandas.CSVDataset":
                assert f"{env}__{asset_name}_io_manager" in named_io_managers
            elif ds_type == "MemoryDataset":
                assert f"{env}__{asset_name}_io_manager" not in named_io_managers
            elif ds_type == "kedro_dagster.datasets.DagsterPartitionedDataset":
                assert asset_name in asset_partitions
                assert isinstance(asset_partitions[asset_name]["partitions_def"], dg.PartitionsDefinition)
            elif ds_type == "kedro_dagster.datasets.DagsterNothingDataset":
                assert f"{env}__{ds_name}_io_manager" not in named_io_managers


class TestCatalogTranslatorIOManagers:
    """Tests for IO manager creation, configuration, and roundtrip behavior."""

    @pytest.mark.parametrize(
        "kedro_project_scenario_env",
        [("exec_filebacked", "base"), ("exec_filebacked", "local")],
        indirect=True,
    )
    def test_builds_configurable_io_managers(self, kedro_project_scenario_env):
        """Ensure IO managers are created with expected names, types and config."""
        options = kedro_project_scenario_env
        project_path = options.project_path
        package_name = options.package_name
        env = options.env

        bootstrap_project(project_path)
        session = KedroSession.create(project_path=project_path, env=env)
        context = session.load_context()

        project_module = importlib.import_module("kedro.framework.project")
        project_module.configure_project(package_name)

        pipeline = pipelines.get("__default__")
        translator = CatalogTranslator(
            catalog=context.catalog,
            pipelines=[pipeline],
            hook_manager=context._hook_manager,
            env=env,
        )

        named_io_managers, _ = translator.to_dagster()

        with open(project_path / "conf" / env / "catalog.yml", encoding="utf-8") as f:
            options_catalog = yaml.safe_load(f)

        for ds_name, ds_cfg in options_catalog.items():
            ds_type = ds_cfg.get("type")
            if ds_type != "pandas.CSVDataset":
                continue

            asset_name = format_dataset_name(ds_name)
            key = f"{env}__{asset_name}_io_manager"
            assert key in named_io_managers, f"Missing IO manager for {ds_name}"

            io_manager = named_io_managers[key]

            assert hasattr(io_manager, "handle_output") and callable(io_manager.handle_output)
            assert hasattr(io_manager, "load_input") and callable(io_manager.load_input)

            assert getattr(io_manager, "dataset", None) == "CSVDataset"

            if "filepath" in ds_cfg:
                io_fp = getattr(io_manager, "filepath", None)
                rel_fp = ds_cfg["filepath"]
                abs_fp = str((project_path / rel_fp).resolve())
                assert io_fp.replace("\\", "/") in {rel_fp.replace("\\", "/"), abs_fp.replace("\\", "/")}

            assert ds_name in (getattr(io_manager.__class__, "__doc__", "") or "")

    def test_handle_output_attaches_dataset_preview_metadata(self, mocker):
        """Datasets exposing preview() should add preview metadata to Dagster outputs."""

        def make_output():
            return pd.DataFrame({"value": [1, 2, 3]})

        dataset = PreviewDataset()
        catalog = DataCatalog(datasets={"preview_data": dataset})
        pipeline = Pipeline([node(make_output, None, "preview_data", name="make_output")])
        translator = CatalogTranslator(
            catalog=catalog,
            pipelines=[pipeline],
            hook_manager=mocker.Mock(),
            env="base",
        )

        named_io_managers, _ = translator.to_dagster()
        io_manager = named_io_managers["base__preview_data_io_manager"]

        context = mocker.Mock()
        context.op_def.name = "unmapped_op"
        context.op_def.tags = {}
        context.has_asset_partitions = False
        context.has_partition_key = False

        io_manager.handle_output(context, make_output())

        context.add_output_metadata.assert_called_once()
        metadata = context.add_output_metadata.call_args.args[0]
        assert set(metadata) == {"kedro_dataset_preview"}
        assert isinstance(metadata["kedro_dataset_preview"], dg.MetadataValue)

    @pytest.mark.parametrize(
        "kedro_project_scenario_env",
        [("exec_filebacked", "base"), ("exec_filebacked", "local")],
        indirect=True,
    )
    def test_roundtrip_matches_dataset(self, kedro_project_scenario_env):
        """Saving/loading via the IO manager should match the underlying Kedro dataset."""
        options = kedro_project_scenario_env
        project_path = options.project_path
        package_name = options.package_name
        env = options.env

        bootstrap_project(project_path)
        session = KedroSession.create(project_path=project_path, env=env)
        context = session.load_context()

        project_module = importlib.import_module("kedro.framework.project")
        project_module.configure_project(package_name)

        pipeline = pipelines.get("__default__")
        translator = CatalogTranslator(
            catalog=context.catalog,
            pipelines=[pipeline],
            hook_manager=context._hook_manager,
            env=env,
        )
        named_io_managers, _ = translator.to_dagster()

        with open(project_path / "conf" / env / "catalog.yml", encoding="utf-8") as f:
            options_catalog = yaml.safe_load(f)

        @dg.op(name="dummy_node")
        def _noop():
            return None

        op_def = _noop

        df_to_write = pd.DataFrame({"a": [1, 2, 3]})

        for ds_name, ds_cfg in options_catalog.items():
            if ds_cfg.get("type") != "pandas.CSVDataset":
                continue

            asset_name = format_dataset_name(ds_name)
            key = f"{env}__{asset_name}_io_manager"
            assert key in named_io_managers
            io_manager = named_io_managers[key]

            out_ctx = dg.build_output_context(op_def=op_def, name="result")
            io_manager.handle_output(out_ctx, df_to_write)

            dataset = get_dataset_from_catalog(context.catalog, ds_name)
            assert dataset is not None, "Expected dataset to be present in catalog"
            df_via_dataset = dataset.load()

            upstream_out_ctx = dg.build_output_context(op_def=op_def, name="result")
            in_ctx = dg.build_input_context(op_def=op_def, upstream_output=upstream_out_ctx)
            df_via_io_manager = io_manager.load_input(in_ctx)

            assert list(df_via_dataset.columns) == list(df_to_write.columns)
            assert list(df_via_io_manager.columns) == list(df_to_write.columns)
            assert df_via_dataset.equals(df_to_write)
            assert df_via_io_manager.equals(df_to_write)

    @pytest.mark.parametrize(
        "kedro_project_scenario_env",
        [("exec_filebacked", "base"), ("exec_filebacked", "local")],
        indirect=True,
    )
    def test_dataset_config_contains_parameters(self, kedro_project_scenario_env):
        """The dataset config built by CatalogTranslator should reflect dataset._describe()."""
        options = kedro_project_scenario_env
        project_path = options.project_path
        package_name = options.package_name
        env = options.env

        bootstrap_project(project_path)
        session = KedroSession.create(project_path=project_path, env=env)
        context = session.load_context()

        project_module = importlib.import_module("kedro.framework.project")
        project_module.configure_project(package_name)

        pipeline = pipelines.get("__default__")
        translator = CatalogTranslator(
            catalog=context.catalog,
            pipelines=[pipeline],
            hook_manager=context._hook_manager,
            env=env,
        )

        with open(project_path / "conf" / env / "catalog.yml", encoding="utf-8") as f:
            options_catalog = yaml.safe_load(f)

        for ds_name, ds_cfg in options_catalog.items():
            if ds_cfg.get("type") != "pandas.CSVDataset":
                continue
            dataset = get_dataset_from_catalog(context.catalog, ds_name)
            assert dataset is not None, "Expected dataset to be present in catalog"

            cfg_model = translator._create_dataset_config(dataset)
            cfg = cfg_model()

            assert cfg.dataset == dataset.__class__.__name__ == "CSVDataset"

            described = dataset._describe()
            for key, val in described.items():
                if key == "version":
                    continue
                expected = str(val) if hasattr(val, "__fspath__") or "PosixPath" in type(val).__name__ else val
                assert hasattr(cfg, key)
                actual = getattr(cfg, key)
                if hasattr(actual, "model_dump"):
                    actual = actual.model_dump()
                if isinstance(actual, str) and isinstance(expected, str) and ("/" in expected or "\\" in expected):
                    assert Path(actual) == Path(expected)
                else:
                    assert actual == expected


class TestCatalogTranslatorPartitioned:
    """Tests for partitioned dataset IO manager behavior."""

    @pytest.mark.parametrize("env", ["base", "local"])
    def test_respects_partition_keys_via_tags_and_context(self, env, request):
        """Ensure IO manager for DagsterPartitionedDataset handles partition keys from tags and context."""
        options = request.getfixturevalue(f"kedro_project_partitioned_identity_mapping_{env}")
        project_path = options.project_path
        package_name = options.package_name

        bootstrap_project(project_path)
        session = KedroSession.create(project_path=project_path, env=env)
        context = session.load_context()

        project_module = importlib.import_module("kedro.framework.project")
        project_module.configure_project(package_name)

        pipeline = pipelines.get("__default__")
        translator = CatalogTranslator(
            catalog=context.catalog,
            pipelines=[pipeline],
            hook_manager=context._hook_manager,
            env=env,
        )
        named_io_managers, asset_partitions = translator.to_dagster()

        with open(project_path / "conf" / env / "catalog.yml", encoding="utf-8") as f:
            options_catalog = yaml.safe_load(f)

        part_ds_name = next(
            (
                n
                for n, cfg in options_catalog.items()
                if cfg.get("type") == "kedro_dagster.datasets.DagsterPartitionedDataset"
            ),
            None,
        )
        assert part_ds_name is not None, "No DagsterPartitionedDataset configured in this scenario"
        dataset = get_dataset_from_catalog(context.catalog, part_ds_name)
        assert dataset is not None, "Expected partitioned dataset to be present in catalog"
        asset_name = format_dataset_name(part_ds_name)
        io_key = f"{env}__{asset_name}_io_manager"
        assert io_key in named_io_managers
        io_manager = named_io_managers[io_key]

        partitions_def = asset_partitions[asset_name]["partitions_def"]
        keys = partitions_def.get_partition_keys()
        assert len(keys) >= 2  # noqa: PLR2004
        k1, k2 = keys[0], keys[1]

        df1 = {k1: pd.DataFrame({"v": [1]})}
        df2 = {k2: pd.DataFrame({"v": [2]})}

        @dg.op(name="dummy_out", tags={"downstream_partition_key": f"{asset_name}|{k1}"})
        def _out():
            return None

        out_ctx = dg.build_output_context(op_def=_out, name="result")
        io_manager.handle_output(out_ctx, df1)

        loaded_map = dataset.load()
        assert k1 in loaded_map
        df1_loaded = loaded_map[k1]() if callable(loaded_map[k1]) else loaded_map[k1]
        assert isinstance(df1_loaded, pd.DataFrame)
        assert df1_loaded.equals(df1[k1])

        @dg.op(name="dummy_in", tags={"upstream_partition_key": f"{asset_name}|{k1}"})
        def _in():
            return None

        upstream_out_ctx = dg.build_output_context(op_def=_out, name="result")
        in_ctx_tags = dg.build_input_context(op_def=_in, upstream_output=upstream_out_ctx)
        loaded_via_io_tags = io_manager.load_input(in_ctx_tags)
        df_via_io_tags = loaded_via_io_tags[k1]() if callable(loaded_via_io_tags[k1]) else loaded_via_io_tags[k1]
        assert isinstance(df_via_io_tags, pd.DataFrame)
        assert df_via_io_tags.equals(df1[k1])

        @dg.op(name="dummy_out2", tags={"downstream_partition_key": f"{asset_name}|{k2}"})
        def _out2():
            return None

        out_ctx_k2 = dg.build_output_context(op_def=_out2, name="result")
        io_manager.handle_output(out_ctx_k2, df2)

        upstream_out_ctx2 = dg.build_output_context(op_def=_out2, name="result")

        @dg.op(name="dummy_in_ctx")
        def _in_ctx():
            return None

        in_ctx_ctx = dg.build_input_context(
            op_def=_in_ctx,
            upstream_output=upstream_out_ctx2,
            partition_key=k2,
            asset_partitions_def=partitions_def,
        )
        loaded_via_io_ctx = io_manager.load_input(in_ctx_ctx)
        df_via_io_ctx = loaded_via_io_ctx[k2]() if callable(loaded_via_io_ctx[k2]) else loaded_via_io_ctx[k2]
        assert isinstance(df_via_io_ctx, pd.DataFrame)
        assert df_via_io_ctx.equals(df2[k2])

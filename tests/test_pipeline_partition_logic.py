# mypy: ignore-errors

from __future__ import annotations

import dagster as dg
import pytest
from kedro.io import DataCatalog, MemoryDataset

from kedro_dagster.pipelines import PipelineTranslator


class DummyContext:
    def __init__(self, catalog: DataCatalog):
        self.catalog = catalog
        self._hook_manager = None


class DummyNode:
    def __init__(self, name: str, inputs: list[str], outputs: list[str]):
        self.name = name
        self.inputs = inputs
        self.outputs = outputs


def _make_translator(catalog: DataCatalog, asset_partitions: dict[str, dict] | None = None) -> PipelineTranslator:
    return PipelineTranslator(
        dagster_config={},
        context=DummyContext(catalog),
        catalog=catalog,
        project_path="/tmp/project",
        env="local",
        run_id="test-session",
        named_assets={},
        asset_partitions=asset_partitions or {},
        named_op_factories={},
        named_resources={},
        named_executors={},
        named_loggers={},
        enable_mlflow=False,
    )


class TestEnumeratePartitionKeys:
    """Tests for PipelineTranslator._enumerate_partition_keys."""

    def test_static_partitions_returns_all_keys(self):
        """Static partitions definition returns all declared keys."""
        catalog = DataCatalog()
        translator = _make_translator(catalog)

        spd = dg.StaticPartitionsDefinition(["2024-01", "2024-02", "2024-03"])
        keys = translator._enumerate_partition_keys(spd)

        assert keys == ["2024-01", "2024-02", "2024-03"]

    def test_none_returns_empty_list(self):
        """None partitions definition returns an empty list."""
        catalog = DataCatalog()
        translator = _make_translator(catalog)

        keys = translator._enumerate_partition_keys(None)

        assert keys == []


class TestGetNodePartitionKeys:
    """Tests for PipelineTranslator._get_node_partition_keys."""

    def test_mixed_outputs_raises_value_error(self):
        """Mixing partitioned and non-partitioned outputs raises ValueError."""
        catalog = DataCatalog(
            datasets={
                "in": MemoryDataset(),
                "out_non_partitioned": MemoryDataset(),
            }
        )
        asset_partitions = {
            "out_partitioned": {
                "partitions_def": dg.StaticPartitionsDefinition(["p1", "p2"]),
            }
        }

        translator = _make_translator(catalog, asset_partitions)
        node = DummyNode(
            name="n1",
            inputs=["in"],
            outputs=["out_partitioned", "out_non_partitioned"],
        )

        with pytest.raises(ValueError, match="mixed partitioned and non-partitioned"):
            translator._get_node_partition_keys(node)

    def test_identity_mapping_with_shared_partitions(self):
        """Partition keys map one-to-one when input and output share the same partitions."""
        catalog = DataCatalog(datasets={"in": MemoryDataset(), "out": MemoryDataset()})
        partitions_def = dg.StaticPartitionsDefinition(["2024-01", "2024-02"])

        asset_partitions = {
            "in": {"partitions_def": partitions_def, "partition_mappings": {}},
            "out": {"partitions_def": partitions_def, "partition_mappings": {}},
        }

        translator = _make_translator(catalog, asset_partitions)
        node = DummyNode(name="n1", inputs=["in"], outputs=["out"])

        mapping = translator._get_node_partition_keys(node)

        assert mapping == {
            "in|2024-01": "out|2024-01",
            "in|2024-02": "out|2024-02",
        }

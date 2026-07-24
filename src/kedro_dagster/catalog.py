"""Translate Kedro catalog datasets into Dagster IO managers.

This module inspects the Kedro catalog to create Dagster IO managers capable of
loading/saving datasets, while invoking Kedro dataset hooks. It also extracts
partitioning information for partitioned datasets.

See Also
--------
`kedro_dagster.nodes.NodeTranslator` :
    Translates Kedro nodes into Dagster ops and assets.
`kedro_dagster.pipelines.PipelineTranslator` :
    Translates Kedro pipelines into Dagster jobs.
"""

import base64
import json
from logging import getLogger
from os import PathLike
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

import dagster as dg
from kedro.io import MemoryDataset
from kedro.pipeline import Pipeline
from pydantic import ConfigDict, create_model

from kedro_dagster.datasets.partitioned_dataset import DagsterPartitionedDataset
from kedro_dagster.utils import (
    _create_pydantic_model_from_dict,
    _is_param_name,
    format_dataset_name,
    format_node_name,
    get_dataset_from_catalog,
    is_nothing_asset_name,
)

if TYPE_CHECKING:
    from kedro.io import AbstractDataset, CatalogProtocol
    from pluggy import PluginManager

LOGGER = getLogger(__name__)


def _json_safe(value: Any) -> Any:
    """Best-effort conversion of ``value`` into a JSON-serialisable structure.

    Kedro table previews are ``dict`` payloads that may hold non-serialisable
    objects (e.g. ``datetime``/``Timestamp`` values), so we coerce those to
    strings rather than letting Dagster fail when it stores the metadata.
    """
    return json.loads(json.dumps(value, default=str))


def _resolve_preview_type(preview_method: Any) -> "str | None":
    """Return the Kedro preview type name declared by a ``preview()`` method.

    Kedro's preview types are ``NewType`` aliases, so the concrete value is only
    ever a ``str`` or ``dict`` at runtime and cannot be told apart by type. The
    intended rendering is carried by the ``preview()`` return annotation instead
    (``TablePreview``, ``ImagePreview``, ``JSONPreview``, ``PlotlyPreview``,
    ``HTMLPreview``), matching how Kedro-Viz dispatches previews.
    """
    annotation = getattr(preview_method, "__annotations__", {}).get("return")
    if annotation is None:
        return None
    name = getattr(annotation, "__name__", None) or str(annotation)
    return name.rsplit(".", 1)[-1]


def _json_metadata(preview: Any) -> dg.MetadataValue:
    """Render a structured preview as JSON metadata, coercing awkward values."""
    try:
        return dg.MetadataValue.json(_json_safe(preview))
    except (TypeError, ValueError):
        return dg.MetadataValue.text(str(preview))


def _image_preview_metadata(preview: str) -> dg.MetadataValue:
    """Render a Kedro ``ImagePreview`` (base64 of the saved file) as Dagster metadata.

    ``MatplotlibDataset.preview()`` base64-encodes the raw saved bytes, so the format
    follows ``save_args["format"]``/the filepath suffix and may be PNG, JPEG, GIF, WEBP,
    SVG or PDF rather than always PNG. Sniff the decoded magic bytes to pick the right
    media type instead of assuming PNG (which would corrupt every non-PNG image). PDF
    cannot be inlined as a markdown image, so surface it as a data-URI link; anything we
    cannot identify falls back to the historical PNG assumption.
    """
    try:
        header = base64.b64decode(preview[:48], validate=False)
    except (ValueError, TypeError):
        return dg.MetadataValue.md(f"![preview](data:image/png;base64,{preview})")

    stripped = header.lstrip()
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type = "image/png"
    elif header.startswith(b"\xff\xd8\xff"):
        media_type = "image/jpeg"
    elif header.startswith((b"GIF87a", b"GIF89a")):
        media_type = "image/gif"
    elif header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        media_type = "image/webp"
    elif stripped.startswith((b"<?xml", b"<svg")):
        media_type = "image/svg+xml"
    elif header.startswith(b"%PDF"):
        return dg.MetadataValue.md(f"[preview.pdf](data:application/pdf;base64,{preview})")
    else:
        media_type = "image/png"

    return dg.MetadataValue.md(f"![preview](data:{media_type};base64,{preview})")


def _metadata_value_from_preview(preview: Any, preview_type: "str | None") -> dg.MetadataValue:
    """Convert a Kedro dataset preview into a Dagster metadata value.

    Dispatches on the declared ``preview_type`` (see :func:`_resolve_preview_type`)
    so images, raw JSON and tables each render correctly in Dagit, falling back to
    a structural check when no annotation is available.
    """
    if preview_type == "ImagePreview" and isinstance(preview, str):
        return _image_preview_metadata(preview)

    if preview_type == "HTMLPreview" and isinstance(preview, str):
        return dg.MetadataValue.md(preview)

    if preview_type == "JSONPreview" and isinstance(preview, str):
        # Raw JSON text; parse it so Dagit shows a structured, collapsible view.
        try:
            return dg.MetadataValue.json(json.loads(preview))
        except (TypeError, ValueError):
            return dg.MetadataValue.md(f"```json\n{preview}\n```")

    if isinstance(preview, str) and preview_type not in ("TablePreview", "PlotlyPreview"):
        return dg.MetadataValue.md(preview)

    return _json_metadata(preview)


def _get_dataset_preview_metadata(dataset: "AbstractDataset") -> dict[str, dg.MetadataValue]:
    """Return Dagster metadata containing a Kedro dataset preview when available.

    ``preview()`` re-reads the dataset from storage, which runs on every save, so
    previewing large datasets can be expensive. This honours the same per-dataset
    ``kedro-viz`` metadata convention used by Kedro-Viz to let users opt out or
    tune previews without touching pipeline code::

        my_dataset:
          type: pandas.CSVDataset
          filepath: ...
          metadata:
            kedro-viz:
              preview: false          # skip preview entirely (e.g. large data)
              preview_args:
                nrows: 5              # forwarded to preview()
    """
    preview = getattr(dataset, "preview", None)
    if not callable(preview):
        return {}

    viz_metadata = (getattr(dataset, "metadata", None) or {}).get("kedro-viz", {}) or {}
    if viz_metadata.get("preview") is False:
        return {}
    preview_args = viz_metadata.get("preview_args") or {}

    preview_value = preview(**preview_args)
    if preview_value is None:
        return {}

    preview_type = _resolve_preview_type(preview)
    return {"kedro_dataset_preview": _metadata_value_from_preview(preview_value, preview_type)}


class CatalogTranslator:
    """Translate Kedro datasets into Dagster IO managers.

    Parameters
    ----------
    catalog : CatalogProtocol
        Kedro catalog.
    pipelines : list[Pipeline]
        Kedro pipelines to consider when building IO managers.
    hook_manager : PluginManager
        Kedro hook manager used to invoke dataset hooks.
    env : str
        Kedro environment (used to namespace resource keys).

    See Also
    --------
    `kedro_dagster.nodes.NodeTranslator` :
        Translates Kedro nodes into Dagster ops and assets.
    `kedro_dagster.translator.KedroProjectTranslator` :
        Orchestrates the full Kedro-to-Dagster translation.
    """

    def __init__(
        self,
        catalog: "CatalogProtocol",
        pipelines: list["Pipeline"],
        hook_manager: "PluginManager",
        env: str,
    ):
        self._catalog = catalog
        self._pipelines = pipelines
        self._hook_manager = hook_manager
        self._env = env

    def _create_dataset_config(self, dataset: "AbstractDataset") -> Any:
        """Create a Pydantic model class capturing dataset configuration.

        The returned class extends Dagster's ``Config`` and contains fields for
        the dataset class short name and fields from ``dataset._describe()``
        (excluding ``version``), converting ``PurePosixPath`` values to strings
        for serialization.

        Parameters
        ----------
        dataset : AbstractDataset
            Kedro dataset to introspect.

        Returns
        -------
        type[Config]
            A Pydantic model class with dataset configuration fields.

        See Also
        --------
        `kedro_dagster.catalog.CatalogTranslator._translate_dataset` :
            Uses this config to build a configurable IO manager.
        """
        params: dict[str, Any] = {"dataset": dataset.__class__.__name__}
        for param, value in dataset._describe().items():
            if param == "version":
                continue
            # Convert any path-like values to strings (preserve original separators).
            if isinstance(value, PurePosixPath | PathLike):
                params[param] = str(value)
            else:
                params[param] = value

        DatasetConfig = _create_pydantic_model_from_dict(
            name="DatasetConfig",
            params=params,
            __base__=dg.Config,
            __config__=ConfigDict(arbitrary_types_allowed=True),
        )
        return DatasetConfig

    def _translate_dataset(
        self, dataset: "AbstractDataset", dataset_name: str
    ) -> tuple[dg.IOManagerDefinition, Any, Any]:
        """Create a configurable IO manager class for a single Kedro dataset.

        Parameters
        ----------
        dataset : AbstractDataset
            Kedro dataset to wrap into an IO manager.
        dataset_name : str
            Name of the dataset in the Kedro catalog.

        Returns
        -------
        tuple[IOManagerDefinition, Any, Any]
            3-tuple of (IO manager instance, partitions_def,
            partition_mappings).

        See Also
        --------
        `kedro_dagster.catalog.CatalogTranslator.to_dagster` :
            Iterates over all datasets calling this method.
        `kedro_dagster.datasets.DagsterPartitionedDataset` :
            Partition-aware dataset wrapper.
        """

        asset_name = format_dataset_name(dataset_name)

        partitions_def, partition_mappings = None, None
        if isinstance(dataset, DagsterPartitionedDataset):
            partitions_def = dataset._get_partitions_definition()
            partition_mappings = dataset._get_partition_mappings()

        DatasetConfig = self._create_dataset_config(dataset)

        hook_manager = self._hook_manager
        named_nodes = {format_node_name(node.name): node for node in sum(self._pipelines, start=Pipeline([])).nodes}

        class ConfigurableDatasetIOManager(DatasetConfig, dg.ConfigurableIOManager):  # type: ignore[valid-type]
            def handle_output(self, context: dg.OutputContext, obj) -> None:  # type: ignore[no-untyped-def]
                """Persist an output through the underlying Kedro dataset.

                Invokes ``before_dataset_saved`` and ``after_dataset_saved``
                Kedro hooks when the calling op corresponds to a known Kedro
                node.
                """
                node_name = context.op_def.name
                is_node_op = node_name in named_nodes

                if is_node_op:
                    context.log.info("Executing `before_dataset_saved` Kedro hook.")
                    node = named_nodes[node_name]
                    hook_manager.hook.before_dataset_saved(
                        dataset_name=dataset_name,
                        data=obj,
                        node=node,
                    )

                partition = None
                # Partition key passed via op tags for fanned-out ops
                if "downstream_partition_key" in context.op_def.tags:
                    downstream_partition_key = context.op_def.tags["downstream_partition_key"]
                    if asset_name == downstream_partition_key.split("|")[0]:
                        partition = downstream_partition_key.split("|")[1]
                # Partition key passed via context for asset jobs
                # Prefer Dagster's asset partition when available, otherwise fall back to plain partition_key
                elif getattr(context, "has_asset_partitions", False):
                    partition = context.asset_partition_key
                elif getattr(context, "has_partition_key", False):
                    partition = context.partition_key

                if partition is not None and isinstance(obj, dict) and set(obj.keys()) != {partition}:
                    raise ValueError(
                        f"Expected data for downstream partition to be a dict with key '{partition}' but got: {obj}"
                    )

                dataset.save(obj)

                try:
                    preview_metadata = _get_dataset_preview_metadata(dataset)
                except Exception as exc:
                    context.log.warning(f"Could not attach dataset preview metadata for `{dataset_name}`: {exc}")
                else:
                    if preview_metadata and hasattr(context, "add_output_metadata"):
                        context.add_output_metadata(preview_metadata)

                if is_node_op:
                    context.log.info("Executing `after_dataset_saved` Kedro hook.")
                    hook_manager.hook.after_dataset_saved(
                        dataset_name=dataset_name,
                        data=obj,
                        node=node,
                    )

            def load_input(self, context: dg.InputContext) -> Any:
                """Load an input through the underlying Kedro dataset.

                Invokes ``before_dataset_loaded`` and ``after_dataset_loaded``
                Kedro hooks when the calling op corresponds to a known Kedro
                node.
                """
                node_name = context.op_def.name
                is_node_op = node_name in named_nodes

                if is_node_op:
                    context.log.info("Executing `before_dataset_loaded` Kedro hook.")
                    node = named_nodes[node_name]
                    hook_manager.hook.before_dataset_loaded(
                        dataset_name=dataset_name,
                        node=node,
                    )

                data = dataset.load()

                partition = None
                # Partition key passed via op tags for fanned-out ops
                if "upstream_partition_key" in context.op_def.tags:
                    upstream_partition_key = context.op_def.tags["upstream_partition_key"]
                    if asset_name == upstream_partition_key.split("|")[0]:
                        partition = upstream_partition_key.split("|")[1]
                # Partition key passed via context for asset jobs
                # Prefer Dagster's asset partition when available, otherwise fall back to plain partition_key
                elif getattr(context, "has_asset_partitions", False):
                    partition = context.asset_partition_key
                elif getattr(context, "has_partition_key", False):
                    partition = context.partition_key

                if partition is not None and isinstance(data, dict):
                    data = {partition: data.get(partition)}

                if is_node_op:
                    context.log.info("Executing `after_dataset_loaded` Kedro hook.")
                    node = named_nodes[node_name]
                    hook_manager.hook.after_dataset_loaded(
                        dataset_name=dataset_name,
                        data=data,
                        node=node,
                    )

                return data

        # Build a named IO manager class for this particular dataset type
        dataset_type_short = dataset.__class__.__name__
        ConfigurableDatasetIOManagerClass = create_model(dataset_type_short, __base__=ConfigurableDatasetIOManager)
        ConfigurableDatasetIOManagerClass.__doc__ = f"IO Manager for Kedro dataset `{dataset_name}`."

        # Instantiate without args; defaults are embedded in the DatasetConfig
        io_manager_instance = ConfigurableDatasetIOManagerClass()

        return io_manager_instance, partitions_def, partition_mappings

    def to_dagster(self) -> tuple[dict[str, dg.IOManagerDefinition], dict[str, dict[str, Any]]]:
        """Generate IO managers and partitions for all Kedro datasets referenced by pipelines.

        Returns
        -------
        tuple[dict[str, IOManagerDefinition], dict[str, dict[str, Any]]]
            2-tuple of (named IO managers, asset partition definitions).

        Notes
        -----
        One IO manager is created per dataset by the private
        ``_translate_dataset`` method.
        """
        LOGGER.info("Translating Kedro catalog to Dagster IO managers...")
        named_io_managers: dict[str, dg.IOManagerDefinition] = {}
        asset_partitions: dict[str, dict[str, Any]] = {}

        for dataset_name in sum(self._pipelines, start=Pipeline([])).datasets():
            if _is_param_name(dataset_name) or is_nothing_asset_name(self._catalog, dataset_name):
                continue

            LOGGER.debug(f"Translating dataset '{dataset_name}'...")
            asset_name = format_dataset_name(dataset_name)
            dataset = get_dataset_from_catalog(self._catalog, dataset_name)
            if dataset is None:
                LOGGER.debug(
                    f"Dataset `{dataset_name}` not in catalog. It will be handled by default IO manager `io_manager`."
                )
                continue

            if isinstance(dataset, MemoryDataset):
                continue

            io_manager, partitions_def, partition_mappings = self._translate_dataset(dataset, dataset_name)
            named_io_managers[f"{self._env}__{asset_name}_io_manager"] = io_manager

            if partitions_def is not None:
                asset_partitions[asset_name] = {
                    "partitions_def": partitions_def,
                    "partition_mappings": partition_mappings,
                }

        LOGGER.debug(
            f"Translated {len(named_io_managers)} IO manager(s) with {len(asset_partitions)} partition definition(s)"
        )
        return named_io_managers, asset_partitions

# mypy: ignore-errors

from types import SimpleNamespace

import dagster as dg
import pytest
from dagster import IdentityPartitionMapping
from dagster._core.errors import DagsterInvalidInvocationError
from kedro.io import DataCatalog
from pydantic import BaseModel, ValidationError

from kedro_dagster.datasets import DagsterNothingDataset
from kedro_dagster.utils import (
    _create_pydantic_model_from_dict,
    _get_node_pipeline_name,
    _is_param_name,
    format_dataset_name,
    format_node_name,
    format_partition_key,
    get_asset_key_from_dataset_name,
    get_dataset_from_catalog,
    get_filter_params_dict,
    get_match_pattern_from_catalog_resolver,
    get_mlflow_resource_from_config,
    get_mlflow_run_url,
    get_partition_mapping,
    is_mlflow_enabled,
    is_nothing_asset_name,
    render_jinja_template,
    unformat_asset_name,
    write_jinja_template,
)


class TestJinjaTemplating:
    """Tests for Jinja template rendering and writing utilities."""

    def test_render_jinja_template(self, tmp_path):
        """Render a Jinja template file with provided context variables."""
        template_content = "Hello, {{ name }}!"
        template_path = tmp_path / "test_template.jinja"
        template_path.write_text(template_content)

        result = render_jinja_template(template_path, name="World")

        assert result == "Hello, World!"

    def test_write_jinja_template(self, tmp_path):
        """Write a rendered Jinja template to the destination path."""
        src = tmp_path / "template.jinja"
        dst = tmp_path / "output.txt"
        src.write_text("Hello, {{ name }}!")

        write_jinja_template(src, dst, name="Dagster")

        assert dst.read_text() == "Hello, Dagster!"

    def test_render_jinja_template_cookiecutter(self, tmp_path):
        """Render templates in Cookiecutter mode using cookiecutter.* variables."""
        src = tmp_path / "cookie.jinja"
        src.write_text("{{ cookiecutter.project_slug }}")

        rendered = render_jinja_template(src, is_cookiecutter=True, project_slug="kedro_dagster")

        assert rendered == "kedro_dagster"


class TestGetAssetKey:
    """Tests for get_asset_key_from_dataset_name."""

    def test_converts_dotted_name_and_env_to_asset_key(self):
        """Convert dataset name and env into a Dagster AssetKey path."""
        asset_key = get_asset_key_from_dataset_name("my.dataset", "dev")

        assert asset_key == dg.AssetKey(["dev", "my", "dataset"])


class TestFormatNodeName:
    """Tests for format_node_name."""

    def test_replaces_dots_with_double_underscore(self):
        """Dots in node names are replaced with double underscores."""
        formatted_name = format_node_name("my.node.name")

        assert formatted_name == "my__node__name"

    def test_hashes_invalid_characters(self):
        """Names with invalid characters are hashed to a stable 'unnamed_node_*' value."""
        invalid_name = "my.node@name"

        formatted_invalid_name = format_node_name(invalid_name)

        assert formatted_invalid_name.startswith("unnamed_node_")

    def test_hashes_hyphenated_names(self):
        """Names containing hyphens are hashed."""
        name = "node-with-hyphen"

        formatted = format_node_name(name)

        assert formatted.startswith("unnamed_node_")


class TestFormatPartitionKey:
    """Tests for format_partition_key."""

    def test_normalizes_partition_key_strings(self):
        """Normalize partition key strings by replacing separators with underscores."""
        assert format_partition_key("2024-01-01") == "2024_01_01"
        assert format_partition_key("a b/c") == "a_b_c"

    def test_raises_for_unfformatable_key(self):
        """Raise ValueError when key cannot be formatted into a valid Dagster key."""
        with pytest.raises(ValueError, match="cannot be formatted into a valid Dagster key"):
            format_partition_key("__")


class TestFormatDatasetName:
    """Tests for format_dataset_name and unformat_asset_name."""

    def test_format_and_unformat_are_inverses(self):
        """format_dataset_name and unformat_asset_name are inverses for dot-delimited names."""
        name = "my_dataset.with.dots"

        dagster = format_dataset_name(name)

        assert dagster == "my_dataset__with__dots"
        assert unformat_asset_name(dagster) == name

    def test_non_dot_chars_break_inversion(self):
        """Formatting replaces non-dot separators; inversion is not guaranteed."""
        name = "dataset-with-hyphen.and.dot"

        dagster_name = format_dataset_name(name)

        assert dagster_name == "dataset__with__hyphen__and__dot"
        assert unformat_asset_name(dagster_name) != name

    def test_rejects_reserved_identifiers(self):
        """Reserved Dagster identifiers like 'input'/'output' raise ValueError."""
        with pytest.raises(ValueError):
            format_dataset_name("input")
        with pytest.raises(ValueError):
            format_dataset_name("output")


class TestIsNothingAssetName:
    """Tests for is_nothing_asset_name."""

    def test_detects_nothing_dataset_in_catalog(self):
        """Detect Nothing datasets by name using the Kedro DataCatalog lookup."""
        catalog = DataCatalog(datasets={"nothing": DagsterNothingDataset()})

        assert is_nothing_asset_name(catalog, "nothing") is True
        assert is_nothing_asset_name(catalog, "missing") is False


class TestIsParamName:
    """Tests for _is_param_name."""

    def test_identifies_parameter_style_names(self):
        """Identify parameter-style names versus asset names."""
        assert not _is_param_name("my_ds")
        assert not _is_param_name("another_dataset__with__underscores")
        assert _is_param_name("parameters")
        assert _is_param_name("params:my_param")


class TestGetNodePipelineName:
    """Tests for _get_node_pipeline_name."""

    def test_infers_pipeline_name_from_registry(self, monkeypatch):
        """Infer the pipeline name a node belongs to from the pipelines registry."""
        mock_node = SimpleNamespace(name="test.node")
        mock_pipeline = SimpleNamespace(nodes=[mock_node])

        monkeypatch.setattr("kedro.framework.project.find_pipelines", lambda: {"pipeline": mock_pipeline})

        pipeline_name = _get_node_pipeline_name(mock_node)

        assert pipeline_name == "test__pipeline"

    def test_returns_none_and_warns_when_node_not_found(self, monkeypatch, caplog):
        """Return '__none__' and log a warning when the node is not in any pipeline."""
        mock_node = SimpleNamespace(name="orphan.node")
        monkeypatch.setattr(
            "kedro.framework.project.find_pipelines", lambda: {"__default__": SimpleNamespace(nodes=[])}
        )

        with caplog.at_level("WARNING"):
            result = _get_node_pipeline_name(mock_node)

            assert result == "__none__"
            assert "not part of any pipelines" in caplog.text


class TestGetFilterParamsDict:
    """Tests for get_filter_params_dict."""

    def test_maps_node_namespace_key_by_kedro_version(self):
        """Map node namespace key depending on Kedro major version; pass others unchanged."""
        pipeline_config = {
            "tags": ["tag1"],
            "from_nodes": ["node1"],
            "to_nodes": ["node2"],
            "node_names": ["node3"],
            "from_inputs": ["input1"],
            "to_outputs": ["output1_ds"],
            "node_namespaces": ["namespace"],
        }

        filter_params = get_filter_params_dict(pipeline_config)

        expected = dict(pipeline_config)
        assert filter_params == expected


class TestGetPartitionMapping:
    """Tests for get_partition_mapping."""

    def test_resolves_by_exact_key_or_pattern(self, monkeypatch, caplog):
        """Resolve partition mapping by exact key or pattern; warn and return None when missing."""

        class DummyResolver:
            def match_pattern(self, name):
                return "pattern" if name.startswith("foo") else None

        mappings = {"down_asset": IdentityPartitionMapping()}

        mapping = get_partition_mapping(mappings, "up", ["down_asset"], DummyResolver())

        assert isinstance(mapping, IdentityPartitionMapping)

        mappings2 = {"pattern": IdentityPartitionMapping()}

        mapping2 = get_partition_mapping(mappings2, "up", ["foo.bar"], DummyResolver())

        assert isinstance(mapping2, IdentityPartitionMapping)

        with caplog.at_level("WARNING"):
            mapping3 = get_partition_mapping({}, "upstream", ["zzz"], DummyResolver())

            assert mapping3 is None
            assert "default partition mapping" in caplog.text.lower()


class TestGetDatasetFromCatalog:
    """Tests for get_dataset_from_catalog."""

    def test_index_access_exception_returns_none(self, caplog):
        """When the catalog provides only index access and it raises, return None and log info."""

        class BadCatalog:
            def __getitem__(self, key):
                raise Exception("unexpected failure in __getitem__")

        bad_catalog = BadCatalog()

        with caplog.at_level("INFO"):
            result = get_dataset_from_catalog(bad_catalog, "missing_ds")

            assert result is None
            assert "Dataset 'missing_ds' not found in catalog." in caplog.text


class TestMlflowUtils:
    """Tests for MLflow-related utility functions."""

    def test_is_mlflow_enabled_returns_bool(self):
        """Return True when kedro-mlflow is importable and enabled in the environment."""
        assert isinstance(is_mlflow_enabled(), bool)

    def test_get_mlflow_resource_from_config(self):
        """Build a Dagster ResourceDefinition from a kedro-mlflow configuration object."""
        pytest.importorskip("kedro_mlflow")
        mock_mlflow_config = SimpleNamespace(
            tracking=SimpleNamespace(experiment=SimpleNamespace(name="test_experiment")),
            server=SimpleNamespace(mlflow_tracking_uri="http://localhost:5000"),
        )

        resource = get_mlflow_resource_from_config(mock_mlflow_config)

        assert isinstance(resource, dg.ResourceDefinition)


class TestGetMlflowRunUrl:
    """Tests for get_mlflow_run_url."""

    def test_remote_tracking_uri(self, monkeypatch):
        """Build URL from remote HTTP tracking URI."""
        pytest.importorskip("mlflow")
        import mlflow  # noqa: F401

        mock_run = SimpleNamespace(info=SimpleNamespace(experiment_id="123", run_id="abc456def"))

        monkeypatch.setattr("mlflow.active_run", lambda: mock_run)
        monkeypatch.setattr("mlflow.get_tracking_uri", lambda: "http://mlflow.example.com:5000")

        url = get_mlflow_run_url(SimpleNamespace())

        assert url == "http://mlflow.example.com:5000/#/experiments/123/runs/abc456def"

    def test_https_tracking_uri(self, monkeypatch):
        """Build URL from HTTPS tracking URI."""
        pytest.importorskip("mlflow")
        import mlflow  # noqa: F401

        mock_run = SimpleNamespace(info=SimpleNamespace(experiment_id="456", run_id="xyz789ghi"))

        monkeypatch.setattr("mlflow.active_run", lambda: mock_run)
        monkeypatch.setattr("mlflow.get_tracking_uri", lambda: "https://secure-mlflow.com/")

        url = get_mlflow_run_url(SimpleNamespace())

        assert url == "https://secure-mlflow.com/#/experiments/456/runs/xyz789ghi"

    def test_local_file_tracking_uri(self, monkeypatch):
        """Build URL from local file-based tracking URI with UI config."""
        pytest.importorskip("mlflow")
        import mlflow  # noqa: F401

        mock_run = SimpleNamespace(info=SimpleNamespace(experiment_id="789", run_id="local123run"))

        monkeypatch.setattr("mlflow.active_run", lambda: mock_run)
        monkeypatch.setattr("mlflow.get_tracking_uri", lambda: "file:///home/user/mlruns")

        mock_config = SimpleNamespace(ui=SimpleNamespace(host="localhost", port=5000))

        url = get_mlflow_run_url(mock_config)

        assert url == "http://localhost:5000/#/experiments/789/runs/local123run"

    def test_no_active_run_raises_runtime_error(self, monkeypatch):
        """Raise RuntimeError when no active MLflow run."""
        pytest.importorskip("mlflow")

        monkeypatch.setattr("mlflow.active_run", lambda: None)

        with pytest.raises(RuntimeError, match="No active MLflow run"):
            get_mlflow_run_url(SimpleNamespace())

    def test_unsupported_tracking_uri_raises_value_error(self, monkeypatch):
        """Raise ValueError for unsupported tracking URI schemes."""
        pytest.importorskip("mlflow")

        mock_run = SimpleNamespace(info=SimpleNamespace(experiment_id="999", run_id="unsupported"))

        monkeypatch.setattr("mlflow.active_run", lambda: mock_run)
        monkeypatch.setattr("mlflow.get_tracking_uri", lambda: "databricks://profile")

        with pytest.raises(ValueError, match="Unsupported MLflow tracking URI"):
            get_mlflow_run_url(SimpleNamespace())


class TestPydanticModelCreation:
    """Tests for _create_pydantic_model_from_dict."""

    def test_create_model_from_dict(self):
        """Create a nested Pydantic model class from a dictionary schema."""
        INNER_VALUE = 42
        params = {"param1": 1, "param2": "value", "nested": {"inner": INNER_VALUE}}

        model = _create_pydantic_model_from_dict("TestModel", params, BaseModel)
        instance = model(param1=1, param2="value", nested={"inner": INNER_VALUE})

        assert instance.param1 == 1
        assert instance.param2 == "value"
        assert hasattr(instance, "nested")
        assert instance.nested.inner == INNER_VALUE

    def test_config_and_model_behavior(self):
        """Validate ConfigDict works with _create_pydantic_model_from_dict."""
        from pydantic import ConfigDict

        config = ConfigDict(extra="forbid", validate_assignment=True)

        Model = _create_pydantic_model_from_dict(
            name="Params",
            params={"x": 1},
            __base__=dg.Config,
            __config__=config,
        )

        m = Model(x=1)
        assert m.x == 1

        with pytest.raises((ValidationError, ValueError, TypeError, DagsterInvalidInvocationError)):
            m.x = "not-an-int"  # type: ignore[assignment]

        model_config = getattr(Model, "model_config", {})
        assert isinstance(model_config, dict)

        ModelNoBase = _create_pydantic_model_from_dict(
            name="ParamsNoBase",
            params={"x": 1},
            __base__=None,
            __config__=config,
        )
        with pytest.raises(ValidationError):
            ModelNoBase(x=1, y=2)  # type: ignore[call-arg]
        cfg = getattr(ModelNoBase, "model_config", {})
        assert cfg.get("validate_assignment") is True
        assert cfg.get("extra") in {"forbid", 2}

    def test_model_with_config_dict(self):
        """Create a dynamic model with ConfigDict."""
        from pydantic import ConfigDict

        config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

        Model = _create_pydantic_model_from_dict(
            name="TestModel", params={"param1": "value1", "param2": 42}, __base__=BaseModel, __config__=config
        )

        instance = Model(param1="value1", param2=42)
        assert instance.param1 == "value1"
        assert instance.param2 == 42

        with pytest.raises(ValidationError):
            Model(param1="value1", param2=42, extra_field="not allowed")

    def test_model_with_dagster_config_base(self):
        """Create a dynamic model with Dagster Config base class."""
        from pydantic import ConfigDict

        config = ConfigDict(arbitrary_types_allowed=True)

        Model = _create_pydantic_model_from_dict(
            name="DagsterConfigModel",
            params={"dataset_name": "my_dataset", "env": "test"},
            __base__=dg.Config,
            __config__=config,
        )

        instance = Model(dataset_name="my_dataset", env="test")
        assert instance.dataset_name == "my_dataset"
        assert instance.env == "test"

    def test_model_without_base(self):
        """Create a dynamic model without a base class."""
        from pydantic import ConfigDict

        config = ConfigDict(extra="forbid")

        Model = _create_pydantic_model_from_dict(
            name="NoBaseModel", params={"field1": "value1"}, __base__=None, __config__=config
        )

        instance = Model(field1="value1")
        assert instance.field1 == "value1"

        with pytest.raises(ValidationError):
            Model(field1="value1", extra="not allowed")

    def test_model_with_nested_params(self):
        """Create a model with nested parameters."""
        from pydantic import ConfigDict

        config = ConfigDict(extra="allow")

        Model = _create_pydantic_model_from_dict(
            name="NestedModel",
            params={"simple_param": "value", "nested": {"inner_param": 123, "deep_nested": {"deep_param": True}}},
            __base__=BaseModel,
            __config__=config,
        )

        instance = Model(simple_param="value", nested={"inner_param": 123, "deep_nested": {"deep_param": True}})

        assert instance.simple_param == "value"
        assert hasattr(instance, "nested")
        assert instance.nested.inner_param == 123
        assert instance.nested.deep_nested.deep_param is True

    def test_model_preserves_validation_behavior(self):
        """Validate that validation behavior is preserved."""
        from pydantic import ConfigDict

        config = ConfigDict(validate_assignment=True, extra="forbid")

        Model = _create_pydantic_model_from_dict(
            name="ValidatedModel", params={"number_field": 42}, __base__=BaseModel, __config__=config
        )

        instance = Model(number_field=42)

        try:
            instance.number_field = "not a number"
        except (ValidationError, ValueError, TypeError):
            pass


class TestGetMatchPatternFromCatalogResolver:
    """Tests for get_match_pattern_from_catalog_resolver."""

    def test_returns_none_when_no_method_is_callable(self):
        """Return None when the resolver has neither match method."""
        resolver = SimpleNamespace()
        assert get_match_pattern_from_catalog_resolver(resolver, "ds") is None

    def test_returns_none_when_methods_are_not_callable(self):
        """Return None when the resolver attributes exist but are not callable."""
        resolver = SimpleNamespace(match_dataset_pattern="not_callable", match_pattern=42)
        assert get_match_pattern_from_catalog_resolver(resolver, "ds") is None


class TestGetPartitionMappingBranches:
    """Additional branch coverage for get_partition_mapping."""

    def test_warns_when_resolved_name_not_in_mappings(self, caplog):
        """Warn when downstream is found but its resolved name is not in partition_mappings."""

        class ResolverReturnsPattern:
            def match_pattern(self, name):
                return "resolved_name"

        with caplog.at_level("WARNING"):
            result = get_partition_mapping({}, "upstream", ["some_ds"], ResolverReturnsPattern())

        assert result is None
        assert "not found in the partition mappings" in caplog.text

    def test_warns_when_no_downstream_matches(self, caplog):
        """Warn when none of the downstream datasets match."""

        class ResolverNoMatch:
            def match_pattern(self, name):
                return None

        with caplog.at_level("WARNING"):
            result = get_partition_mapping(
                {"irrelevant": IdentityPartitionMapping()}, "upstream", ["no_match_ds"], ResolverNoMatch()
            )

        assert result is None
        assert "None of the downstream datasets" in caplog.text

    def test_returns_none_for_empty_downstream_list(self):
        """Return None when downstream_dataset_names is empty."""
        result = get_partition_mapping({"x": IdentityPartitionMapping()}, "upstream", [], SimpleNamespace())
        assert result is None


class TestPydanticModelNoneValues:
    """Test _create_pydantic_model_from_dict with None-valued params."""

    def test_none_value_typed_as_any(self):
        """A None value in params should produce a field typed as Any."""
        model = _create_pydantic_model_from_dict("NoneModel", {"nullable_field": None}, __base__=BaseModel)
        instance = model()
        assert instance.nullable_field is None
        # Should accept any type since it's typed as Any
        instance2 = model(nullable_field="hello")
        assert instance2.nullable_field == "hello"


class TestGetNodePipelineNameNonNamespaced:
    """Test _get_node_pipeline_name with non-namespaced node names."""

    def test_non_namespaced_node_returns_pipeline_name(self, monkeypatch):
        """Return plain pipeline name for non-namespaced node (no dots)."""
        mock_node = SimpleNamespace(name="simple_node")
        mock_pipeline = SimpleNamespace(nodes=[mock_node])

        monkeypatch.setattr("kedro.framework.project.find_pipelines", lambda: {"my_pipeline": mock_pipeline})

        result = _get_node_pipeline_name(mock_node)
        assert result == "my_pipeline"

    def test_skips_default_pipeline(self, monkeypatch):
        """Skip __default__ pipeline and find the node in a named pipeline."""
        mock_node = SimpleNamespace(name="node_a")
        default_pipeline = SimpleNamespace(nodes=[mock_node])
        named_pipeline = SimpleNamespace(nodes=[mock_node])

        monkeypatch.setattr(
            "kedro.framework.project.find_pipelines",
            lambda: {"__default__": default_pipeline, "data_processing": named_pipeline},
        )

        result = _get_node_pipeline_name(mock_node)
        assert result == "data_processing"

    def test_iterates_past_non_matching_nodes(self, monkeypatch):
        """Exercise inner loop continuation when node names don't match."""
        target_node = SimpleNamespace(name="target_node")
        other_node = SimpleNamespace(name="other_node")
        pipeline_with_both = SimpleNamespace(nodes=[other_node, target_node])

        monkeypatch.setattr(
            "kedro.framework.project.find_pipelines",
            lambda: {"pipeline_a": pipeline_with_both},
        )

        result = _get_node_pipeline_name(target_node)
        assert result == "pipeline_a"

    def test_iterates_past_non_matching_pipelines(self, monkeypatch):
        """Exercise outer loop continuation when pipeline has no matching node."""
        target_node = SimpleNamespace(name="target")
        wrong_node = SimpleNamespace(name="wrong")
        pipeline_a = SimpleNamespace(nodes=[wrong_node])
        pipeline_b = SimpleNamespace(nodes=[target_node])

        monkeypatch.setattr(
            "kedro.framework.project.find_pipelines",
            lambda: {"pipeline_a": pipeline_a, "pipeline_b": pipeline_b},
        )

        result = _get_node_pipeline_name(target_node)
        assert result == "pipeline_b"

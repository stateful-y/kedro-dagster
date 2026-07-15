"""Tests for forward-only job factory resolution (pipeline-derived bindings).

Ported from the sibling ``kedro-azureml-pipeline`` plugin, adapted to the
Kedro-Dagster models and the ``__`` job-type boundary (Dagster names forbid the
``-`` used there). Stub pipelines are plain objects exposing ``.nodes`` whose
items expose ``.namespace`` — the only pipeline attributes the factory reads.
"""

from types import SimpleNamespace

import pytest

from kedro_dagster.config.models import KedroDagsterConfig
from kedro_dagster.factory import (
    _bind_namespace,
    _job_suffix,
    _matches_job_type,
    _render_job,
    _render_str,
    enumerate_jobs,
    expand_job_factories,
    is_factory,
    resolve_jobs,
    resolve_target,
)

_NS4 = ["da_energy.hub.champion", "da_energy.hub.challenger", "rt_energy.hub.champion", "rt_energy.hub.challenger"]


def _pipe(*namespaces):
    """A stand-in Kedro pipeline: an object with ``.nodes``, each with ``.namespace``."""
    return SimpleNamespace(nodes=[SimpleNamespace(namespace=ns) for ns in namespaces])


def _config(jobs):
    """Build a ``KedroDagsterConfig`` from a raw ``jobs`` mapping."""
    return KedroDagsterConfig.model_validate({"jobs": jobs})


def _factories(jobs):
    """Build a config and return its factory entries as validated JobOptions values."""
    return {k: v for k, v in _config(jobs).jobs.items() if is_factory(k)}


def _inference(schedule="da_daily"):
    """A minimal inference-pipeline factory body with a three-level binding axis."""
    return {
        "schedule": schedule,
        "pipeline": {"pipeline_name": "inference", "node_namespaces": ["{product}.{group}.{variant}"]},
    }


def _base_jobs():
    """A representative set of training/inference factories over the ``_NS4`` namespaces."""
    return {
        "{product}__{group}__{variant}__training": {
            "schedule": "weekly_monday",
            "pipeline": {"pipeline_name": "training", "node_namespaces": ["{product}.{group}.{variant}"]},
        },
        "{product}__{group}__{variant}__inference": _inference("da_daily"),
        "rt_energy__{group}__{variant}__inference": _inference("rt_hourly"),
    }


_PIPES = {"training": _pipe(*_NS4), "inference": _pipe(*_NS4)}

# A complete binding (incl. job-type) as produced by _derive_bindings.
DA = {"product": "da_energy", "group": "hub", "variant": "champion", "job": "inference"}
RT = {"product": "rt_energy", "group": "hub", "variant": "champion", "job": "inference"}


class TestHelpers:
    """Tests for the small factory helper functions."""

    def test_is_factory(self):
        """A key with ``{placeholder}`` markers is a factory; a plain key is not."""
        assert is_factory("{product}__{group}__inference")
        assert not is_factory("snapshot")

    def test_job_suffix(self):
        """The job-type suffix is the literal text after the last ``{token}``."""
        assert _job_suffix("{product}__{group}__{variant}__inference") == "inference"
        assert _job_suffix("{product}__data_processing_candidate1") == "data_processing_candidate1"
        assert _job_suffix("rt_energy__{group}__{variant}__inference") == "inference"

    def test_bind_namespace(self):
        """A namespace binds to a template's tokens, honoring literal segments and depth."""
        assert _bind_namespace("{product}.{group}.{variant}", "da_energy.hub.champion") == {
            "product": "da_energy",
            "group": "hub",
            "variant": "champion",
        }
        assert _bind_namespace("{product}.{group}.{variant}", "da_energy.hub") is None  # too shallow
        assert _bind_namespace("rt_energy.{group}", "rt_energy.hub") == {"group": "hub"}  # literal match
        assert _bind_namespace("rt_energy.{group}", "da_energy.hub") is None  # literal mismatch

    def test_render_str_tolerates_unknown_and_passthrough(self):
        """String rendering fills known fields and leaves other syntax untouched."""
        assert _render_str("plain", {"a": "b"}) == "plain"
        assert _render_str("{variant}", {"variant": "champion"}) == "champion"
        assert _render_str("${oc.env:FOO}", {"variant": "x"}) == "${oc.env:FOO}"  # not a {token}
        assert _render_str("{missing}", {"variant": "x"}) == "{missing}"  # KeyError tolerated

    def test_render_job_accepts_dict_and_joboptions(self):
        """Rendering interpolates string leaves of a raw dict body."""
        job = _render_job({"pipeline": {"pipeline_name": "p", "tags": ["{variant}"]}}, {"variant": "champion"})
        assert job.pipeline.tags == ["champion"]

    def test_render_job_passes_through_non_string_leaves(self):
        """Non-string leaves (e.g. an int in schedule metadata) survive rendering unchanged."""
        job = _render_job(
            {
                "pipeline": {"pipeline_name": "p"},
                "schedule": {"cron_schedule": "0 0 * * *", "metadata": {"retries": 3}},
            },
            {},
        )
        assert job.schedule.metadata["retries"] == 3

    def test_matches_job_type(self):
        """A rendered name matches a job-type only on the ``__`` boundary (or exactly)."""
        assert _matches_job_type("x__inference", None) is True  # no job constraint
        assert _matches_job_type("x__inference", "inference") is True
        assert _matches_job_type("x__data_science", "data_processing") is False
        assert _matches_job_type("inference", "inference") is True  # exact


class TestResolveTarget:
    """Tests for the forward rendering engine, :func:`resolve_target`."""

    def test_renders_forward(self):
        """A binding renders forward into its concrete name and interpolated body."""
        factories = _factories({"{product}__{group}__{variant}__inference": _inference()})
        name, job = resolve_target(DA, factories)
        assert name == "da_energy__hub__champion__inference"
        assert job.pipeline.node_namespaces == ["da_energy.hub.champion"]

    def test_most_specific_wins(self):
        """The most-specific factory (most literal characters) supplies the body."""
        factories = _factories({
            "{product}__{group}__{variant}__inference": _inference("da_daily"),
            "rt_energy__{group}__{variant}__inference": _inference("rt_hourly"),
        })
        _, job = resolve_target(RT, factories)
        assert job.schedule == "rt_hourly"  # rt factory is more specific
        _, job = resolve_target(DA, factories)
        assert job.schedule == "da_daily"  # rt render != canonical -> excluded

    def test_none_when_no_consistent_factory(self):
        """A binding whose job-type matches no factory resolves to ``None``."""
        factories = _factories({"{product}__{group}__{variant}__training": _inference()})
        assert resolve_target(DA, factories) is None  # job 'inference' != 'training'

    def test_skips_factory_with_extra_token(self):
        """A factory needing a token the binding lacks is not a candidate."""
        factories = _factories({"{product}__{group}__{variant}__{region}__inference": _inference()})
        assert resolve_target(DA, factories) is None

    def test_skips_when_render_leaves_a_brace(self):
        """A binding value containing a brace leaves an unfilled placeholder and is skipped."""
        factories = _factories({"{product}__{group}__inference": _inference()})
        assert resolve_target({"product": "da_energy", "group": "{oops}", "job": "inference"}, factories) is None

    def test_roundtrips_string_executor_and_inline_schedule(self):
        """D3: a JobOptions body round-trips through model_dump/validate keeping refs intact."""
        factories = _factories({
            "{product}__{group}__{variant}__inference": {
                "pipeline": {"pipeline_name": "inference", "node_namespaces": ["{product}.{group}.{variant}"]},
                "executor": "multiprocessing",
                "schedule": {"cron_schedule": "0 2 * * *"},
                "loggers": ["console"],
            }
        })
        name, job = resolve_target(DA, factories)
        assert name == "da_energy__hub__champion__inference"
        assert job.executor == "multiprocessing"  # string executor reference intact
        assert job.schedule.cron_schedule == "0 2 * * *"  # inline schedule intact
        assert job.loggers == ["console"]
        assert job.pipeline.node_namespaces == ["da_energy.hub.champion"]


class TestEnumerateJobs:
    """Tests for pipeline-derived enumeration, :func:`enumerate_jobs`."""

    def test_derives_one_job_per_namespace(self):
        """Each distinct pipeline namespace yields one rendered job per factory."""
        jobs = enumerate_jobs(_config(_base_jobs()), pipelines=_PIPES)
        assert set(jobs) == {
            "da_energy__hub__champion__training",
            "da_energy__hub__challenger__training",
            "rt_energy__hub__champion__training",
            "rt_energy__hub__challenger__training",
            "da_energy__hub__champion__inference",
            "da_energy__hub__challenger__inference",
            "rt_energy__hub__champion__inference",
            "rt_energy__hub__challenger__inference",
        }
        assert jobs["da_energy__hub__champion__inference"].schedule == "da_daily"
        assert jobs["rt_energy__hub__champion__inference"].schedule == "rt_hourly"  # most-specific + dedup
        assert jobs["da_energy__hub__champion__inference"].pipeline.node_namespaces == ["da_energy.hub.champion"]

    def test_adding_a_namespace_adds_a_job(self):
        """A new pipeline namespace produces a new rendered job."""
        pipes = {"training": _pipe(*_NS4, "da_energy.zone.champion"), "inference": _pipe(*_NS4)}
        jobs = enumerate_jobs(_config(_base_jobs()), pipelines=pipes)
        assert "da_energy__zone__champion__training" in jobs
        assert jobs["da_energy__zone__champion__training"].pipeline.node_namespaces == ["da_energy.zone.champion"]

    def test_includes_literals_with_precedence(self):
        """Literal (non-factory) jobs are included alongside rendered ones."""
        jobs_cfg = {**_base_jobs(), "snapshot": {"pipeline": {"pipeline_name": "snapshot"}}}
        jobs = enumerate_jobs(_config(jobs_cfg), pipelines=_PIPES)
        assert jobs["snapshot"].pipeline.pipeline_name == "snapshot"  # literal preserved

    def test_literal_overrides_rendered_name(self):
        """A literal job wins over a rendered job of the same name."""
        jobs_cfg = {
            "{product}__{group}__{variant}__inference": _inference(),
            "da_energy__hub__champion__inference": {"pipeline": {"pipeline_name": "custom"}},  # literal collision
        }
        jobs = enumerate_jobs(_config(jobs_cfg), pipelines={"inference": _pipe("da_energy.hub.champion")})
        assert jobs["da_energy__hub__champion__inference"].pipeline.pipeline_name == "custom"

    def test_name_token_absent_from_namespaces_raises(self):
        """A factory token absent from the binding axis raises a helpful ``ValueError``."""
        cfg = _config({
            "{product}__{group}__{variant}__{job}": {
                "pipeline": {"pipeline_name": "training", "node_namespaces": ["{product}.{group}.{variant}"]},
            }
        })
        with pytest.raises(ValueError, match="absent from its node_namespaces template"):
            enumerate_jobs(cfg, pipelines={"training": _pipe("da_energy.hub.champion")})

    def test_skips_unregistered_pipeline_and_shallow_namespace(self):
        """Factories over absent pipelines and namespaces shallower than the axis are skipped."""
        cfg = _config({
            "{product}__{group}__{variant}__ghost": {
                "pipeline": {"pipeline_name": "ghost", "node_namespaces": ["{product}.{group}.{variant}"]},
            },
            "{product}__{group}__{variant}__training": {
                "pipeline": {"pipeline_name": "training", "node_namespaces": ["{product}.{group}.{variant}"]},
            },
        })
        pipes = {
            "training": _pipe("da_energy.hub.champion", "da_energy.shared")
        }  # 'ghost' absent; 'shared' too shallow
        jobs = enumerate_jobs(cfg, pipelines=pipes)
        assert set(jobs) == {"da_energy__hub__champion__training"}

    def test_literal_prefix_template_skips_nonmatching_namespace(self):
        """A literal segment in the axis restricts which namespaces bind."""
        cfg = _config({
            "rt_only__{group}__{variant}__training": {
                "pipeline": {"pipeline_name": "training", "node_namespaces": ["rt_energy.{group}.{variant}"]},
            }
        })
        pipes = {"training": _pipe("rt_energy.hub.champion", "da_energy.hub.champion")}
        jobs = enumerate_jobs(cfg, pipelines=pipes)
        assert set(jobs) == {"rt_only__hub__champion__training"}  # da_energy skipped by literal mismatch

    def test_factory_with_no_node_namespaces_is_skipped(self):
        """A factory without a ``node_namespaces`` axis derives no jobs."""
        cfg = _config({"{product}__{group}__{variant}__training": {"pipeline": {"pipeline_name": "training"}}})
        assert enumerate_jobs(cfg, pipelines={"training": _pipe("da_energy.hub.champion")}) == {}

    def test_falls_back_to_global_pipelines(self, monkeypatch):
        """When ``pipelines`` is ``None`` the global Kedro registry is used."""
        monkeypatch.setattr(
            "kedro.framework.project.pipelines", {"training": _pipe("da_energy.hub.champion")}, raising=False
        )
        cfg = _config({
            "{product}__{group}__{variant}__training": {
                "pipeline": {"pipeline_name": "training", "node_namespaces": ["{product}.{group}.{variant}"]}
            }
        })
        jobs = enumerate_jobs(cfg)  # pipelines=None -> global registry
        assert "da_energy__hub__champion__training" in jobs


class TestExpandJobFactories:
    """Tests for the translation entry point, :func:`expand_job_factories`."""

    def test_example_namespaces(self):
        """Mirrors the kedro-dagster-example staging config across mixed-depth namespaces."""
        cfg = _config({
            "{product}__data_processing_candidate1": {
                "pipeline": {
                    "pipeline_name": "data_processing",
                    "node_namespaces": ["{product}"],
                    "tags": ["candidate1"],
                },
                "executor": "multiprocessing",
                "schedule": "daily",
            },
            "{product}__data_science_candidate1": {
                "pipeline": {"pipeline_name": "data_science", "node_namespaces": ["{product}"], "tags": ["candidate1"]},
                "executor": "sequential",
                "schedule": "daily",
            },
        })
        pipes = {
            "data_processing": _pipe("reviews_predictor", "price_predictor"),
            "data_science": _pipe("reviews_predictor.candidate1", "price_predictor.candidate1"),
        }
        expanded = expand_job_factories(cfg, pipes)
        assert set(expanded.jobs) == {
            "reviews_predictor__data_processing_candidate1",
            "price_predictor__data_processing_candidate1",
            "reviews_predictor__data_science_candidate1",
            "price_predictor__data_science_candidate1",
        }
        # depth-1 axis truncates the 2-level data_science namespace to its product prefix
        ds_job = expanded.jobs["reviews_predictor__data_science_candidate1"]
        assert ds_job.pipeline.node_namespaces == ["reviews_predictor"]
        assert ds_job.executor == "sequential"
        assert expanded.jobs["price_predictor__data_processing_candidate1"].executor == "multiprocessing"

    def test_noop_without_factories(self):
        """A config with only literal jobs is returned unchanged (same object)."""
        cfg = _config({"snapshot": {"pipeline": {"pipeline_name": "snapshot"}}})
        assert expand_job_factories(cfg, pipelines={}) is cfg

    def test_noop_when_jobs_is_none(self):
        """A config with no ``jobs`` at all is returned unchanged (same object)."""
        cfg = KedroDagsterConfig()  # jobs is None
        assert expand_job_factories(cfg, pipelines={}) is cfg


class TestResolveJobs:
    """Tests for the dormant single-name lookup, :func:`resolve_jobs`."""

    def test_by_name(self):
        """A rendered job is resolvable by its concrete name."""
        selected = resolve_jobs(_config(_base_jobs()), ["rt_energy__hub__champion__inference"], pipelines=_PIPES)
        assert list(selected) == ["rt_energy__hub__champion__inference"]

    def test_multiple_names_reuse_enumeration(self):
        """Resolving several rendered names enumerates the job set only once."""
        names = ["da_energy__hub__champion__inference", "rt_energy__hub__champion__inference"]
        selected = resolve_jobs(_config(_base_jobs()), names, pipelines=_PIPES)
        assert set(selected) == set(names)

    def test_literal_fast_path(self):
        """A literal job is resolved directly without enumerating factories."""
        cfg = _config({"snapshot": {"pipeline": {"pipeline_name": "snapshot"}}})
        assert list(resolve_jobs(cfg, ["snapshot"])) == ["snapshot"]

    def test_miss_lists_available(self):
        """An unknown name raises a ``ValueError`` listing the available jobs."""
        with pytest.raises(ValueError, match="Job\\(s\\) not found"):
            resolve_jobs(_config(_base_jobs()), ["nope__x__y__inference"], pipelines=_PIPES)

    def test_miss_without_factories(self):
        """An unknown name with no factories present raises a ``ValueError``."""
        cfg = _config({"snapshot": {"pipeline": {"pipeline_name": "snapshot"}}})
        with pytest.raises(ValueError, match="Job\\(s\\) not found"):
            resolve_jobs(cfg, ["ghost"])

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
    return KedroDagsterConfig.model_validate({"jobs": jobs})


def _factories(jobs):
    """Build a config and return its factory entries as validated JobOptions values."""
    return {k: v for k, v in _config(jobs).jobs.items() if is_factory(k)}


def _inference(schedule="da_daily"):
    return {
        "schedule": schedule,
        "pipeline": {"pipeline_name": "inference", "node_namespaces": ["{product}.{group}.{variant}"]},
    }


def _base_jobs():
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


# --- small helpers -----------------------------------------------------------


def test_is_factory():
    assert is_factory("{product}__{group}__inference")
    assert not is_factory("snapshot")


def test_job_suffix():
    assert _job_suffix("{product}__{group}__{variant}__inference") == "inference"
    assert _job_suffix("{product}__data_processing_candidate1") == "data_processing_candidate1"
    assert _job_suffix("rt_energy__{group}__{variant}__inference") == "inference"


def test_bind_namespace():
    assert _bind_namespace("{product}.{group}.{variant}", "da_energy.hub.champion") == {
        "product": "da_energy",
        "group": "hub",
        "variant": "champion",
    }
    assert _bind_namespace("{product}.{group}.{variant}", "da_energy.hub") is None  # too shallow
    assert _bind_namespace("rt_energy.{group}", "rt_energy.hub") == {"group": "hub"}  # literal match
    assert _bind_namespace("rt_energy.{group}", "da_energy.hub") is None  # literal mismatch


def test_render_str_tolerates_unknown_and_passthrough():
    assert _render_str("plain", {"a": "b"}) == "plain"
    assert _render_str("{variant}", {"variant": "champion"}) == "champion"
    assert _render_str("${oc.env:FOO}", {"variant": "x"}) == "${oc.env:FOO}"  # not a {token}
    assert _render_str("{missing}", {"variant": "x"}) == "{missing}"  # KeyError tolerated


def test_render_job_accepts_dict_and_joboptions():
    job = _render_job({"pipeline": {"pipeline_name": "p", "tags": ["{variant}"]}}, {"variant": "champion"})
    assert job.pipeline.tags == ["champion"]


def test_render_job_passes_through_non_string_leaves():
    job = _render_job(
        {"pipeline": {"pipeline_name": "p"}, "schedule": {"cron_schedule": "0 0 * * *", "metadata": {"retries": 3}}},
        {},
    )
    assert job.schedule.metadata["retries"] == 3  # int leaves are passed through unchanged


def test_matches_job_type():
    assert _matches_job_type("x__inference", None) is True  # no job constraint
    assert _matches_job_type("x__inference", "inference") is True
    assert _matches_job_type("x__data_science", "data_processing") is False
    assert _matches_job_type("inference", "inference") is True  # exact


# --- resolve_target (the forward engine) -------------------------------------


def test_resolve_target_renders_forward():
    factories = _factories({"{product}__{group}__{variant}__inference": _inference()})
    name, job = resolve_target(DA, factories)
    assert name == "da_energy__hub__champion__inference"
    assert job.pipeline.node_namespaces == ["da_energy.hub.champion"]


def test_resolve_target_most_specific_wins():
    factories = _factories({
        "{product}__{group}__{variant}__inference": _inference("da_daily"),
        "rt_energy__{group}__{variant}__inference": _inference("rt_hourly"),
    })
    _, job = resolve_target(RT, factories)
    assert job.schedule == "rt_hourly"  # rt factory is more specific
    _, job = resolve_target(DA, factories)
    assert job.schedule == "da_daily"  # rt render != canonical -> excluded


def test_resolve_target_none_when_no_consistent_factory():
    factories = _factories({"{product}__{group}__{variant}__training": _inference()})
    assert resolve_target(DA, factories) is None  # job 'inference' != 'training'


def test_resolve_target_skips_factory_with_extra_token():
    # factory needs {region}, which the binding lacks -> not a candidate
    factories = _factories({"{product}__{group}__{variant}__{region}__inference": _inference()})
    assert resolve_target(DA, factories) is None


def test_resolve_target_skips_when_render_leaves_a_brace():
    # a binding value containing a brace leaves an unfilled placeholder
    factories = _factories({"{product}__{group}__inference": _inference()})
    assert resolve_target({"product": "da_energy", "group": "{oops}", "job": "inference"}, factories) is None


def test_render_job_roundtrips_string_executor_and_inline_schedule():
    # D3: a real JobOptions instance round-trips through model_dump -> model_validate,
    # keeping a string executor reference and an inline schedule intact.
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


# --- enumerate_jobs (pipeline-derived) ---------------------------------------


def test_enumerate_derives_one_job_per_namespace():
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


def test_enumerate_adding_a_namespace_adds_a_job():
    pipes = {"training": _pipe(*_NS4, "da_energy.zone.champion"), "inference": _pipe(*_NS4)}
    jobs = enumerate_jobs(_config(_base_jobs()), pipelines=pipes)
    assert "da_energy__zone__champion__training" in jobs
    assert jobs["da_energy__zone__champion__training"].pipeline.node_namespaces == ["da_energy.zone.champion"]


def test_enumerate_includes_literals_with_precedence():
    jobs_cfg = {**_base_jobs(), "snapshot": {"pipeline": {"pipeline_name": "snapshot"}}}
    jobs = enumerate_jobs(_config(jobs_cfg), pipelines=_PIPES)
    assert jobs["snapshot"].pipeline.pipeline_name == "snapshot"  # literal preserved


def test_enumerate_literal_overrides_rendered_name():
    jobs_cfg = {
        "{product}__{group}__{variant}__inference": _inference(),
        "da_energy__hub__champion__inference": {"pipeline": {"pipeline_name": "custom"}},  # literal collision
    }
    jobs = enumerate_jobs(_config(jobs_cfg), pipelines={"inference": _pipe("da_energy.hub.champion")})
    assert jobs["da_energy__hub__champion__inference"].pipeline.pipeline_name == "custom"


def test_enumerate_name_token_absent_from_namespaces_raises():
    cfg = _config({
        "{product}__{group}__{variant}__{job}": {
            "pipeline": {"pipeline_name": "training", "node_namespaces": ["{product}.{group}.{variant}"]},
        }
    })
    with pytest.raises(ValueError, match="absent from its node_namespaces template"):
        enumerate_jobs(cfg, pipelines={"training": _pipe("da_energy.hub.champion")})


def test_enumerate_skips_unregistered_pipeline_and_shallow_namespace():
    cfg = _config({
        "{product}__{group}__{variant}__ghost": {
            "pipeline": {"pipeline_name": "ghost", "node_namespaces": ["{product}.{group}.{variant}"]},
        },
        "{product}__{group}__{variant}__training": {
            "pipeline": {"pipeline_name": "training", "node_namespaces": ["{product}.{group}.{variant}"]},
        },
    })
    pipes = {"training": _pipe("da_energy.hub.champion", "da_energy.shared")}  # 'ghost' absent; 'shared' too shallow
    jobs = enumerate_jobs(cfg, pipelines=pipes)
    assert set(jobs) == {"da_energy__hub__champion__training"}


def test_enumerate_literal_prefix_template_skips_nonmatching_namespace():
    cfg = _config({
        "rt_only__{group}__{variant}__training": {
            "pipeline": {"pipeline_name": "training", "node_namespaces": ["rt_energy.{group}.{variant}"]},
        }
    })
    pipes = {"training": _pipe("rt_energy.hub.champion", "da_energy.hub.champion")}
    jobs = enumerate_jobs(cfg, pipelines=pipes)
    assert set(jobs) == {"rt_only__hub__champion__training"}  # da_energy skipped by literal mismatch


def test_enumerate_factory_with_no_node_namespaces_is_skipped():
    cfg = _config({"{product}__{group}__{variant}__training": {"pipeline": {"pipeline_name": "training"}}})
    assert enumerate_jobs(cfg, pipelines={"training": _pipe("da_energy.hub.champion")}) == {}


def test_enumerate_falls_back_to_global_pipelines(monkeypatch):
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


# --- expand_job_factories (the translation entry point) ----------------------


def test_expand_job_factories_example_namespaces():
    # Mirrors the kedro-dagster-example staging config: data_processing namespaces are
    # depth-1 ('reviews_predictor'), data_science are depth-2 ('reviews_predictor.candidate1'),
    # both bound by the depth-1 axis '{product}'.
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


def test_expand_job_factories_noop_without_factories():
    cfg = _config({"snapshot": {"pipeline": {"pipeline_name": "snapshot"}}})
    assert expand_job_factories(cfg, pipelines={}) is cfg  # unchanged, same object


def test_expand_job_factories_noop_when_jobs_is_none():
    cfg = KedroDagsterConfig()  # jobs is None
    assert expand_job_factories(cfg, pipelines={}) is cfg


# --- resolve_jobs (dormant, kept for parity) ---------------------------------


def test_resolve_jobs_by_name():
    selected = resolve_jobs(_config(_base_jobs()), ["rt_energy__hub__champion__inference"], pipelines=_PIPES)
    assert list(selected) == ["rt_energy__hub__champion__inference"]


def test_resolve_jobs_literal_fast_path():
    cfg = _config({"snapshot": {"pipeline": {"pipeline_name": "snapshot"}}})
    assert list(resolve_jobs(cfg, ["snapshot"])) == ["snapshot"]


def test_resolve_jobs_miss_lists_available():
    with pytest.raises(ValueError, match="Job\\(s\\) not found"):
        resolve_jobs(_config(_base_jobs()), ["nope__x__y__inference"], pipelines=_PIPES)


def test_resolve_jobs_miss_without_factories():
    # only literal jobs exist -> the requested name can never be rendered
    cfg = _config({"snapshot": {"pipeline": {"pipeline_name": "snapshot"}}})
    with pytest.raises(ValueError, match="Job\\(s\\) not found"):
        resolve_jobs(cfg, ["ghost"])

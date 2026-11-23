# mypy: ignore-errors

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import dagster as dg
import pytest
from kedro.framework.session import KedroSession
from kedro.framework.startup import bootstrap_project

from kedro_dagster.kedro import KedroRunTranslator, _get_failure_error_info


class _FakeHook:
    def __init__(self) -> None:
        self.after_context_created_called_with: list[Any] = []
        self.after_catalog_created_called_with: list[dict[str, Any]] = []
        self.on_pipeline_error_called_with: list[dict[str, Any]] = []

    def after_context_created(self, *, context: Any) -> None:
        self.after_context_created_called_with.append(context)

    def after_catalog_created(
        self,
        *,
        catalog: Any,
        conf_catalog: dict[str, Any],
        conf_creds: dict[str, Any],
        save_version: str | None = None,
        load_versions: Any = None,
        parameters: dict[str, Any] | None = None,
        feed_dict: dict[str, Any] | None = None,
    ) -> None:
        self.after_catalog_created_called_with.append({
            "catalog": catalog,
            "parameters": parameters,
            "feed_dict": feed_dict,
            "conf_catalog": conf_catalog,
            "conf_creds": conf_creds,
            "save_version": save_version,
            "load_versions": load_versions,
        })

    def on_pipeline_error(self, *, error: Exception, run_params: dict[str, Any], pipeline: Any, catalog: Any) -> None:
        self.on_pipeline_error_called_with.append({
            "error": error,
            "run_params": run_params,
            "pipeline": pipeline,
            "catalog": catalog,
        })


class _FakeHookManager:
    def __init__(self) -> None:
        self.hook = _FakeHook()


@pytest.fixture()
def kedro_context_base(kedro_project_exec_filebacked_base) -> Any:
    """Create and return a real Kedro context for the base exec_filebacked scenario."""
    options = kedro_project_exec_filebacked_base
    project_path = str(options.project_path)
    bootstrap_project(project_path)
    session = KedroSession.create(project_path=project_path, env=options.env)
    return session.load_context()


class TestKedroRunResource:
    """Tests for KedroRunTranslator resource creation and pipeline filtering."""

    def test_creates_resource_and_merges_params(
        self, kedro_context_base, kedro_project_exec_filebacked_base, monkeypatch
    ):
        """Resource contains merged Kedro defaults, pipeline name, and filter params."""
        options = kedro_project_exec_filebacked_base
        translator = KedroRunTranslator(
            context=kedro_context_base,
            catalog=kedro_context_base.catalog,
            project_path=str(options.project_path),
            env=options.env,
            run_id="sid-123",
        )

        resource = translator.to_dagster(
            pipeline_name="__default__",
            filter_params={
                "tags": ["a", "b"],
                "from_nodes": ["n1"],
                "to_nodes": None,
                "node_names": ["task"],
            },
        )

        params = resource.run_params
        assert params["project_path"] == str(options.project_path)
        assert params["env"] == options.env
        assert params["run_id"] == "sid-123"
        assert params["pipeline_name"] == "__default__"
        assert params["load_versions"] is None
        assert params["runtime_params"] is None
        assert params["runner"] is None
        assert params["tags"] == ["a", "b"]
        assert params["from_nodes"] == ["n1"]
        assert params["node_names"] == ["task"]

    def test_pipeline_filters_via_registry(self, kedro_context_base, kedro_project_exec_filebacked_base, monkeypatch):
        """Resource.pipeline delegates to Kedro registry and calls filter with provided args."""
        options = kedro_project_exec_filebacked_base
        translator = KedroRunTranslator(
            context=kedro_context_base,
            catalog=kedro_context_base.catalog,
            project_path=str(options.project_path),
            env=options.env,
            run_id="sid-xyz",
        )

        captured: dict[str, Any] = {}

        node_namespace_key = "node_namespaces"
        node_namespace_val = ["ns"]

        class _DummyPipeline:
            def filter(
                self,
                *,
                tags=None,
                from_nodes=None,
                to_nodes=None,
                node_names=None,
                from_inputs=None,
                to_outputs=None,
                node_namespaces=None,
            ) -> dict[str, Any]:
                captured.update({
                    "tags": tags,
                    "from_nodes": from_nodes,
                    "to_nodes": to_nodes,
                    "node_names": node_names,
                    "from_inputs": from_inputs,
                    "to_outputs": to_outputs,
                    "node_namespaces": node_namespaces,
                })
                return {"ok": True}

        monkeypatch.setattr("kedro.framework.project.pipelines.get", lambda name: _DummyPipeline())

        resource = translator.to_dagster(
            pipeline_name="my_pipeline",
            filter_params={
                "tags": ["x"],
                "from_nodes": ["A"],
                "to_outputs": ["out"],
                node_namespace_key: node_namespace_val,
            },
        )

        pipe = resource.pipeline
        assert pipe == {"ok": True}
        assert captured == {
            "tags": ["x"],
            "from_nodes": ["A"],
            "to_nodes": None,
            "node_names": None,
            "from_inputs": None,
            "to_outputs": ["out"],
            node_namespace_key: node_namespace_val,
        }


class TestKedroRunHooks:
    """Tests for KedroRunTranslator hook invocation."""

    def test_after_context_created_hook(self, kedro_context_base, kedro_project_exec_filebacked_base):
        """after_context_created_hook triggers the Kedro hook with the current context."""
        options = kedro_project_exec_filebacked_base
        translator = KedroRunTranslator(
            context=kedro_context_base,
            catalog=kedro_context_base.catalog,
            project_path=str(options.project_path),
            env=options.env,
            run_id="sid-123",
        )
        fake_hook_mgr = _FakeHookManager()
        translator._context._hook_manager = fake_hook_mgr
        translator._hook_manager = fake_hook_mgr
        resource = translator.to_dagster(pipeline_name="__default__", filter_params={})

        resource.after_context_created_hook()

        fake_ctx = translator._context
        assert fake_ctx._hook_manager.hook.after_context_created_called_with == [fake_ctx]

    def test_after_catalog_created_hook(self, kedro_context_base, kedro_project_exec_filebacked_base):
        """after_catalog_created_hook triggers the Kedro hook with all required parameters."""
        options = kedro_project_exec_filebacked_base
        translator = KedroRunTranslator(
            context=kedro_context_base,
            catalog=kedro_context_base.catalog,
            project_path=str(options.project_path),
            env=options.env,
            run_id="sid-456",
        )
        fake_hook_mgr = _FakeHookManager()
        translator._context._hook_manager = fake_hook_mgr
        translator._hook_manager = fake_hook_mgr
        resource = translator.to_dagster(pipeline_name="__default__", filter_params={})

        resource.after_catalog_created_hook()

        assert len(fake_hook_mgr.hook.after_catalog_created_called_with) >= 1

        hook_call = fake_hook_mgr.hook.after_catalog_created_called_with[-1]

        assert hasattr(hook_call["catalog"], "_datasets")

        assert hook_call["parameters"] == translator._context._get_parameters()
        assert hook_call["feed_dict"] is None

        assert isinstance(hook_call["conf_catalog"], dict)
        assert isinstance(hook_call["conf_creds"], dict)

        assert hook_call["save_version"] == "sid-456"

        assert hook_call["load_versions"] is None

    def test_on_pipeline_error_hook_returns_sensor(
        self, kedro_context_base, kedro_project_exec_filebacked_base, monkeypatch
    ):
        """_translate_on_pipeline_error_hook returns a sensor with expected metadata."""
        options = kedro_project_exec_filebacked_base
        translator = KedroRunTranslator(
            context=kedro_context_base,
            catalog=kedro_context_base.catalog,
            project_path=str(options.project_path),
            env=options.env,
            run_id="sid-123",
        )

        named_jobs = {"default": object()}

        @dataclass
        class _FakeSensorDefinition:
            name: str
            description: str
            monitored_jobs: list[Any]
            default_status: Any
            fn: Callable[..., Any]

        def fake_run_failure_sensor(name: str, description: str, monitored_jobs: list[Any], default_status: Any):
            def _decorator(fn: Callable[..., Any]) -> _FakeSensorDefinition:
                return _FakeSensorDefinition(
                    name=name,
                    description=description,
                    monitored_jobs=monitored_jobs,
                    default_status=default_status,
                    fn=fn,
                )

            return _decorator

        monkeypatch.setattr(dg, "run_failure_sensor", fake_run_failure_sensor)

        class _Sentinel:
            RUNNING = "RUNNING"

        monkeypatch.setattr(dg, "DefaultSensorStatus", _Sentinel)

        sensors = translator._translate_on_pipeline_error_hook(named_jobs)
        assert "on_pipeline_error_sensor" in sensors
        sensor_def = sensors["on_pipeline_error_sensor"]

        assert sensor_def.name == "on_pipeline_error_sensor"
        assert isinstance(sensor_def.description, str) and len(sensor_def.description) > 0
        assert sensor_def.monitored_jobs == list(named_jobs.values())
        assert sensor_def.default_status == "RUNNING"

    def test_on_pipeline_error_sensor_calls_hook_on_failed_run(
        self, kedro_context_base, kedro_project_exec_filebacked_base
    ):
        """The sensor passes an exception and the run params of the failed job to the Kedro hook."""
        options = kedro_project_exec_filebacked_base
        translator = KedroRunTranslator(
            context=kedro_context_base,
            catalog=kedro_context_base.catalog,
            project_path=str(options.project_path),
            env=options.env,
            run_id="sid-123",
        )
        fake_hook_mgr = _FakeHookManager()
        translator._hook_manager = fake_hook_mgr

        @dg.op
        def failing_op():
            raise ValueError("kaboom")

        @dg.job(resource_defs={"kedro_run": translator.to_dagster(pipeline_name="__default__", filter_params={})})
        def other_job():
            failing_op()

        @dg.job(
            resource_defs={"kedro_run": translator.to_dagster(pipeline_name="pipe", filter_params={"tags": ["tag2"]})}
        )
        def failing_job():
            failing_op()

        sensors = translator._translate_on_pipeline_error_hook({"other": other_job, "failing": failing_job})
        sensor_def = sensors["on_pipeline_error_sensor"]

        with dg.DagsterInstance.ephemeral() as instance:
            result = failing_job.execute_in_process(instance=instance, raise_on_error=False)
            assert not result.success

            # As in a deployment, the sensor gets no resource: it requires none.
            assert sensor_def.required_resource_keys == set()
            sensor_context = dg.build_run_status_sensor_context(
                sensor_name="on_pipeline_error_sensor",
                dagster_event=result.get_run_failure_event(),
                dagster_instance=instance,
                dagster_run=result.dagster_run,
            ).for_run_failure()

            sensor_def(sensor_context)

        assert len(fake_hook_mgr.hook.on_pipeline_error_called_with) == 1
        hook_call = fake_hook_mgr.hook.on_pipeline_error_called_with[0]

        error = hook_call["error"]
        assert isinstance(error, Exception)
        assert type(error).__name__ == "DagsterExecutionStepExecutionError"
        assert str(error) == 'Error occurred while executing op "failing_op":'
        assert isinstance(error.__cause__, Exception)
        assert type(error.__cause__).__name__ == "ValueError"
        assert str(error.__cause__) == "kaboom"

        assert hook_call["run_params"]["pipeline_name"] == "pipe"
        assert hook_call["run_params"]["tags"] == ["tag2"]
        assert hook_call["run_params"]["run_id"] == "sid-123"
        assert {node.name for node in hook_call["pipeline"].nodes} == {"node3", "node4"}
        assert hook_call["catalog"] is translator._catalog


@dataclass
class _FakeEvent:
    event_specific_data: Any
    message: str | None = None


@dataclass
class _FakeFailureData:
    error: Any


@dataclass
class _FakeSensorContext:
    failure_event: _FakeEvent
    step_failure_events: list[_FakeEvent]

    def get_step_failure_events(self) -> list[_FakeEvent]:
        return self.step_failure_events


class TestFailureErrorInfo:
    """Tests for the error lookup of the `on_pipeline_error` sensor."""

    def test_error_of_the_run_failure_event_is_preferred(self):
        """The error of the run failure event is returned when it exists."""
        context = _FakeSensorContext(
            failure_event=_FakeEvent(_FakeFailureData(error="run error")),
            step_failure_events=[_FakeEvent(_FakeFailureData(error="step error"))],
        )

        assert _get_failure_error_info(context) == "run error"

    def test_falls_back_to_the_first_failed_step(self):
        """Dagster before 1.13 records the error on the step failure events only."""
        context = _FakeSensorContext(
            failure_event=_FakeEvent(_FakeFailureData(error=None)),
            step_failure_events=[
                _FakeEvent(_FakeFailureData(error=None)),
                _FakeEvent(_FakeFailureData(error="step error")),
            ],
        )

        assert _get_failure_error_info(context) == "step error"

    def test_returns_none_when_no_error_was_recorded(self):
        """A run reported as failed from outside an execution has no error."""
        context = _FakeSensorContext(failure_event=_FakeEvent(None), step_failure_events=[])

        assert _get_failure_error_info(context) is None

    def test_sensor_reports_a_run_that_failed_without_error(self, kedro_context_base):
        """The hook receives a `RuntimeError` with the event message when Dagster recorded no error."""
        translator = KedroRunTranslator(
            context=kedro_context_base,
            catalog=kedro_context_base.catalog,
            project_path=str(kedro_context_base.project_path),
            env="base",
            run_id="sid-123",
        )
        fake_hook_mgr = _FakeHookManager()
        translator._hook_manager = fake_hook_mgr

        @dg.op
        def passing_op():
            return 1

        @dg.job(resource_defs={"kedro_run": translator.to_dagster(pipeline_name="__default__", filter_params={})})
        def reported_job():
            passing_op()

        sensor_def = translator._translate_on_pipeline_error_hook({"reported": reported_job})[
            "on_pipeline_error_sensor"
        ]

        with dg.DagsterInstance.ephemeral() as instance:
            run = instance.create_run_for_job(reported_job)
            instance.report_run_failed(run, "stopped from outside")
            failure_event = next(
                record.event_log_entry.dagster_event
                for record in instance.get_records_for_run(run.run_id).records
                if record.event_log_entry.dagster_event is not None
                and record.event_log_entry.dagster_event.event_type == dg.DagsterEventType.RUN_FAILURE
            )
            sensor_context = dg.build_run_status_sensor_context(
                sensor_name="on_pipeline_error_sensor",
                dagster_instance=instance,
                dagster_run=instance.get_run_by_id(run.run_id),
                dagster_event=failure_event,
            ).for_run_failure()
            sensor_def(sensor_context)

        assert len(fake_hook_mgr.hook.on_pipeline_error_called_with) == 1
        error = fake_hook_mgr.hook.on_pipeline_error_called_with[0]["error"]
        assert type(error) is RuntimeError
        assert "stopped from outside" in str(error)

"""Forward-only job factory resolution.

A ``jobs`` key containing ``{placeholder}`` markers is a *job factory*: a
templated job entry sharing the config surface of a Kedro dataset factory. The
concrete jobs are derived from the Kedro pipeline namespaces. For each factory,
its ``node_namespaces`` template defines the binding placeholders and their
namespace depth, and the distinct namespaces of its pipeline become the jobs (the
job analogue of a dataset factory, whose datasets are determined by pipeline node
references).

Names are produced only by rendering bindings forward; they are never
reverse-parsed (a placeholder value can contain the ``_`` separator, e.g.
``reviews_predictor``, which would make reverse-parsing ambiguous). The fixed
job-type tail is separated from the placeholder-derived part by
:data:`~kedro_dagster.constants.KEDRO_DAGSTER_SEPARATOR` (``__``) so it can be
recovered unambiguously with ``rsplit("__")``; placeholder-derived parts keep
single ``_``. Rendered names are valid Dagster names (``^[A-Za-z0-9_]+$``), which
forbid the ``-`` used by the sibling ``kedro-azureml-pipeline`` plugin.

* enumerate (schedule creation, listing): render every binding into its job.
* resolve <name>: render all bindings (plus literal jobs) into a name -> job map
  and look the requested name up.

Each binding is tagged with its factory's job-type suffix, so a binding for one
job type never matches a factory for another. When several factories render the
same name, the most-specific one (most literal characters) supplies the config.
"""

from __future__ import annotations

import string
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from kedro_dagster.config.models import JobOptions
from kedro_dagster.constants import KEDRO_DAGSTER_SEPARATOR

if TYPE_CHECKING:
    from kedro_dagster.config.models import KedroDagsterConfig


def _job_suffix(factory_key: str) -> str:
    """Job-type suffix of a factory key (literal text after the last ``{token}``)."""
    return factory_key.rsplit("}", 1)[-1].lstrip("_")


def _ordered_tokens(template: str) -> list[str]:
    """Field names in *template*, in order of appearance."""
    return [name for _, name, _, _ in string.Formatter().parse(template) if name]


def _bind_namespace(template: str, namespace: str) -> dict[str, str] | None:
    """Bind a node *namespace* to the tokens of a `node_namespaces` *template*.

    The template and namespace are split on ``.``; each template segment is either
    a single ``{token}`` (bound to the namespace part) or a literal (which must
    match the namespace part). Returns the binding, or ``None`` if the namespace is
    shallower than the template or a literal segment does not match.
    """
    segments = template.split(".")
    parts = namespace.split(".")
    if len(parts) < len(segments):
        return None
    binding: dict[str, str] = {}
    for segment, part in zip(segments, parts, strict=False):  # parts may be deeper than the template
        tokens = _ordered_tokens(segment)
        if tokens:
            binding[tokens[0]] = part
        elif segment != part:
            return None
    return binding


def _derive_bindings(config: KedroDagsterConfig, pipelines: Mapping[str, Any] | None) -> list[dict[str, str]]:
    """Derive job bindings from each factory's pipeline namespaces.

    For each job factory, the factory's ``pipeline.node_namespaces`` template
    defines the binding tokens and their namespace depth; the distinct namespaces
    of the factory's ``pipeline_name`` pipeline at that depth become the bindings,
    each tagged with the factory's job-type suffix. *pipelines* is the Kedro
    pipeline registry; when ``None`` the global registry is used.

    Only the *first* ``node_namespaces`` entry is the binding axis: it sets the
    tokens and depth used here. Any further entries are not used for derivation;
    they still render per binding (in :func:`_render_job`) as the rendered job's
    runtime namespace filters, so a factory can derive its axis from the first
    entry and carry extra static namespace filters in the rest.
    """
    if pipelines is None:
        from kedro.framework.project import pipelines  # noqa: PLC0415

    bindings: list[dict[str, str]] = []
    seen: set[frozenset[tuple[str, str]]] = set()
    for key, job in (config.jobs or {}).items():
        if not is_factory(key):
            continue
        templates = job.pipeline.node_namespaces or []
        pipe = pipelines.get(job.pipeline.pipeline_name)
        if not templates or pipe is None:
            continue
        template = templates[0]
        # Every token in the factory name must be bindable from the namespace
        # template; otherwise the rendered name would keep an unfilled `{token}`.
        unbindable = _tokens(key) - _tokens(template)
        if unbindable:
            raise ValueError(
                f"Job factory '{key}' references token(s) {sorted(unbindable)} "
                f"absent from its node_namespaces template '{template}'."
            )
        depth = len(template.split("."))
        namespaces = {
            ".".join(node.namespace.split(".")[:depth])
            for node in pipe.nodes
            if node.namespace and len(node.namespace.split(".")) >= depth
        }
        suffix = _job_suffix(key)
        for namespace in namespaces:
            binding = _bind_namespace(template, namespace)
            if binding is None:
                continue
            binding["job"] = suffix
            marker = frozenset(binding.items())
            if marker in seen:
                continue
            seen.add(marker)
            bindings.append(binding)
    return bindings


def is_factory(key: str) -> bool:
    """True if a ``jobs`` key is a factory (contains ``{placeholder}`` markers)."""
    return "{" in key and "}" in key


def _tokens(template: str) -> set[str]:
    """Field names referenced by ``{token}`` placeholders in *template*."""
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def _literal_len(template: str) -> int:
    """Total length of the literal (non-placeholder) text in *template*."""
    return sum(len(literal or "") for literal, _, _, _ in string.Formatter().parse(template))


def _render_str(value: str, tokens: dict[str, str]) -> str:
    """``str.format`` *value* with *tokens*, but only if it has a fillable field.

    Strings without ``{...}`` are returned unchanged. A leftover OmegaConf
    ``${...}`` (already resolved at config-load time, so not expected here) or any
    unknown field is tolerated by returning the original string rather than
    raising, so ``{token}`` rendering never disturbs other interpolation syntax.
    """
    if "{" not in value or "}" not in value:
        return value
    try:
        return value.format(**tokens)
    except (KeyError, IndexError, ValueError):
        return value


def _render_value(value: Any, tokens: dict[str, str]) -> Any:
    """Recursively interpolate string leaves of *value* (str/list/dict) with *tokens*."""
    if isinstance(value, str):
        return _render_str(value, tokens)
    if isinstance(value, list):
        return [_render_value(item, tokens) for item in value]
    if isinstance(value, dict):
        return {key: _render_value(item, tokens) for key, item in value.items()}
    return value


def _render_job(config: JobOptions | dict[str, Any], tokens: dict[str, str]) -> JobOptions:
    """Render a factory's job config (``JobOptions`` or raw dict) by interpolating leaves."""
    data = config.model_dump(exclude_none=True) if isinstance(config, JobOptions) else config
    return JobOptions.model_validate(_render_value(data, tokens))


def _matches_job_type(name: str, job: str | None) -> bool:
    """True if rendered *name* ends at the target's *job* value on the ``__`` boundary."""
    if job is None:
        return True
    return name == job or name.endswith(f"{KEDRO_DAGSTER_SEPARATOR}{job}")


def resolve_target(target: dict[str, str], factories: dict[str, JobOptions]) -> tuple[str, JobOptions] | None:
    """Render a single target into its ``(name, JobOptions)``, or ``None``.

    Selects the most-specific factory consistent with the target (see module
    docstring). Returns ``None`` if no factory is consistent with the target.
    """
    target_keys = set(target)
    job = target.get("job")

    candidates: list[tuple[str, JobOptions, str, int, int]] = []
    for key, config in factories.items():
        toks = _tokens(key)
        if not toks <= target_keys:
            continue
        name = _render_str(key, target)
        if "{" in name:  # unfilled placeholder remained
            continue
        if not _matches_job_type(name, job):
            continue
        candidates.append((key, config, name, _literal_len(key), len(toks)))

    if not candidates:
        return None

    # The canonical name is set by the most-general candidate (most tokens; ties
    # broken by most literal characters, then key) so it reflects every token of
    # the target (e.g. the full product, not a specific factory's literal prefix).
    canonical = max(candidates, key=lambda c: (c[4], c[3], c[0]))[2]
    applicable = [c for c in candidates if c[2] == canonical]
    # Most-specific applicable factory (most literal characters) supplies the body.
    key, config, name, *_ = max(applicable, key=lambda c: (c[3], c[0]))
    return name, _render_job(config, target)


def enumerate_jobs(config: KedroDagsterConfig, pipelines: Mapping[str, Any] | None = None) -> dict[str, JobOptions]:
    """Render every derived binding into a ``name -> JobOptions`` map, overlaying literals.

    Bindings are derived from the Kedro pipeline namespaces (see
    :func:`_derive_bindings`). Literal (non-factory) ``jobs`` entries are included
    and take precedence over rendered ones on a name collision.
    """
    jobs = config.jobs or {}
    factories = {k: v for k, v in jobs.items() if is_factory(k)}
    literals = {k: v for k, v in jobs.items() if not is_factory(k)}

    rendered: dict[str, JobOptions] = {}
    for binding in _derive_bindings(config, pipelines):
        result = resolve_target(binding, factories)
        if result is None:  # pragma: no cover - defensive; a derived binding always has its own factory
            raise ValueError(f"No job factory matches binding {binding!r}.")
        name, job_config = result
        if name in rendered:  # pragma: no cover - defensive; bindings are de-duplicated before rendering
            raise ValueError(f"Two bindings render to the same job name '{name}'.")
        rendered[name] = job_config

    rendered.update(literals)  # literal jobs win over rendered ones
    return rendered


def resolve_jobs(
    config: KedroDagsterConfig, job_names: list[str], pipelines: Mapping[str, Any] | None = None
) -> dict[str, JobOptions]:
    """Resolve requested job names to ``JobOptions`` via literals + rendered bindings.

    Literal jobs are matched directly; any remaining name is looked up in the
    enumerated job set (see :func:`enumerate_jobs`). Raises a ``ValueError`` listing
    available names if a requested name is neither a literal job nor a rendered one.

    Notes
    -----
    Dagster's ``Definitions`` enumerates every job up front, so kedro-dagster has
    no single-job ``run -j <name>`` path; this function is retained for structural
    parity with the sibling ``kedro-azureml-pipeline`` plugin.
    """
    jobs = config.jobs or {}
    literals = {k: v for k, v in jobs.items() if not is_factory(k)}
    has_factories = any(is_factory(k) for k in jobs)

    resolved: dict[str, JobOptions] = {}
    all_jobs: dict[str, JobOptions] | None = None
    missing: list[str] = []
    for name in job_names:
        if name in literals:
            resolved[name] = literals[name]
            continue
        if not has_factories:  # nothing to render; only literal jobs exist
            missing.append(name)
            continue
        if all_jobs is None:
            all_jobs = enumerate_jobs(config, pipelines)
        if name in all_jobs:
            resolved[name] = all_jobs[name]
        else:
            missing.append(name)

    if missing:
        available = sorted(all_jobs if all_jobs is not None else literals)
        raise ValueError(
            f"Job(s) not found in config: {', '.join(sorted(missing))}. Available jobs: {', '.join(available)}"
        )
    return resolved


def expand_job_factories(config: KedroDagsterConfig, pipelines: Mapping[str, Any] | None = None) -> KedroDagsterConfig:
    """Expand factory ``jobs`` keys into concrete jobs, once, before translation.

    Returns *config* unchanged when it declares no factory keys (expansion is a
    no-op for the common case). Otherwise returns a copy whose ``jobs`` are the
    concrete jobs from :func:`enumerate_jobs` (rendered factory jobs plus literal
    jobs), so every downstream consumer sees only concrete jobs.

    Parameters
    ----------
    config : KedroDagsterConfig
        Parsed Kedro-Dagster configuration, possibly containing factory keys.
    pipelines : Mapping[str, Any] or None, optional
        Kedro pipeline registry used to derive bindings. Defaults to the global
        registry when ``None``.

    Returns
    -------
    KedroDagsterConfig
        Configuration whose ``jobs`` contain no ``{placeholder}`` keys.

    See Also
    --------
    `kedro_dagster.factory.enumerate_jobs` :
        Renders the concrete job set consumed here.
    `kedro_dagster.translator.KedroProjectTranslator.to_dagster` :
        Calls this immediately after loading the configuration.
    """
    if not any(is_factory(key) for key in (config.jobs or {})):
        return config
    return config.model_copy(update={"jobs": enumerate_jobs(config, pipelines)})

---
description: How to cite Kedro-Dagster, in plain text and in BibTeX.
---

# Citation

If you use Kedro-Dagster in work you publish, please cite it.

## Plain text

Guillaume Tauzin. Kedro-Dagster: Deploy Kedro projects to Dagster. https://github.com/stateful-y/kedro-dagster

## BibTeX

```bibtex
@software{kedro_dagster,
  author  = "Guillaume Tauzin",
  title   = "{Kedro-Dagster: Deploy Kedro projects to Dagster}",
  url     = "https://github.com/stateful-y/kedro-dagster",
  license = "Apache-2.0"
}
```

The entry carries no `year` and no `version` on purpose, for the same reason the
machine-readable file below carries no release date: either one is wrong as soon as
the next version ships. If your citation style needs them, add the year and the
version you actually used:

```text
  year    = "2026",
  version = "1.2.3",
```

The version you used is the one `pip show kedro_dagster` reports.

## Machine-readable metadata

The repository root carries a
[`CITATION.cff`](https://github.com/stateful-y/kedro-dagster/blob/main/CITATION.cff)
file. It is the same citation in the Citation File Format, which is what GitHub's
"Cite this repository" button, Zenodo, and most reference managers read. If your tool
can import that file, prefer it over copying from this page: it cannot fall out of
step with the repository.

## There is no DOI

No release of Kedro-Dagster has been deposited with a DOI-issuing archive, so
there is no DOI to cite. Cite the repository URL above instead. If that changes, the
`doi` field in `CITATION.cff` is where it will appear first.

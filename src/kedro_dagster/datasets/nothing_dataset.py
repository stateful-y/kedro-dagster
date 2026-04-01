"""A sentinel dataset representing no data for Dagster Nothing-typed assets."""

from typing import Any

from kedro.io.core import AbstractDataset

from kedro_dagster.constants import NOTHING_OUTPUT


class DagsterNothingDataset(AbstractDataset):
    """A Kedro dataset used to represent placeholder outputs.

    This dataset can be used in Kedro pipelines to signify that a node has
    completed its task without actually producing any tangible output. It is
    particularly useful for enforcing execution order in pipelines where
    certain nodes need to run after others without passing data.

    Parameters
    ----------
    metadata : dict[str, Any] or None, optional
        Optional metadata stored alongside the dataset.

    Examples
    --------
    >>> from kedro_dagster.datasets.nothing_dataset import DagsterNothingDataset
    >>> nothing_ds = DagsterNothingDataset(metadata={"info": "no output"})
    >>> data = nothing_ds.load()
    >>> print(data)
    __nothing__
    >>> nothing_ds.save(data)

    See Also
    --------
    `kedro_dagster.utils.is_nothing_asset_name` :
        Predicate that checks whether a catalog entry is this type.
    """

    def __init__(
        self,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()

        self._metadata = metadata or {}

    def load(self) -> str:
        """Return the nothing sentinel for every load.

        Returns
        -------
        str
            Always ``"__nothing__"``.
        """
        return NOTHING_OUTPUT

    def save(self, data: Any) -> None:
        """Do nothing when saving data.

        Parameters
        ----------
        data : Any
            Ignored.
        """
        # Intentionally do not persist anything
        pass

    def _exists(self) -> bool:
        """Always report that the dataset exists.

        Returns
        -------
        bool
            Always ``True``.
        """
        return True

    def _describe(self) -> dict[str, Any]:
        """Return a JSON-serializable description of the dataset.

        Returns
        -------
        dict[str, Any]
            Basic dataset type info.
        """
        return {"type": self.__class__.__name__}

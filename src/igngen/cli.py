from __future__ import annotations

"""IgnGen CLI entry — body assembled from chunk modules (transport split)."""

from . import _cli_chunk_0, _cli_chunk_1, _cli_chunk_2, _cli_chunk_3

_SRC = (
    _cli_chunk_0.CHUNK
    + _cli_chunk_1.CHUNK
    + _cli_chunk_2.CHUNK
    + _cli_chunk_3.CHUNK
)
_NS: dict = {"__name__": __name__, "__package__": __package__}
exec(_SRC, _NS)
main = _NS["main"]

if __name__ == "__main__":
    raise SystemExit(main())

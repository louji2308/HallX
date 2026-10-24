import socket
import sys

from hallx.curation import validate_export
from tests.support_curation import valid_export


def test_curation_no_toolkit_or_network(monkeypatch) -> None:
    loaded = {name.split(".")[0] for name in sys.modules}
    assert "curatorkit" not in loaded
    assert "aligntune" not in loaded
    assert "auditkit" not in loaded

    def forbidden(*args, **kwargs):
        raise AssertionError("curation validation must not use the network")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)

    config, records, sources, tokens, digest, tokenizer = valid_export()
    result = validate_export(
        config,
        records,
        sources,
        observed_total_tokens=tokens,
        observed_sha256=digest,
        observed_tokenizer_id=tokenizer,
    )
    assert result.passed

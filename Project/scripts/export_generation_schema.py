"""Export the model-owned generation schema.

The exported file must never contain character offsets: the server computes
them after quote resolution.
"""

from __future__ import annotations

import json
from pathlib import Path

from hallx.models import GenerationProofEnvelope

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    target = ROOT / "configs" / "proof_envelope_schema.json"
    schema = GenerationProofEnvelope.model_json_schema()
    target.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {target}")


if __name__ == "__main__":
    main()

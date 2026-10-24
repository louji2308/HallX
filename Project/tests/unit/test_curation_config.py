import pytest

from hallx.curation import IssueCode, load_config, validate_config
from tests.support_curation import (
    CONFIG_DIR,
    CONFIG_NAMES,
    GENERATOR_MODEL,
    JUDGE_MODEL,
    TASK_BY_NAME,
    construct_config,
    make_config,
)


def _codes(config) -> list[str]:
    return [issue.code for issue in validate_config(config)]


@pytest.mark.parametrize("name", CONFIG_NAMES)
def test_curation_configs_parse_and_load(name: str) -> None:
    config = load_config(CONFIG_DIR / f"train-{name}.json")
    assert config.mode.value == "fixture"
    assert config.task == TASK_BY_NAME[name]
    assert config.snapshot_id == "snap-fixture-train-v1"
    assert config.split_name == "train"
    assert config.generator_endpoint == "http://127.0.0.1:30000"
    assert config.judge_endpoint == "http://127.0.0.1:30001"
    assert config.generator_model == GENERATOR_MODEL
    assert config.judge_model == JUDGE_MODEL
    assert config.output_path.startswith("data/curation/fixture/")
    assert validate_config(config) == ()


def test_curation_rejects_shared_generator_judge() -> None:
    for judge_endpoint in (
        "http://127.0.0.1:30000",
        "http://localhost:30000",
        "http://[::1]:30000",
        "http://127.0.0.1:30000/",
    ):
        config = make_config(judge_endpoint=judge_endpoint)
        assert IssueCode.GEN_JUDGE_SAME_ENDPOINT in _codes(config)

    for judge_model in (
        "Qwen/Qwen3-4B-Instruct-2507",
        " qwen/qwen3-4b-instruct-2507 ",
    ):
        config = make_config(judge_model=judge_model)
        assert IssueCode.GEN_JUDGE_SAME_MODEL in _codes(config)


@pytest.mark.parametrize(
    "endpoint",
    (
        "https://127.0.0.1:30000",
        "http://127.0.0.1.evil.com:30000",
        "http://127.0.0.1@evil.com:30000",
        "http://127.0.0.1:30000/v1",
        "http://127.0.0.1:30000//",
        "http://127.0.0.1:30000?x=1",
        "http://127.0.0.1:30000#fragment",
        "http://127.0.0.1",
        "http://0.0.0.0:30000",
        "http://192.168.1.5:30000",
        "http://localhost.:30000",
        "http://[::2]:30000",
        "http://127.0.0.1:0",
        "http://127.0.0.1:99999",
        " http://127.0.0.1:30000",
    ),
)
def test_curation_rejects_non_loopback(endpoint: str) -> None:
    config = make_config(generator_endpoint=endpoint)
    assert IssueCode.NON_LOOPBACK_ENDPOINT in _codes(config)


def test_curation_config_failures() -> None:
    assert IssueCode.SPLIT_NOT_TRAIN in _codes(make_config(split_name="validation"))
    assert IssueCode.SPLIT_NOT_TRAIN in _codes(make_config(split_name="test_indomain"))

    for tolerance in (float("nan"), float("inf"), -0.1, 1.1):
        assert IssueCode.INVALID_BUDGET in _codes(make_config(token_tolerance=tolerance))

    assert IssueCode.INVALID_BUDGET in _codes(make_config(expected_examples=9))
    assert IssueCode.INVALID_BUDGET in _codes(
        make_config(expected_total_tokens=8 * 4096 + 1)
    )

    for field, value in (
        ("max_examples", 0),
        ("max_tokens", 0),
        ("expected_examples", 0),
        ("expected_total_tokens", -1),
    ):
        config = construct_config(**{field: value})
        assert IssueCode.INVALID_BUDGET in _codes(config)

    assert validate_config(make_config()) == ()

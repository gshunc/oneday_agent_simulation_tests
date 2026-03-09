import asyncio
import json

import doc_extraction.doc_to_scenarios as scenario_module


def write_cache(rows):
    with open("case_scenarios_cache.jsonl", "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def read_cache():
    with open("case_scenarios_cache.jsonl", "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_doc_to_scenarios_prunes_stale_cache_and_refreshes_case_numbers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_cache(
        [
            {
                "name": "stale",
                "description": "stale",
                "expected_diagnosis": "stale",
                "case_number": 1,
                "original_text": "stale text",
            },
            {
                "name": "cached",
                "description": "cached",
                "expected_diagnosis": "cached",
                "case_number": 2,
                "original_text": "keep text",
            },
        ]
    )

    monkeypatch.setattr(
        scenario_module,
        "extract_case_separated_docs",
        lambda: [(7, "keep text"), (8, "new text")],
    )

    async def fake_process_batch_async(cases, batch_size=10):
        assert cases == [(8, "new text")]
        return [
            (
                '{"name": "new"}',
                8,
                "new text",
                {
                    "name": "new",
                    "description": "new",
                    "expected_diagnosis": "new",
                },
            )
        ]

    monkeypatch.setattr(
        scenario_module,
        "process_batch_async",
        fake_process_batch_async,
    )

    scenarios = asyncio.run(scenario_module.doc_to_scenarios_async(retries=1))

    assert [scenario["case_number"] for scenario in scenarios] == [7, 8]
    assert {scenario["original_text"] for scenario in scenarios} == {"keep text", "new text"}
    assert {scenario["name"] for scenario in scenarios} == {"Case 7 - cached", "Case 8 - new"}

    cached_rows = read_cache()
    assert len(cached_rows) == 2
    assert {row["original_text"] for row in cached_rows} == {"keep text", "new text"}
    assert {row["case_number"] for row in cached_rows} == {7, 8}
    assert {row["name"] for row in cached_rows} == {"Case 7 - cached", "Case 8 - new"}


def test_doc_to_scenarios_updates_case_number_for_cache_hit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_cache(
        [
            {
                "name": "cached",
                "description": "cached",
                "expected_diagnosis": "cached",
                "case_number": 5,
                "original_text": "same text",
            }
        ]
    )

    monkeypatch.setattr(
        scenario_module,
        "extract_case_separated_docs",
        lambda: [(9, "same text")],
    )

    async def fail_if_called(cases, batch_size=10):
        raise AssertionError("process_batch_async should not run for a pure cache hit")

    monkeypatch.setattr(
        scenario_module,
        "process_batch_async",
        fail_if_called,
    )

    scenarios = asyncio.run(scenario_module.doc_to_scenarios_async(retries=1))

    assert len(scenarios) == 1
    assert scenarios[0]["case_number"] == 9
    assert scenarios[0]["name"] == "Case 9 - cached"

    cached_rows = read_cache()
    assert len(cached_rows) == 1
    assert cached_rows[0]["case_number"] == 9
    assert cached_rows[0]["name"] == "Case 9 - cached"

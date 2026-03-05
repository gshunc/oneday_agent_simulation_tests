from typing import TypedDict
import litellm
import json
import os
import asyncio
from doc_extraction import extract_case_separated_docs


class Scenario(TypedDict):
    """Type definition for test scenario data"""
    case_number: int
    name: str
    description: str
    original_text: str
    expected_diagnosis: str | None

def system_prompt() -> str:
    """
    Returns the system prompt for the GPT model.
    """
    return """
You convert medical case files into structured JSON test scenarios.

You will receive a raw, haphazardly formatted case. Return a single JSON object (no markdown fences, no surrounding text) with this schema:

{
  "name": string,
  "description": string,
  "expected_diagnosis": string or null
}

## Field definitions

**name**: A concise scenario title summarising the patient's age, sex, and chief complaint.
  - Format: "OneDay - <age> <sex> with <chief complaint and suspected condition>"
  - Example: "OneDay - 30-year-old woman with mild headache suspected tension headache"

**description**: A structured breakdown of the case with these sections, each on its own line:

  NURSE: <patient demographics, presenting symptoms, vitals, and any initial test results>
  ONEDAY_AGENT_QUESTIONS:
  - <Question>? (NURSE_RESPONSE: <answer>),
  - <Question>? (NURSE_RESPONSE: <answer>)
  ONEDAY_AGENT_RESPONSE: <the final diagnosis and explanation of next steps by the OneDay Agent>
  EXPECTED_DIAGNOSIS: <the expected diagnosis>

  Rules for the description:
  - Fix grammar and punctuation, but preserve ALL medical details exactly.
  - Every question-answer pair must use the "(NURSE_RESPONSE: ...)" format.
  - Include the ONEDAY_AGENT_RESPONSE section with the expected final diagnosis and next steps as described in the case.

**expected_diagnosis**: The diagnosis the agent should arrive at, or null if no diagnosis is specified.

## Extracting the diagnosis

IMPORTANT: expected_diagnosis should almost NEVER be null. Most cases have a diagnosis — you just need to find it.

1. If the case contains an explicit "Diagnosis:" line, use that value.
2. If there is no "Diagnosis:" line but there is an "Answer:" line, the Answer IS the diagnosis source. Extract the diagnosis from it:
   - "Answer: communicate and treat with ciprofloxacin page 9" → the diagnosis is the condition being treated (e.g. "Bloody diarrhea" or "Dysentery")
   - "Answer: treat as severe malaria, refer" → the diagnosis is "Severe malaria"
   - "Answer: give ORS and zinc, review in 5 days" → the diagnosis is "Acute diarrhoea with some dehydration" (or whatever the symptoms indicate)
   - The Answer line always implies a diagnosis — use the symptoms, treatment, and medical context to determine what condition is being diagnosed.
3. Only set expected_diagnosis to null if there is genuinely no Answer line AND no Diagnosis line AND no indication of what the condition is.

## Example

Input:
<CASE>
A 55 year old man with Blood pressure of 165 systolic who has a very mild headache but no other symptoms.
RDT for malaria was negative and his temperature was 36.8. What should I do next?
Questions - Has their blood pressure been tested before? (no) - Have you tested blood sugar as well to check for diabetes? (yes its 6.0 fasting) - Are they a smoker (no) Answer - With only one measurement high, there should be another test another day before starting medication, so ask them to come back Diagnosis: Tension headache OR no diagnosis
</CASE>

Output:
{
  "name": "OneDay - 55-year-old man with high blood pressure and mild headache suspected tension headache",
  "description": "NURSE: A 55-year-old man with blood pressure of 165 systolic who has a very mild headache but no other symptoms. RDT for malaria was negative and his temperature was 36.8.\\nONEDAY_AGENT_QUESTIONS:\\n- Has their blood pressure been tested before? (NURSE_RESPONSE: no)\\n- Have you tested blood sugar as well to check for diabetes? (NURSE_RESPONSE: yes, it's 6.0 fasting)\\n- Are they a smoker? (NURSE_RESPONSE: no)\\nONEDAY_AGENT_RESPONSE: With only one measurement high, there should be another test another day before starting medication, so ask them to come back.\\nEXPECTED_DIAGNOSIS: Tension headache OR no diagnosis",
  "expected_diagnosis": "Tension headache OR no diagnosis"
}

Example 2 (Answer line, no Diagnosis line):

Input:
<CASE>
Case 12
A 4 year old child with loose mucoid diarrhoea for 5 days, fever 2 days, and abdominal cramps is drinking eagerly. Temperature 38.2 degree respiration 42 breath per minute no cough and flu no abdominal tenderness.
Questions
- Any danger sign (no)
- Any other sign of dehydration (no)
- Malaria test (negative)
- Blood in the stool (yes)
Answer: communicate and treat with ciprofloxacin page 9
</CASE>

Output:
{
  "name": "OneDay - 4-year-old child with bloody diarrhea and fever suspected dysentery",
  "description": "NURSE: A 4-year-old child with loose mucoid diarrhoea for 5 days, fever for 2 days, and abdominal cramps. The child is drinking eagerly. Temperature 38.2°C, respiration 42 breaths per minute, no cough or flu, no abdominal tenderness.\\nONEDAY_AGENT_QUESTIONS:\\n- Any danger signs? (NURSE_RESPONSE: no)\\n- Any other signs of dehydration? (NURSE_RESPONSE: no)\\n- Malaria test result? (NURSE_RESPONSE: negative)\\n- Blood in the stool? (NURSE_RESPONSE: yes)\\nONEDAY_AGENT_RESPONSE: Communicate and treat with ciprofloxacin.\\nEXPECTED_DIAGNOSIS: Bloody diarrhea (dysentery)",
  "expected_diagnosis": "Bloody diarrhea (dysentery)"
}

Return ONLY the raw JSON object. No markdown code fences, no explanation, no extra text.
"""

async def format_case_async(case_num: int, case_text: str) -> tuple[str, int, str]:
    """
    Formats the case using async LLM call.
    Returns tuple of (formatted_case, case_num, original_case_text).
    """
    _system_prompt = system_prompt()
    response = await litellm.acompletion(
        model="gpt-5-nano",
        messages=[
            {"role": "system", "content": _system_prompt},
            {"role": "user", "content": case_text}
        ]
    )
    return response.choices[0].message.content, case_num, case_text


def check_json(response: str, case_index: int = 0) -> dict | None:
    """
    Checks if the response is valid JSON.
    Returns the json object if the response is valid JSON, None otherwise.
    Strips markdown code fences if present.
    """
    text = response.strip()
    if text.startswith("```"):
        # Remove opening fence (with optional language tag) and closing fence
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            result = result[0]
        return result
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse JSON for case {case_index}: {e}")
        print(f"Response was: {response[:200]}...")
        return None

async def process_batch_async(cases: list[tuple[int, str]], batch_size: int = 10) -> list[tuple[str | None, int, str, dict | None]]:
    """
    Process cases in batches to avoid overwhelming the API.
    Returns list of (formatted_case, case_num, original_case_text, parsed_scenario).
    """
    results = []
    
    for i in range(0, len(cases), batch_size):
        batch = cases[i:i+batch_size]
        
        tasks = [format_case_async(case_num, case_text) for case_num, case_text in batch]
        
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in batch_results:
            if isinstance(result, Exception):
                print(f"Error processing case: {result}")
                results.append((None, -1, "", None))
            else:
                formatted_case, case_num, original_case_text = result
                print(f"Processed case number: {case_num} (/{len(cases)} total)")
                checked = check_json(formatted_case, case_num)
                if checked and not checked.get("expected_diagnosis"):
                    print(f"Warning: Case {case_num} has null/missing expected_diagnosis, will retry. Response: {formatted_case[:200]}...")
                    checked = None  # Force retry
                results.append((formatted_case, case_num, original_case_text, checked))
    
    return results

async def doc_to_scenarios_async(retries: int = 2, batch_size: int = 10) -> list[Scenario]:
    """
    Converts the docs file into a list of test scenarios using gpt-5-nano.
    Processes cases in parallel batches for faster execution.
    """
    cached_cases = {}
    cache_file = 'case_scenarios_cache.jsonl'
    
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            for line in f:
                if line.strip():
                    scenario = json.loads(line)
                    if 'original_text' in scenario:
                        cached_cases[scenario['original_text']] = scenario

    cached_count = len(cached_cases)

    case_separated = extract_case_separated_docs()
    total_cases = len(case_separated)
    
    # Start scenarios list with cached cases that match current cases
    scenarios = [cached_cases[case_text] for case_num, case_text in case_separated if case_text in cached_cases]
    
    # Filter out cached cases from cases to process
    case_separated = [(case_num, case_text) for case_num, case_text in case_separated if case_text not in cached_cases]
    print(f"Total cases extracted from Google Doc: {total_cases}")
    print(f"Number of cases found in cache: {cached_count}")
    print(f"Cache hits: {total_cases - len(case_separated)}")
    print(f"Cases to process: {len(case_separated)}")
    
    failed_cases = []

    # is there a good way to make sure that cases which are _basically_ the same are not processed twice other than embedding and checking similarity?
    for r in range(retries):
        if len(failed_cases) > 0:
            print(f"Retrying {len(failed_cases)} failed cases...")
        cases_to_process = case_separated if r == 0 else failed_cases
        if not cases_to_process:
            break
            
        failed_cases = []
        
        results = await process_batch_async(cases_to_process, batch_size=batch_size)
        
        # Collect results
        for formatted_case, case_num, original_case_text, checked_scenario in results:
            if checked_scenario:
                checked_scenario['case_number'] = case_num
                checked_scenario['original_text'] = original_case_text
                cached_cases[original_case_text] = checked_scenario
                scenarios.append(checked_scenario)
            elif original_case_text:
                failed_cases.append((case_num, original_case_text))
    
    with open(cache_file, 'w') as f:
        for scenario in cached_cases.values():
            f.write(json.dumps(scenario) + '\n')

    print(f"Added {len(cached_cases) - cached_count} new cases to cache.")
    print(f"Total cases processed: {len(scenarios)}")

    # Sort by case_number to ensure deterministic test collection
    scenarios.sort(key=lambda s: s['case_number'])
    
    return scenarios

def doc_to_scenarios(retries: int = 2, batch_size: int = 10) -> list[Scenario]:
    """
    Converts the docs file into a list of test scenarios using gpt-5-nano.
    Synchronous wrapper for the async implementation.
    
    Args:
        retries: Number of retry attempts for failed cases
        batch_size: Number of cases to process concurrently in each batch (default: 10)
    
    Returns:
        List of formatted test scenarios
    """
    return asyncio.run(doc_to_scenarios_async(retries=retries, batch_size=batch_size))

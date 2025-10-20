from typing import TypedDict
import litellm
import json
import os
from doc_extraction import extract_case_separated_docs


class TestScenario(TypedDict):
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
    You are a helpful assistant that converts a docs file into a list of test scenarios. You will be given a string that represents a medical case file.

    You are tasked with taking this haphazardly formatted text and converting it into a test scenario, formatted in JSON, and with the following schema:

    {
        "case_number": int,
        "name": str,
        "description": str,
        "original_text": str,
        "expected_diagnosis": str | None
    }

    Field descriptions:
    - case_number: Sequential number starting from 1, derived from the case labels in the doc
    - name: A short, descriptive title for the test scenario based on the patient's main condition
    - description: A formatted breakdown with these sections:
        NURSE: <patient's symptoms and initial information>
        AGENT_QUESTIONS: <list of questions with expected nurse responses in format: - Question? (NURSE_RESPONSE: answer)>
        AGENT_ANSWER: <the agent's diagnostic answer>
        DIAGNOSIS: <the expected diagnosis>
    - original_text: The exact, unmodified text you received (verbatim copy of input)
    - expected_diagnosis: The diagnosis the agent should provide, or null if none specified

    Important: 
    - original_text MUST be an exact copy of the input text you received
    - description should fix grammar/punctuation but preserve all medical details
    - Use "NURSE_RESPONSE:" format in AGENT_QUESTIONS section

    Here is an example of a test scenario, unformatted, and the JSON that should be returned:
    <CASE>
    Case 1) A 55 year old man with Blood pressure of 165 systolic who has a very mild headache but no other symptoms. 
    RDT for malaria was negative and his temperature was 36.8. What should I do next? 
    Questions - Has their blood pressure been tested before? (no) - Have you tested blood sugar as well to check for diabetes? (yes its 6.0 fasting) - Are they a smoker (no) Answer - With only one measurement high, there should be another test another day before starting medication, so ask them to come back (this isn’t necessarily so clear in the guidelines actually0 Diagnosis: Tension headache OR no diagnosis
    </CASE>

    <JSON>
    {
        "case_number": 1,
        "name": "A 55 year old man with Blood pressure of 165 systolic who has a very mild headache but no other symptoms",
        "description": "NURSE: A 55 year old man with Blood pressure of 165 systolic who has a very mild headache but no other symptoms. RDT for malaria was negative and his temperature was 36.8. What should I do next? AGENT_QUESTIONS: - Has their blood pressure been tested before? (NURSE_RESPONSE: no) - Have you tested blood sugar as well to check for diabetes? (NURSE_RESPONSE: yes its 6.0 fasting) - Are they a smoker (NURSE_RESPONSE: no) AGENT_ANSWER: - With only one measurement high, there should be another test another day before starting medication, so ask them to come back. DIAGNOSIS: Tension headache OR no diagnosis",
        "original_text": "Case 1) A 55 year old man with Blood pressure of 165 systolic who has a very mild headache but no other symptoms. RDT for malaria was negative and his temperature was 36.8. What should I do next? Questions - Has their blood pressure been tested before? (no) - Have you tested blood sugar as well to check for diabetes? (yes its 6.0 fasting) - Are they a smoker (no) Answer - With only one measurement high, there should be another test another day before starting medication, so ask them to come back (this isn’t necessarily so clear in the guidelines actually0 Diagnosis: Tension headache OR no diagnosis",
        "expected_diagnosis": "Tension headache OR no diagnosis"
    }
    </JSON>

    Return only the JSON, no other text or formatting.
    """

def format_case(case: str) -> str:
    """
    Formats the case using LLM call.
    Returns the formatted case as a string.
    """
    _system_prompt = system_prompt()
    response = litellm.completion(
        model="gpt5-nano",
        messages=[
            {"role": "system", "content": _system_prompt},
            {"role": "user", "content": case}
        ]
    )
    return response.choices[0].message.content

def check_json(response: str, case_index: int = 0) -> dict | None:
    """
    Checks if the response is valid JSON.
    Returns the json object if the response is valid JSON, None otherwise.
    """
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        print(f"⚠ Warning: Failed to parse JSON for case {case_index}: {e}")
        print(f"  Response was: {response[:200]}...")
        return None

# TODO: Test that the response is valid JSON and read a sample of the scenarios to ensure they are valid.
def doc_to_scenarios(retries = 1) -> list[TestScenario]:
    """
    Converts the docs file into a list of test scenarios using gpt5-nano.
    """

    cached_cases = {}
    cache_file = 'case_scenarios_cache.jsonl'
    
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            for line in f:
                if line.strip():
                    scenario = json.loads(line)
                    # Use original_text as key if it exists
                    if 'original_text' in scenario:
                        cached_cases[scenario['original_text']] = scenario

    cached_count = len(cached_cases)
    if cached_count > 0:
        print(f"Loaded {cached_count} cached cases from file.")
    else:
        print("No cached cases found, all cases will be processed from scratch.")

    case_separated = extract_case_separated_docs()
    scenarios = []

    # is there a good way to make sure that cases which are _basically_ the same are not processed twice other than embedding and checking similarity?

    for r in range(retries):
        failed_cases = []
        cases_to_process = case_separated if r == 0 else failed_cases
        
        for i, case in enumerate(cases_to_process):
            if case in cached_cases:
                scenarios.append(cached_cases[case])
                continue

            formatted_case = format_case(case)
            checked_scenario = check_json(formatted_case, i+1)

            if checked_scenario:
                # Add original_text for caching
                checked_scenario['original_text'] = case
                cached_cases[case] = checked_scenario
                scenarios.append(checked_scenario)
            elif r < retries - 1:
                failed_cases.append(case)
    
    with open(cache_file, 'w') as f:
        for scenario in cached_cases.values():
            f.write(json.dumps(scenario) + '\n')
    
    print(f"Added {len(cached_cases) - cached_count} new cases to cache.")
    print(f"Total cases processed: {len(scenarios)}")

    return scenarios


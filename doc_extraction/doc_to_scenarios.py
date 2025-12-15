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
    You are a helpful assistant that converts a docs file into a list of test scenarios. You will be given a string that represents a medical case file.

    You are tasked with taking this haphazardly formatted text and converting it into a test scenario, formatted in JSON, and with the following schema:

    {
        "name": str,
        "description": str,
        "expected_diagnosis": str | None
    }

    Field descriptions:
    - name: A short, descriptive title for the test scenario based on the patient's main condition
    - description: A formatted breakdown with these sections:
        NURSE: <patient's symptoms and initial information>
        AGENT_QUESTIONS: <list of questions with expected nurse responses in format: - Question? (NURSE_RESPONSE: answer)>
        AGENT_ANSWER: <the agent's diagnostic answer>
        DIAGNOSIS: <the expected diagnosis>
    - expected_diagnosis: The diagnosis the agent should provide, or null if none specified

    Important: 
    - description should fix grammar/punctuation but preserve all medical details
    - Use "NURSE_RESPONSE:" format in AGENT_QUESTIONS section
    - Sometimes the case will be given in a format this like as follows:
    <CASE>
    Case 12
    A 4 year old child with loose mucoid diarrhoea for 5days, fever 2  days, and abdominal cramps is drinking eagerly. Temperature 38.2 degree respiration 42 breath per minute no cough and flu no abdominal tenderness.
    Questions
    - Any danger sign (no)
    - Any other sign of dehydration (no)
    - Malaria test (negative)
    - Blood in the stool (yes)
    Answer: communicate and treat with ciprofloxacin page 9
    </CASE>
    In this case, where we just see Answer and the word diagnosis is not present, you should extract the diagnosis from the Answer line.

    Here is an example of a test scenario, unformatted, and the JSON that should be returned:
    <CASE>
    A 55 year old man with Blood pressure of 165 systolic who has a very mild headache but no other symptoms. 
    RDT for malaria was negative and his temperature was 36.8. What should I do next? 
    Questions - Has their blood pressure been tested before? (no) - Have you tested blood sugar as well to check for diabetes? (yes its 6.0 fasting) - Are they a smoker (no) Answer - With only one measurement high, there should be another test another day before starting medication, so ask them to come back (this isn't necessarily so clear in the guidelines actually0 Diagnosis: Tension headache OR no diagnosis
    </CASE>

    <JSON>
    {
        "name": "A 55 year old man with Blood pressure of 165 systolic who has a very mild headache but no other symptoms",
        "description": "NURSE: A 55 year old man with Blood pressure of 165 systolic who has a very mild headache but no other symptoms. RDT for malaria was negative and his temperature was 36.8. What should I do next? AGENT_QUESTIONS: - Has their blood pressure been tested before? (NURSE_RESPONSE: no) - Have you tested blood sugar as well to check for diabetes? (NURSE_RESPONSE: yes its 6.0 fasting) - Are they a smoker (NURSE_RESPONSE: no) AGENT_ANSWER: - With only one measurement high, there should be another test another day before starting medication, so ask them to come back. DIAGNOSIS: Tension headache OR no diagnosis",
        "expected_diagnosis": "Tension headache OR no diagnosis"
    }
    </JSON>

    Return only the JSON, no other text or formatting.
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
    """
    try:
        result = json.loads(response)
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

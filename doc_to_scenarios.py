from typing import TypedDict
import litellm
import json
from doc_extraction import extract_case_separated_docs


class TestScenario(TypedDict):
    """Type definition for test scenario data"""
    case_number: int
    name: str
    description: str
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
        "expected_diagnosis": str | None
    }

    The case_number is a sequential number starting from 1, which should be derived from the labels of the cases in the doc.
    The name is a short description of the test scenario, which you should come up with based on the content of the case.
    The description is a step by step breakdown of the test scenario. This should include the patient's symptoms, the list of questions formatted as a list of string, and the expected diagnosis.
    The description should be formatted as follows:

    NURSE: <patient's symptoms>
    AGENT_QUESTIONS: <list of questions, including the expected response from the nurse>
    AGENT_ANSWER: <agent's answer>
    DIAGNOSIS: <expected diagnosis>

    The expected diagnosis is the diagnosis that you expect the agent to provide based on the content of the case. Sometimes there is no expected diagnosis listed. In that case, ensure that you provide None.
    You should seek to provide a verbatim reproduction of the case, but fixing grammar and punctuation errors.

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
        "expected_diagnosis": "Tension headache OR no diagnosis"
    }
    </JSON>

    Return only the JSON, no other text or formatting.
    """

def doc_to_scenarios(doc_text: str) -> list[TestScenario]:
    """
    Converts the docs file into a list of test scenarios using gpt5-nano.
    """
    case_separated = extract_case_separated_docs()
    system_prompt = system_prompt()
    scenarios = []

    for case in case_separated:
        response = litellm.completion(
            model="gpt5-nano",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": case}
            ]
        ).choices[0].message.content
        scenarios.append(json.loads(response.choices[0].message.content))

    return scenarios
import pytest
import scenario
import litellm
litellm.drop_params = True  # Ignore params models don't support
from dotenv import load_dotenv
from typing import TypedDict
load_dotenv()


class Scenario(TypedDict):
    """Type definition for test scenario data"""
    case_number: int
    name: str
    description: str
    original_text: str
    expected_diagnosis: str | None

def oneday_guidelines() -> str:
    """Returns the content of the oneday_guidelines.md file."""
    import os

    current_dir = os.path.dirname(os.path.abspath(__file__))
    guidelines_path = os.path.join(current_dir, "oneday_guidelines.md")

    with open(guidelines_path, "r", encoding="utf-8") as f:
        return f.read()


def oneday_system_prompt() -> str:
    """Returns the OneDay Agent system prompt exactly as it is in Turn.io internally"""
    system_prompt = f"""
        You help nurses diagnose patients exclusively following the diagnostic guidelines outlined below:

        <GUIDELINES>
        {oneday_guidelines()}
        </GUIDELINES>

        ## Instructions

        Ask the nurse to report the patient symptoms and ask followup questions to reach one
        of the diagnoses present in the provided guidelines. The guidelines contain steps and decision trees that will help
        you deduct followup questions.

        DO NOT ask too many questions in the same message, start with the most important 1-2 questions, then wait for the nurse's reply,
        then asks 1-2 more followup questions if necessary, wait for the reply, and so on.

        Don't ask the same questions again if the nurse already provided the information you need during the conversation.

        GOAL: you goal is to form a diagnosis as soon as possible but don't skip important questions if needed to confidently reach one
        of the diagnoses from the guidelines. Once you are sure about the diagnosis, report the diagnosis and the treatments exactly as it is in the
        provided guidelines and stop asking questions.

        DO NOT continue asking questions once you have sufficient information to make a confident diagnosis

        Only follow the provided guidelines. If the reported symptoms don't match any diagnosis in the guidelines
        with high accuracy even after having asked followup questions, then say so and reccomend an hospital visit.

        If the nurse hasn't interacted with you yet, greet them and ask what symptoms the patient is presenting.

        ## Conversation ending criteria
        When providing the final diagnosis and treatment plan, you MUST add the special tag "<END>" at the end of your response to conclude the session.

        Append the special tag "<END>" at the end of your message when you have given the final diagnosis providing:
        1. A specific diagnosis from the guidelines
        2. Complete treatment instructions
        3. Medication dosages and duration
        4. Communication points for the patient

        ALSO END the conversation if you determine the symptoms don't match any guideline diagnosis and recommend hospital referral

        ## Reply format
        It is of the upmost importance that everything you say, diagnose, and ask strictly follows the provided guidelines: for that reason
        you always must return a very short but clear explanation of what you referred from the guidelines contains inside a special
        <EXPLANATION>your explanation here</EXPLANATION> tag at the end of your response.

        ### WhatsApp Message Formatting
        Your messages will be sent via WhatsApp. Follow these formatting guidelines (1,600 character limit per message):

        Supported Formatting:
        - Bold: Use *single asterisks* (NOT **double**). Example: This is a *bold* word
        - Italic: Use _underscores_. Example: This is an _italic_ word
        - Strike-through: Use ~tildes~. Example: This is a ~crossed out~ word
        - Monospace: Use ```triple backticks```. Example: This is ```monospace``` text
        - Inline code: Use `single backticks`. Example: Use the `code` command
        - Bulleted list: Start lines with -. Example:
        - First item
        - Second item
        - Block quote: Start lines with >. Example: > This is a quote

        CRITICAL FORMATTING RULES:
        1. Add spaces BEFORE and AFTER special characters when formatting mid-sentence
            ✓ Correct: "This is a *bold* word in a sentence"
            ✗ Wrong: "This is a*bold*word in a sentence"
        2. Use SINGLE asterisks (*) for bold, never double (**)
        3. Keep messages under 1,600 characters
        4. Format naturally - don't over-format or it looks unprofessional

        ### Example of conversation
        Here is a minimal example of a conversation just for you to understand the format:

        Human (nurse): I am visiting a 4yo male child with cough
        Asisstant (you): I see... does the child have *fever*? <EXPLANATION>I asked if the child has a fever because the guidelines say...</EXPLANATION>
        Human (nurse): No, the kid doesn't have a fever
        Assistant (you): Ok, thanks for checking that. The _diagnosis_ is X, treatment is Y, communicate Z to the patiend <EXPLANATION>I provided the X diagnoses because the guidelines say that...</EXPLANATION> <END>

        Your message will be delivered over whatsapp, so keep it short and direct. You can use newlines, bullet points and basic whatsapp markdown like *bold*, _italic_ and emojis.

        If you detect the human wants to end the conversation (e.g. human says "that'd be all", "tahnks", "that's all", "please exit", etc.) insert at the end of your reply the speical keyword tag `<END>`
        so that our system can detect the exit intent and redirect the nurse to the main menu afterwards.
    """
    return system_prompt


def oneday_judge_prompt(scenario_description: str, criteria: list[str]) -> str:
    """Returns the judge prompt for evaluating OneDay agent performance in scenarios."""
    return f"""
      <role>
      You are an LLM as a judge watching a simulated conversation as it plays out live to determine if the agent under test meets the criteria or not.
      </role>

      The agent under test helps nurses make medical diagnosis strictly following the OneDay medical guidelines, which are reported below:

      <one_day_guidelines>
      {oneday_guidelines()}
      </one_day_guidelines>

      <goal>
      Your goal is to determine if you already have enough information to make a verdict of the scenario below, or if the conversation should continue for longer.
      If you do have enough information or it is clear that the test should continue based on the previous response and criteria, use the continue_test tool to continue the conversation. If you are certain that the agent has made a fatal mistake or alternatively has correctly, directly provided the diagnosis, use the finish_test tool to end the test.
      We expect to see a full turn-by-turn conversation between the agent and the user. You should only end the test when you're unequivocally certain that the test needs to end and that the agent will never get to the right answer.
      </goal>

      <scenario>
      {scenario_description}
      If the user doesn't follow the script, you should make note of this and report it as a failure. 
      It's very important that the agent asks all of the follow up questions until they have enough information to make the diagnosis. This means not prematurely ending the test!
      </scenario>

      <criteria>
      {"\n".join(criteria)}
      </criteria>

      <rules>
      - DO NOT make any judgment calls that are not explicitly listed in the success or failure criteria, withhold judgement if necessary.
      - Don't count the <EXPLANATION> tag as the diagnosis. You should not simply look at the words of the agent, but ensure that they agent actually directly provides a definitive diagnosis.
      - Only award points for diagnonsis if the agent has correctly, directly provided the diagnosis.
      </rules>
    """


@scenario.cache()
def generate_oneday_agent_response(messages, model: str) -> scenario.AgentReturnTypes:
    response = litellm.completion(
        model=model,
        messages=[
            {
                "role": "system",
                "content": oneday_system_prompt(),
            },
            *messages,
        ],
    )
    return response.choices[0].message


class OneDayAgentAdapter(scenario.AgentAdapter):
    """Provides the scenario agent adapter for the OneDay workflow"""
    def __init__(self, model: str):
        self.model = model

    async def call(self, input: scenario.AgentInput) -> scenario.AgentReturnTypes:
        return generate_oneday_agent_response(input.messages, self.model)


async def run_oneday_scenario(test_scenario: Scenario, testrun_uid: str, model_id: str, strict: bool = False):
    """
    Shared helper that runs a OneDay agent scenario test.

    Args:
        test_scenario: The scenario data containing description, expected diagnosis, etc.
        testrun_uid: Unique identifier for the test run.
        model_id: The litellm model ID to use for the agent.
        strict: If True, adds criteria requiring correct follow-up questions.
    """
    description = test_scenario["description"]
    expected_diagnosis = test_scenario["expected_diagnosis"]
    test_name = test_scenario["name"]

    criteria = [
        "Agent provides accurate information closely following the OneDay medical guidelines",
        "Agent doesn't ask for the same information multiple times",
    ]

    if strict:
        criteria.append("Agent asks correct follow-up questions according to the OneDay medical guidelines")

    if expected_diagnosis:
        criteria.append(f"Agent provides the following diagnosis from the OneDay guidelines: {expected_diagnosis}")

    result = await scenario.run(
        name=f"OneDay - {test_name}",
        description=description,
        agents=[
            OneDayAgentAdapter(model_id),
            scenario.UserSimulatorAgent(),
            scenario.JudgeAgent(
                criteria=criteria,
                model="gpt-5",
                system_prompt=oneday_judge_prompt(description, criteria)
            )
        ],
        set_id=testrun_uid
    )

    assert result.success


@pytest.mark.agent_test
@pytest.mark.asyncio
async def test_oneday_agent_standard(test_scenario: Scenario, testrun_uid: str, model_id: str):
    """Standard test for OneDay agent diagnostic scenarios."""
    await run_oneday_scenario(test_scenario, testrun_uid, model_id, strict=False)


@pytest.mark.agent_test
@pytest.mark.asyncio
async def test_oneday_agent_strict(test_scenario: Scenario, testrun_uid: str, model_id: str):
    """
    Strict test for OneDay agent diagnostic scenarios.
    Requires the agent to ask exactly the follow-up questions specified in the scenario and guidelines.
    """
    await run_oneday_scenario(test_scenario, testrun_uid, model_id, strict=True)
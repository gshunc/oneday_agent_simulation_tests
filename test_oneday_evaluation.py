import os
import pytest
import scenario
import litellm
import requests
import datetime

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

  GOAL: you goal is to a diagnosis as soon as possible but don't skip important questions if needed to confidently reach one
  of the diagnoses from the guidelines. Once you are sure about the diagnosis, report the diagnosis and the treatments exactly as it is in the
  provided guidelines and stop asking questions.

  DO NOT continue asking questions once you have sufficient information to make a confident diagnosis

  CRITICAL!! Only follow the provided guidelines. If the reported symptoms don't match any diagnosis in the guidelines
  with high accuracy even after having asked followup questions, then always say so and reccomend an hospital visit.

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
  It is of the upmost importnace that everything you say and diagnose and ask stricly follows the provided guidelines: for that reason
  you always must return a very short but clear exaplanation of what you referred from the guidelines containes inside a special
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
      The agent under test helps nurses make medical diagnosis strictly following the OneDay medical guidelines, which are reported below:
      </role>

      <one_day_guidelines>
      {oneday_guidelines()}
      </one_day_guidelines>

      <goal>
      Your goal is to determine whether the agent under test has explicitly stated a final diagnosis or whether the conversation should continue.

      Use the continue_test tool by default. Only call finish_test when ALL of the following are true:
        1. The agent's message contains the literal tag <END> — this is the agent's own signal that it has concluded the conversation.
        2. The agent has stated a specific diagnosis using an explicit diagnostic frame (e.g. "The diagnosis is X", "Diagnosis: X", "Diagnosis: possible X", "This sounds like X", "This is X") — bare suspicions like "I think it might be X" do not qualify.
        3. The agent has provided complete treatment instructions alongside the diagnosis.

      If ANY of these three conditions is not met, you MUST call continue_test. Do not call finish_test early.
      When in doubt, always continue the test. Err heavily on the side of letting the conversation play out.
      </goal>

      <scenario>
      {scenario_description}
      If the user doesn't follow the script, you should make note of this and report it as a failure.
      It is critical that the agent asks all necessary follow-up questions before arriving at a diagnosis. Do NOT end the test prematurely — let the agent gather information and reach its own conclusion. The test should only end once a definitive diagnosis has been stated.
      </scenario>

      <criteria>
      {"\n".join(criteria)}
      </criteria>

      <rules>
      - DO NOT make any judgment calls that are not explicitly listed in the success or failure criteria. Withhold judgement if necessary.
      - Do NOT count the <EXPLANATION> tag as a diagnosis and do not confuse the case information given to you with the actual output of the model.
      - NEVER call finish_test unless the agent's message contains the literal string <END>. No <END> tag = call continue_test, no exceptions.
      - A diagnosis MUST be an explicit, committed statement. The agent must outright declare the diagnosis using a clear diagnostic frame such as "The diagnosis is X", "Diagnosis: X", "Based on the symptoms, the diagnosis is X", or "This sounds like X".
      - Exception: if the agent uses an explicit diagnostic label (e.g. "Diagnosis: possible X" or "The likely diagnosis is X"), hedged qualifiers like "possible" or "likely" within that framing DO count as a valid diagnosis. What matters is the explicit diagnostic frame, not the absence of every qualifier.
      - Hedged language WITHOUT a diagnostic frame does NOT qualify — e.g. "I suspect X", "this could be X", or "X is a possibility" on their own are not a diagnosis.
      - Only award points for diagnosis if the agent has stated the correct diagnosis using the above criteria, not merely mentioned it in passing or as one of several possibilities.
      - If the agent has not yet committed to a diagnosis, continue the test regardless of how much information has been exchanged.
      - The user's very first message will be a plain "Hello" with no symptom information. This is intentional and must NOT be treated as a failure to follow the script.
      </rules>

      <NOTE>
      If a diagnosis has already been given in the conversation AND the agent's current message offers to send, share, or provide a document, checklist, PDF, report, or any written resource — treat this as a conversation end state and call finish_test immediately, even if the message does not contain <END>.
      </NOTE>

      <NOTE>
      If the agent sends:
      "Did I do well?

      Exclusively reply with one of the following options: ✅ Yes, ❌ No, 💬 Continue chat

      Please only reply with the exact word. Do not use any other words or phrases."
      This is an ending condition which should constitute the end of a run. If at this poiint no diagnosis has been given, the conversation is a failure and you should call the finish_test tool.
      </NOTE>
    """


def generate_oneday_agent_response(messages, model: str, turn: bool = False, simulation_id: str = "", turn_uuid: str | None = ""):
    if turn:
        turn_key = os.getenv("TURN_API_KEY")
        user_input = messages[-1]["content"] if messages else ""
        response = requests.post(
            f"https://whatsapp.turn.io/v1/journeys/{turn_uuid}/simulation",
            headers={
                "Authorization": f"Bearer {turn_key}",
                "Content-Type": "application/json",
            },
            json={
                "simulation_id": f"{simulation_id}",
                "revision": "staging",
                "contact": {
                    "name": "Test User",
                    "language": "eng",
                },
                "input": user_input,
            },
        )
        if not response.ok:
            # Turn.io returns 500 when the journey has already ended and receives
            # an unexpected user message (e.g. the UserSimulator sends one more
            # turn after the agent emitted <END>). Treat this as a graceful
            # conversation end rather than a hard failure.
            if response.status_code == 500 and "unexpectedly received user input" in response.text:
                return {"role": "assistant", "content": "<END>"}
            raise RuntimeError(f"Turn API error {response.status_code}: {response.text[:500]}")
        message = response.json()["message"]

    else:
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

        message = response.choices[0].message #type: ignore

    return message #type: ignore

class OneDayAgentAdapter(scenario.AgentAdapter):
    """Provides the scenario agent adapter for the OneDay workflow"""
    def __init__(self, model: str, simulation_id: str, turn: bool, turn_uuid: str | None):
        self.model = model
        self.turn = turn
        self.simulation_id = simulation_id
        self.turn_uuid = turn_uuid

    async def call(self, input: scenario.AgentInput) -> scenario.AgentReturnTypes:
        if self.turn and not self.turn_uuid:
            raise ValueError("Cannot call turn without an associated uuid.")
        
        message = generate_oneday_agent_response(input.messages, self.model, turn = self.turn, simulation_id = self.simulation_id, turn_uuid = self.turn_uuid)
        return message # type: ignore[return-value]


async def run_oneday_scenario(test_scenario: Scenario, testrun_uid: str, model_id: str, diagnosis_only: bool = False, use_turn: bool = False, turn_uuid: str | None = None, request=None):
    """
    Shared helper that runs a OneDay agent scenario test.

    Args:
        test_scenario: The scenario data containing description, expected diagnosis, etc.
        testrun_uid: Unique identifier for the test run.
        model_id: The litellm model ID to use for the agent.
        diagnosis_only: If True, only checks that the agent provides the correct diagnosis.
        use_turn: If True, use the Turn.io simulation API instead of calling the model directly.
        turn_uuid: Turn.io journey UUID. When provided it takes exclusive precedence over the
                   TURN_JOURNEY_UUID env var; when None the env var is used as a fallback.
    """
    description = (
        "IMPORTANT: Your FIRST message must be exactly 'Hello' and nothing else. "
        "Do not introduce the patient or any symptoms in your first message.\n\n"
        "IMPORTANT: You are roleplaying as a nurse. NEVER dump out the scenario description, "
        "question/answer pairs, or any structured data from your instructions. "
        "Instead, respond naturally to whatever the OneDay agent asks you, "
        "answering only what is asked using the scenario details as your source of truth.\n\n"
        "IMPORTANT: If the agent offers to send, share, or provide a document, checklist, PDF, "
        "report, or any written resource, do NOT engage with it. Simply say you are done and want "
        "to end the conversation.\n\n"
        + test_scenario["description"]
    )
    expected_diagnosis = test_scenario["expected_diagnosis"]
    test_name = test_scenario["name"]

    criteria = [
        "Agent provides accurate information closely following the OneDay medical guidelines",
        "Agent doesn't ask for the same information multiple times",
    ]

    if expected_diagnosis:
        criteria.append(f"Agent provides the following diagnosis from the OneDay guidelines: {expected_diagnosis}")

    if diagnosis_only:
        criteria = [f"Agent provides the following diagnosis from the OneDay guidelines: {expected_diagnosis}"]

    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resolved_turn_uuid = turn_uuid  # if turn_uuid is not None else os.getenv("TURN_JOURNEY_UUID")
    raw_simulation_id = f"OD{test_scenario['case_number']}-{time}"
    simulation_id = raw_simulation_id[:24].ljust(6, "0")
    agent = OneDayAgentAdapter(model_id, simulation_id=simulation_id, turn=use_turn, turn_uuid=resolved_turn_uuid)
    result = await scenario.run(
        name=f"OneDay - {test_name}",
        description=description,
        agents=[
            agent,
            scenario.UserSimulatorAgent(),
            scenario.JudgeAgent(
                criteria=criteria,
                model="gpt-5",
                system_prompt=oneday_judge_prompt(description, criteria)
            )
        ],
        set_id=testrun_uid
    )

    # Collect all unique trace_ids (one per turn); usage is computed in conftest post-run hook
    trace_ids = list(dict.fromkeys(
        tid for msg in result.messages if (tid := msg.get("trace_id"))
    ))

    if request is not None:
        request.node.user_properties.append(("total_time", result.total_time))
        request.node.user_properties.append(("agent_time", result.agent_time))
        request.node.user_properties.append(("trace_ids", ",".join(trace_ids)))
        if use_turn:
            # Turn API doesn't expose model info, so estimate only the Turn agent's token
            # contribution. Judge + UserSimulator tokens come from LangWatch (accurate).
            # 4/3 tokens per word is the industry-standard approximation for English text.
            def _word_count(msg):
                content = msg.get("content")
                return len(str(content).split()) if content else 0

            system_prompt_words = len(oneday_system_prompt().split())
            agent_prompt_words = system_prompt_words + sum(_word_count(m) for m in result.messages if m.get("role") == "user")
            agent_completion_words = sum(_word_count(m) for m in result.messages if m.get("role") == "assistant")
            request.node.user_properties.append(("turn_agent_prompt_tokens", round(agent_prompt_words * 4 / 3)))
            request.node.user_properties.append(("turn_agent_completion_tokens", round(agent_completion_words * 4 / 3)))

    assert result.success


@pytest.mark.agent_test
@pytest.mark.asyncio
async def test_oneday_agent_standard(test_scenario: Scenario, testrun_uid: str, model_id: str, use_turn: bool, turn_journey_uuid: str | None, request):
    """Standard test for OneDay agent diagnostic scenarios."""
    await run_oneday_scenario(test_scenario, testrun_uid, model_id, use_turn=use_turn, turn_uuid=turn_journey_uuid, request=request)


@pytest.mark.agent_test
@pytest.mark.asyncio
async def test_oneday_agent_diagnosis_only(test_scenario: Scenario, testrun_uid: str, model_id: str, use_turn: bool, turn_journey_uuid: str | None, request):
    """
    Test for OneDay agent diagnostic scenarios.
    Requires the agent to provide the correct diagnosis only.
    """
    await run_oneday_scenario(test_scenario, testrun_uid, model_id, diagnosis_only=True, use_turn=use_turn, turn_uuid=turn_journey_uuid, request=request)
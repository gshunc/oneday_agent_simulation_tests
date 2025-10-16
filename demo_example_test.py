# Demo Test of how to write a Scenario simulation test
# from https://scenario.langwatch.ai/introduction/getting-started

# IMPORTANT: Add your OPENAI_API_KEY and LANGWATCH_API_KEY to your .env file

import pytest
import scenario
import litellm
from dotenv import load_dotenv

load_dotenv()

# Configure the default model for simulations
scenario.configure(default_model="openai/gpt-4.1")


@pytest.mark.agent_test
@pytest.mark.asyncio
async def test_vegetarian_recipe_agent():
    # 1. Create your agent adapter
    class RecipeAgent(scenario.AgentAdapter):
        async def call(self, input: scenario.AgentInput) -> scenario.AgentReturnTypes:
            return vegetarian_recipe_agent(input.messages)

    # 2. Run the scenario
    result = await scenario.run(
        name="dinner recipe request",
        description="""
            It's saturday evening, the user is very hungry and tired,
            but have no money to order out, so they are looking for a recipe.
        """,
        agents=[
            RecipeAgent(),
            scenario.UserSimulatorAgent(),
            scenario.JudgeAgent(criteria=[
                "Agent should not ask more than two follow-up questions",
                "Agent should generate a recipe",
                "Recipe should include a list of ingredients",
                "Recipe should include step-by-step cooking instructions",
                "Recipe should be vegetarian and not include any sort of meat",
            ])
        ],
        script=[
            scenario.user("quick recipe for dinner"),
            scenario.agent(),
            scenario.user(),
            scenario.agent(),
            scenario.judge(),
        ],
    )

    # 3. Assert the result
    assert result.success

# Example agent implementation using litellm


@scenario.cache()
def vegetarian_recipe_agent(messages) -> scenario.AgentReturnTypes:
    response = litellm.completion(
        model="openai/gpt-4.1",
        messages=[
            {
                "role": "system",
                "content": """
                    You are a vegetarian recipe agent.
                    Given the user request, ask AT MOST ONE follow-up question,
                    then provide a complete recipe. Keep your responses concise and focused.
                """,
            },
            *messages,
        ],
    )
    return response.choices[0].message

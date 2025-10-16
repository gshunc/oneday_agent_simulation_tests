# LLM Simulation Testing
Examples of tests that simulate a conversation between a user and an AI Agent using the [LangWatch Scenario](https://scenario.langwatch.ai/introduction/getting-started) Python library.

## Instructions to run the tests
1. Create an account on [LangWatch](https://langwatch.ai/) and copy your API key
2. Obtain an OpenAI API key
3. Add your OpenAI and LangWatch API keys to your `.env` file (see `.env.example`)
4. Install Python and the [uv package manager](https://github.com/astral-sh/uv)
5. Run the demo test with `uv run pytest -s demo_example_test.py `
5. Run the OneDay demo tests with `uv run pytest -s oneday_tests.py `
# LLM Simulation Testing

Examples of tests that simulate a conversation between a user and an AI Agent using the [LangWatch Scenario](https://scenario.langwatch.ai/introduction/getting-started) Python library.

## Instructions to run the tests

### Prerequisites

1. Create an account on [LangWatch](https://langwatch.ai/) and copy your API key
2. Obtain an OpenAI API key
3. Add your OpenAI and LangWatch API keys to your `.env` file (see `.env.example`)

### Setup Option 1: Using uv (recommended)

4. Install Python and the [uv package manager](https://github.com/astral-sh/uv)
5. Run the demo test with `uv run pytest -s demo_example_test.py`
6. Run the OneDay demo tests with `uv run pytest -s oneday_evaluation.py`

### Setup Option 2: Using venv

4. Install Python 3.13 or higher
5. Create and activate the virtual environment:
   ```bash
   source venv/bin/activate  # On macOS/Linux
   # or
   venv\Scripts\activate  # On Windows
   ```
6. Run the tests:
   ```bash
   pytest -s demo_example_test.py
   # or
   pytest -s oneday_evaluation.py
   ```

Note: The virtual environment is already set up with all dependencies from `requirements.txt`

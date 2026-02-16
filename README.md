# OneDay Agent Simulation Tests

This project runs automated tests that simulate conversations between a nurse and the OneDay diagnostic AI agent. The tests verify that the agent correctly follows medical guidelines and provides accurate diagnoses.

---

## What This Does

The tests simulate realistic nurse-agent conversations where:

1. A simulated nurse describes patient symptoms
2. The OneDay agent asks follow-up questions
3. The agent provides a diagnosis based on the guidelines
4. A "judge" AI evaluates whether the agent performed correctly

Results are displayed in the terminal and tracked in the [LangWatch dashboard](https://langwatch.ai/).

---

## Quick Start Guide

### Step 1: Get Your API Keys

You'll need three API keys:

1. **LangWatch API Key** (for tracking test results)

   - Go to [langwatch.ai](https://langwatch.ai/) and create a free account
   - Find your API key in the dashboard settings

2. **OpenAI API Key** (for running GPT models)

   - Go to [platform.openai.com](https://platform.openai.com/)
   - Create an account and generate an API key

3. **Google Docs Access** (for loading test scenarios)
   - You'll need access to the scenarios Google Doc
   - Run the authentication flow when prompted

### Step 2: Set Up Your Environment File

1. Find the file called `.env.example` in this folder
2. Make a copy and rename it to `.env`
3. Open `.env` in a text editor and fill in your API keys:

```
LANGWATCH_API_KEY=your_langwatch_key_here
OPENAI_API_KEY=your_openai_key_here
```

### Step 3: Install the Tools

**On Mac/Linux:**

1. Open Terminal
2. Install `uv` (a Python package manager):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
3. Restart your terminal

**On Windows:**

1. Open PowerShell
2. Install `uv`:
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
3. Restart PowerShell

### Step 4: Run the Tests

Navigate to this project folder in your terminal, then run:

You can use the commands "ls" to list what files are in your current folder, and "cd" to choose a folder.

```bash
uv run pytest -n auto
```

This will:

- Run all tests in parallel (using all your CPU cores)
- Show progress as tests complete
- Display a summary at the end

---

## Choosing a Model

You can test with different AI models using the `--model` option:

| Model             | Command                                           | Notes                      |
| ----------------- | ------------------------------------------------- | -------------------------- |
| GPT-5 Mini        | `uv run pytest -n auto --model gpt-5-mini`        | Default                    |
| Claude 4.5 Sonnet | `uv run pytest -n auto --model claude-4.5-sonnet` | Requires Anthropic API key |
| Gemini 2.5 Flash  | `uv run pytest -n auto --model gemini-2.5-flash`  | Requires Google AI API key |

If you don't specify a model, it defaults to `gpt-5-mini`.

---

## Understanding the Results

### Terminal Output

After tests complete, you'll see a summary like this:

```
════════════════════════════════════════════════════════════
  TEST RESULTS SUMMARY
  Model: gpt-5-mini  |  Time: Dec03-1430Z
════════════════════════════════════════════════════════════

  STANDARD TESTS (7/8 passed)
  ----------------------------------------
    Case   1: ✓ PASS
    Case   2: ✓ PASS
    Case   3: ✗ FAIL
    ...
  ----------------------------------------
  Passed: 7  |  Failed: 1  |  Skipped: 0

  DIAGNOSIS ONLY TESTS (6/8 passed)
  ----------------------------------------
    ...
════════════════════════════════════════════════════════════
```

### Test Types

- **Standard Tests**: Check that the agent provides correct diagnoses, regardless of the path taken to get there, along with not repeating information and following oneday guidelines
- **Diagnosis Only Tests**: Simply checks that the agent provides the correct diagnosis, nothing else.

### LangWatch Dashboard

For detailed results including full conversation transcripts:

1. Go to [langwatch.ai](https://langwatch.ai/)
2. Log in to your account
3. Find your test run by the timestamp (e.g., "oneday-gpt-5-mini-Dec03-1430Z-[diagnosis_only/standard]")

---

## Common Commands

| What you want to do         | Command                                   |
| --------------------------- | ----------------------------------------- |
| Run all tests               | `uv run pytest -n auto`                   |
| Run only standard tests     | `uv run pytest -n auto -k standard`       |
| Run diagnosis_only tests    | `uv run pytest -n auto -k diagnosis_only` |
| Run a specific case         | `uv run pytest -n auto -k case_3`         |
| Run without parallelization | `uv run pytest`                           |
| See detailed output         | `uv run pytest -n auto --tb=short`        |

---

## Troubleshooting

### "API key not found" error

- Make sure your `.env` file exists and contains the correct keys
- Check there are no extra spaces around the `=` sign

### Tests are running very slowly

- Make sure you're using `-n auto` to run tests in parallel
- Check your internet connection

### "Google auth" error

- Delete any `token.json` file in the project folder
- Run the tests again and complete the Google authentication

### A test keeps timing out

- Some scenarios may hit the 10-turn conversation limit
- Check the LangWatch dashboard to see the full conversation

---

## Project Structure

```
├── web/                    # Web UI for running tests
│   ├── app/                # Next.js app
│   └── package.json
├── oneday_evaluation.py    # Main test file
├── conftest.py             # Test configuration
├── oneday_guidelines.md    # Medical guidelines the agent follows
├── doc_extraction/         # Loads test scenarios from Google Docs
├── .env                    # Your API keys (don't share this!)
└── pyproject.toml          # Project dependencies
```

---

## 🚀 Web UI (Deprecated)

<s>A local web interface is available for running tests without using the command line.

**To start:**

```bash
cd web
npm install   # First time only
npm run dev
```

Then open **http://localhost:3000** in your browser.

The web UI lets you:

- Select which AI model to test
- Enter API keys directly (no `.env` file needed)
- Watch test progress in real-time
- View results in a formatted table
- Link directly to the LangWatch dashboard
</s>

---

#
# OneDay Agent Simulation Tests - Setup Script (Windows)
#
# This script installs all necessary dependencies and configures API keys.
# After running this script, you can execute: uv run pytest -n auto
#
# To run this script, open PowerShell and execute:
#   .\setup.ps1
#
# If you get an execution policy error, run:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#

$ErrorActionPreference = "Stop"

# Helper functions
function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Blue -NoNewline
    Write-Host ""
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] " -ForegroundColor Green -NoNewline
    Write-Host $Message
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[!] " -ForegroundColor Yellow -NoNewline
    Write-Host $Message
}

function Write-Err {
    param([string]$Message)
    Write-Host "[X] " -ForegroundColor Red -NoNewline
    Write-Host $Message
}

function Write-Info {
    param([string]$Message)
    Write-Host "[i] " -ForegroundColor Cyan -NoNewline
    Write-Host $Message
}

# Change to script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Clear-Host

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "      OneDay Agent Simulation Tests - Setup Wizard" -ForegroundColor White
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This script will:"
Write-Host "  1. Install the 'uv' package manager (if needed)"
Write-Host "  2. Install Python 3.13 and all dependencies"
Write-Host "  3. Help you configure your API keys"
Write-Host "  4. Verify everything is working"
Write-Host ""
Write-Host "Press Enter to continue or Ctrl+C to cancel..." -ForegroundColor Yellow
Read-Host

# Step 1: Check/Install uv
Write-Step "Step 1/4: Installing uv package manager"

$uvExists = $null
try {
    $uvExists = Get-Command uv -ErrorAction SilentlyContinue
} catch {
    $uvExists = $null
}

if ($uvExists) {
    $uvVersion = & uv --version 2>$null
    Write-Success "uv is already installed ($uvVersion)"
} else {
    Write-Info "uv not found. Installing now..."
    Write-Host ""
    Write-Host "Running: Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression"
    Write-Host ""

    try {
        $env:UV_INSTALL_DIR = "$env:USERPROFILE\.local\bin"
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression

        # Add to PATH for current session
        $uvPath = "$env:USERPROFILE\.local\bin"
        if (Test-Path $uvPath) {
            $env:PATH = "$uvPath;$env:PATH"
        }

        # Also check cargo bin (alternative install location)
        $cargoPath = "$env:USERPROFILE\.cargo\bin"
        if (Test-Path $cargoPath) {
            $env:PATH = "$cargoPath;$env:PATH"
        }

        # Verify installation
        $uvExists = Get-Command uv -ErrorAction SilentlyContinue
        if ($uvExists) {
            Write-Success "uv installed successfully"
        } else {
            Write-Err "uv installation requires restarting PowerShell"
            Write-Host ""
            Write-Host "Please:"
            Write-Host "  1. Close this PowerShell window"
            Write-Host "  2. Open a new PowerShell window"
            Write-Host "  3. Run this script again: .\setup.ps1"
            exit 1
        }
    } catch {
        Write-Err "Failed to install uv: $_"
        Write-Host "Please install uv manually from: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    }
}

# Step 2: Sync dependencies with uv
Write-Step "Step 2/4: Installing Python and dependencies"

Write-Host ""
Write-Host "Running: uv sync"
Write-Host ""
Write-Host "This will download Python 3.13 (if needed) and install all packages..."
Write-Host ""

try {
    & uv sync
    if ($LASTEXITCODE -ne 0) {
        throw "uv sync failed with exit code $LASTEXITCODE"
    }
    Write-Success "All dependencies installed successfully"
} catch {
    Write-Err "Failed to install dependencies: $_"
    exit 1
}

# Step 3: Configure API keys and Google Doc
Write-Step "Step 3/4: Configuring API keys and test document"

$envFile = Join-Path $ScriptDir ".env"
$envExample = Join-Path $ScriptDir ".env.example"

$needOpenAI = $true
$needLangWatch = $true
$needDocID = $true

if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -Raw
    if ($envContent -match "OPENAI_API_KEY=.+") {
        $needOpenAI = $false
    }
    if ($envContent -match "LANGWATCH_API_KEY=.+") {
        $needLangWatch = $false
    }
    if ($envContent -match "DOC_ID=.+") {
        $needDocID = $false
    }
}

if (-not $needOpenAI -and -not $needLangWatch -and -not $needDocID) {
    Write-Success "API keys and document ID already configured in .env"
} else {
    Write-Host ""
    Write-Host "You need API keys and a test document to run the tests."
    Write-Host "Would you like to configure them now?"
    Write-Host ""
    Write-Host "  [1] Yes, I have everything ready"
    Write-Host "  [2] No, I'll add them to .env manually later"
    Write-Host ""
    $setupChoice = Read-Host "Enter choice (1 or 2)"

    if ($setupChoice -eq "1") {
        Write-Host ""
        Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan
        Write-Host "Where to get your API keys:" -ForegroundColor White
        Write-Host ""
        Write-Host "  OpenAI API Key:"
        Write-Host "    1. Go to: https://platform.openai.com/api-keys"
        Write-Host "    2. Sign in or create an account"
        Write-Host "    3. Click 'Create new secret key'"
        Write-Host "    4. Copy the key (starts with 'sk-')"
        Write-Host ""
        Write-Host "  LangWatch API Key:"
        Write-Host "    1. Go to: https://langwatch.ai/"
        Write-Host "    2. Sign in or create a free account"
        Write-Host "    3. Go to Settings > API Keys"
        Write-Host "    4. Copy your API key"
        Write-Host ""
        Write-Host "Google Doc with test cases:" -ForegroundColor White
        Write-Host ""
        Write-Host "  You need a Google Doc containing your test scenarios."
        Write-Host "  The doc must be shared as 'Anyone with the link can view'."
        Write-Host ""
        Write-Host "  Paste the full URL, for example:"
        Write-Host "    https://docs.google.com/document/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ/edit"
        Write-Host ""
        Write-Host "  (The document ID will be extracted automatically)"
        Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan
        Write-Host ""

        # Only ask for keys that are actually needed
        $openAIKey = ""
        $langWatchKey = ""
        $docIDInput = ""

        if ($needOpenAI) {
            Write-Host "Enter your OpenAI API Key (or press Enter to skip):" -ForegroundColor White
            $openAIKey = Read-Host
        }

        if ($needLangWatch) {
            Write-Host ""
            Write-Host "Enter your LangWatch API Key (or press Enter to skip):" -ForegroundColor White
            $langWatchKey = Read-Host
        }

        if ($needDocID) {
            Write-Host ""
            Write-Host "Enter your Google Doc URL (or press Enter to skip):" -ForegroundColor White
            $docIDInput = Read-Host
            # Extract doc ID from URL if a full URL was provided
            if ($docIDInput -match "/d/([a-zA-Z0-9_-]+)") {
                $docIDInput = $Matches[1]
            }
        }

        # Create .env if it doesn't exist
        if (-not (Test-Path $envFile)) {
            if (Test-Path $envExample) {
                Copy-Item $envExample $envFile
            } else {
                @"
OPENAI_API_KEY=
LANGWATCH_API_KEY=
DOC_ID=
"@ | Set-Content $envFile
            }
        }

        # Only update keys that the user actually provided (non-empty)
        if ($openAIKey) {
            $content = Get-Content $envFile
            $found = $false
            $newContent = @()

            foreach ($line in $content) {
                if ($line -match "^OPENAI_API_KEY=") {
                    $newContent += "OPENAI_API_KEY=$openAIKey"
                    $found = $true
                } else {
                    $newContent += $line
                }
            }

            if (-not $found) {
                $newContent += "OPENAI_API_KEY=$openAIKey"
            }

            $newContent | Set-Content $envFile
            Write-Success "OpenAI API key saved"
        } elseif ($needOpenAI) {
            Write-Warn "OpenAI API key not set - you'll need to add it to .env"
        }

        if ($langWatchKey) {
            $content = Get-Content $envFile
            $found = $false
            $newContent = @()

            foreach ($line in $content) {
                if ($line -match "^LANGWATCH_API_KEY=") {
                    $newContent += "LANGWATCH_API_KEY=$langWatchKey"
                    $found = $true
                } else {
                    $newContent += $line
                }
            }

            if (-not $found) {
                $newContent += "LANGWATCH_API_KEY=$langWatchKey"
            }

            $newContent | Set-Content $envFile
            Write-Success "LangWatch API key saved"
        } elseif ($needLangWatch) {
            Write-Warn "LangWatch API key not set - you'll need to add it to .env"
        }

        if ($docIDInput) {
            $content = Get-Content $envFile
            $found = $false
            $newContent = @()

            foreach ($line in $content) {
                if ($line -match "^DOC_ID=") {
                    $newContent += "DOC_ID=$docIDInput"
                    $found = $true
                } else {
                    $newContent += $line
                }
            }

            if (-not $found) {
                $newContent += "DOC_ID=$docIDInput"
            }

            $newContent | Set-Content $envFile
            Write-Success "Google Doc ID saved"
        } elseif ($needDocID) {
            Write-Warn "Google Doc ID not set - you'll need to add it to .env"
        }

    } else {
        # Create .env from example or blank
        if (-not (Test-Path $envFile)) {
            if (Test-Path $envExample) {
                Copy-Item $envExample $envFile
            } else {
                @"
OPENAI_API_KEY=
LANGWATCH_API_KEY=
DOC_ID=
"@ | Set-Content $envFile
            }
            Write-Success "Created .env file"
        }
        Write-Host ""
        Write-Info "To add your configuration later, edit the .env file:"
        Write-Host "      Open .env in any text editor (like Notepad) and add your keys"
        Write-Host ""
        Write-Host "      Or run this command to open it:"
        Write-Host "        notepad .env"
    }
}

# Step 4: Verify installation
Write-Step "Step 4/4: Verifying installation"

Write-Host ""
try {
    $result = & uv run python -c "import pytest; import litellm; import scenario; print('All packages imported successfully')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "All required packages are working"
    } else {
        throw "Import check failed"
    }
} catch {
    Write-Err "Some packages failed to import. Try running: uv sync --reinstall"
    exit 1
}

# Final summary
Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "                    Setup Complete!" -ForegroundColor White
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""

# Check if keys are configured
$keysOK = $true
$missingItems = @()
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -Raw
    if ($envContent -notmatch "OPENAI_API_KEY=.+") {
        $keysOK = $false
        $missingItems += "  - OPENAI_API_KEY=your_key_here"
    }
    if ($envContent -notmatch "LANGWATCH_API_KEY=.+") {
        $keysOK = $false
        $missingItems += "  - LANGWATCH_API_KEY=your_key_here"
    }
    if ($envContent -notmatch "DOC_ID=.+") {
        $keysOK = $false
        $missingItems += "  - DOC_ID=your_google_doc_id_or_url"
    }
} else {
    $keysOK = $false
    $missingItems = @("  - OPENAI_API_KEY=your_key_here", "  - LANGWATCH_API_KEY=your_key_here", "  - DOC_ID=your_google_doc_id_or_url")
}

if ($keysOK) {
    Write-Host "You're all set! " -ForegroundColor Green -NoNewline
    Write-Host "Run the tests with:"
    Write-Host ""
    Write-Host "  uv run pytest -n auto" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "Almost there! " -ForegroundColor Yellow -NoNewline
    Write-Host "You still need to add some configuration."
    Write-Host ""
    Write-Host "Edit the .env file and add:"
    foreach ($item in $missingItems) {
        Write-Host $item
    }
    Write-Host ""
    Write-Host "Then run the tests with:"
    Write-Host ""
    Write-Host "  uv run pytest -n auto" -ForegroundColor White
    Write-Host ""
}

Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Quick Reference - Commands you can run:" -ForegroundColor White
Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Run all tests:              uv run pytest -n auto"
Write-Host "  Run standard tests only:    uv run pytest -n auto -k standard"
Write-Host "  Run strict tests only:      uv run pytest -n auto -k strict"
Write-Host "  Run specific case:          uv run pytest -n auto -k case_3"
Write-Host "  Use different model:        uv run pytest -n auto --model claude-4.5-sonnet"
Write-Host "  ^^^ In order to use a different model, ensure that the API key is added to the .env file. Additionally, ensure that the model is supported. ^^^"
Write-Host ""
Write-Host "  Start web UI:               cd web; npm install; npm run dev"
Write-Host ""

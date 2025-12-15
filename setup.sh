#!/bin/bash
#
# OneDay Agent Simulation Tests - Setup Script (Mac/Linux)
#
# This script installs all necessary dependencies and configures API keys.
# After running this script, you can execute: uv run pytest -n auto
#

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

print_step() {
    echo -e "\n${BLUE}==>${NC} ${BOLD}$1${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${CYAN}i${NC} $1"
}

# Get script directory (works even if script is sourced)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

clear 2>/dev/null || true

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}       ${BOLD}OneDay Agent Simulation Tests - Setup Wizard${NC}          ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "This script will:"
echo "  1. Install the 'uv' package manager (if needed)"
echo "  2. Install Python 3.13 and all dependencies"
echo "  3. Help you configure your API keys"
echo "  4. Verify everything is working"
echo ""
echo -e "${YELLOW}Press Enter to continue or Ctrl+C to cancel...${NC}"
read -r

# Step 1: Check/Install uv
print_step "Step 1/4: Installing uv package manager"

if command -v uv &> /dev/null; then
    UV_VERSION=$(uv --version 2>/dev/null || echo "unknown")
    print_success "uv is already installed ($UV_VERSION)"
else
    print_info "uv not found. Installing now..."
    echo ""
    echo "Running: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""

    # Install uv using the official installer
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Source the shell profile to get uv in PATH
    if [ -f "$HOME/.cargo/env" ]; then
        source "$HOME/.cargo/env"
    fi

    # Also try common shell configs
    for profile in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile" "$HOME/.bash_profile"; do
        if [ -f "$profile" ]; then
            source "$profile" 2>/dev/null || true
        fi
    done

    # Add to PATH for current session if not already there
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

    if command -v uv &> /dev/null; then
        print_success "uv installed successfully"
    else
        print_error "uv installation requires restarting your terminal"
        echo ""
        echo "Please:"
        echo "  1. Close this terminal window"
        echo "  2. Open a new terminal"
        echo "  3. Run this script again: ./setup.sh"
        exit 1
    fi
fi

# Step 2: Sync dependencies with uv
print_step "Step 2/4: Installing Python and dependencies"

echo ""
echo "Running: uv sync"
echo ""
echo "This will download Python 3.13 (if needed) and install all packages..."
echo ""

# uv sync will:
# - Download Python 3.13 if needed (as specified in pyproject.toml)
# - Create a virtual environment
# - Install all dependencies
uv sync

print_success "All dependencies installed successfully"

# Step 3: Configure API keys and Google Doc
print_step "Step 3/4: Configuring API keys and test document"

# Check if .env exists and has keys
NEED_OPENAI=true
NEED_LANGWATCH=true
NEED_DOC_ID=true

if [ -f ".env" ]; then
    # Check if keys are already set (non-empty)
    if grep -q "^OPENAI_API_KEY=.\+" .env 2>/dev/null; then
        NEED_OPENAI=false
    fi
    if grep -q "^LANGWATCH_API_KEY=.\+" .env 2>/dev/null; then
        NEED_LANGWATCH=false
    fi
    if grep -q "^DOC_ID=.\+" .env 2>/dev/null; then
        NEED_DOC_ID=false
    fi
fi

if [ "$NEED_OPENAI" = false ] && [ "$NEED_LANGWATCH" = false ] && [ "$NEED_DOC_ID" = false ]; then
    print_success "API keys and document ID already configured in .env"
else
    echo ""
    echo "You need API keys and a test document to run the tests."
    echo "Would you like to configure them now?"
    echo ""
    echo "  [1] Yes, I have everything ready"
    echo "  [2] No, I'll add them to .env manually later"
    echo ""
    read -p "Enter choice (1 or 2): " SETUP_CHOICE

    if [ "$SETUP_CHOICE" = "1" ]; then
        echo ""
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${BOLD}Where to get your API keys:${NC}"
        echo ""
        echo "  OpenAI API Key:"
        echo "    1. Go to: https://platform.openai.com/api-keys"
        echo "    2. Sign in or create an account"
        echo "    3. Click 'Create new secret key'"
        echo "    4. Copy the key (starts with 'sk-')"
        echo ""
        echo "  LangWatch API Key:"
        echo "    1. Go to: https://langwatch.ai/"
        echo "    2. Sign in or create a free account"
        echo "    3. Go to Settings > API Key and Setup"
        echo "    4. Copy your API key"
        echo ""
        echo -e "${BOLD}Google Doc with test cases:${NC}"
        echo ""
        echo "  You need a Google Doc containing your test scenarios."
        echo "  The doc must be shared as 'Anyone with the link can view'."
        echo ""
        echo "  Paste the full URL, for example:"
        echo "    https://docs.google.com/document/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ/edit"
        echo ""
        echo "  (The document ID will be extracted automatically)"
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""

        # Only ask for keys that are actually needed
        OPENAI_KEY=""
        LANGWATCH_KEY=""
        DOC_ID_INPUT=""

        if [ "$NEED_OPENAI" = true ]; then
            echo -e "Enter your ${BOLD}OpenAI API Key${NC} (or press Enter to skip):"
            read -r OPENAI_KEY
        fi

        if [ "$NEED_LANGWATCH" = true ]; then
            echo ""
            echo -e "Enter your ${BOLD}LangWatch API Key${NC} (or press Enter to skip):"
            read -r LANGWATCH_KEY
        fi

        if [ "$NEED_DOC_ID" = true ]; then
            echo ""
            echo -e "Enter your ${BOLD}Google Doc URL${NC} (or press Enter to skip):"
            read -r DOC_ID_INPUT
            # Extract doc ID from URL if a full URL was provided
            if [ -n "$DOC_ID_INPUT" ]; then
                DOC_ID_EXTRACTED=$(echo "$DOC_ID_INPUT" | sed -n 's/.*\/d\/\([a-zA-Z0-9_-]*\).*/\1/p')
                if [ -n "$DOC_ID_EXTRACTED" ]; then
                    DOC_ID_INPUT="$DOC_ID_EXTRACTED"
                fi
            fi
        fi

        # Create .env if it doesn't exist
        if [ ! -f ".env" ]; then
            if [ -f ".env.example" ]; then
                cp .env.example .env
            else
                cat > .env << 'EOF'
OPENAI_API_KEY=
LANGWATCH_API_KEY=
DOC_ID=
EOF
            fi
        fi

        # Only update keys that the user actually provided (non-empty)
        if [ -n "$OPENAI_KEY" ]; then
            if grep -q "^OPENAI_API_KEY=" .env; then
                sed -i.bak "s/^OPENAI_API_KEY=.*/OPENAI_API_KEY=$OPENAI_KEY/" .env
            else
                echo "OPENAI_API_KEY=$OPENAI_KEY" >> .env
            fi
            rm -f .env.bak
            print_success "OpenAI API key saved"
        elif [ "$NEED_OPENAI" = true ]; then
            print_warning "OpenAI API key not set - you'll need to add it to .env"
        fi

        if [ -n "$LANGWATCH_KEY" ]; then
            if grep -q "^LANGWATCH_API_KEY=" .env; then
                sed -i.bak "s/^LANGWATCH_API_KEY=.*/LANGWATCH_API_KEY=$LANGWATCH_KEY/" .env
            else
                echo "LANGWATCH_API_KEY=$LANGWATCH_KEY" >> .env
            fi
            rm -f .env.bak
            print_success "LangWatch API key saved"
        elif [ "$NEED_LANGWATCH" = true ]; then
            print_warning "LangWatch API key not set - you'll need to add it to .env"
        fi

        if [ -n "$DOC_ID_INPUT" ]; then
            if grep -q "^DOC_ID=" .env; then
                sed -i.bak "s/^DOC_ID=.*/DOC_ID=$DOC_ID_INPUT/" .env
            else
                echo "DOC_ID=$DOC_ID_INPUT" >> .env
            fi
            rm -f .env.bak
            print_success "Google Doc ID saved"
        elif [ "$NEED_DOC_ID" = true ]; then
            print_warning "Google Doc ID not set - you'll need to add it to .env"
        fi

    else
        # Create .env from example or blank
        if [ ! -f ".env" ]; then
            if [ -f ".env.example" ]; then
                cp .env.example .env
            else
                cat > .env << 'EOF'
OPENAI_API_KEY=
LANGWATCH_API_KEY=
DOC_ID=
EOF
            fi
            print_success "Created .env file"
        fi
        echo ""
        print_info "To add your configuration later, edit the .env file:"
        echo "      Open .env in any text editor and add your keys"
        echo ""
        echo "      Or use these terminal commands:"
        echo "        Mac:   open -e .env"
        echo "        Linux: nano .env  (then Ctrl+X to save)"
    fi
fi

# Step 4: Verify installation
print_step "Step 4/4: Verifying installation"

echo ""
if uv run python -c "import pytest; import litellm; import scenario; print('All packages imported successfully')" 2>/dev/null; then
    print_success "All required packages are working"
else
    print_error "Some packages failed to import"
    echo "Try running: uv sync --reinstall"
    exit 1
fi

# Final summary
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}                    ${BOLD}Setup Complete!${NC}                          ${GREEN}║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if keys are configured
KEYS_OK=true
MISSING_ITEMS=""
if ! grep -q "^OPENAI_API_KEY=.\+" .env 2>/dev/null; then
    KEYS_OK=false
    MISSING_ITEMS="$MISSING_ITEMS\n  - OPENAI_API_KEY=your_key_here"
fi
if ! grep -q "^LANGWATCH_API_KEY=.\+" .env 2>/dev/null; then
    KEYS_OK=false
    MISSING_ITEMS="$MISSING_ITEMS\n  - LANGWATCH_API_KEY=your_key_here"
fi
if ! grep -q "^DOC_ID=.\+" .env 2>/dev/null; then
    KEYS_OK=false
    MISSING_ITEMS="$MISSING_ITEMS\n  - DOC_ID=your_google_doc_id_or_url"
fi

if [ "$KEYS_OK" = true ]; then
    echo -e "${GREEN}You're all set!${NC} Run the tests with:"
    echo ""
    echo -e "  ${BOLD}uv run pytest -n auto${NC}"
    echo ""
else
    echo -e "${YELLOW}Almost there!${NC} You still need to add some configuration."
    echo ""
    echo "Edit the .env file and add:"
    echo -e "$MISSING_ITEMS"
    echo ""
    echo "Then run the tests with:"
    echo ""
    echo -e "  ${BOLD}uv run pytest -n auto${NC}"
    echo ""
fi

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Quick Reference - Commands you can run:${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Run all tests:              uv run pytest -n auto"
echo "  Run standard tests only:    uv run pytest -n auto -k standard"
echo "  Run diagnosis_only tests only:      uv run pytest -n auto -k diagnosis_only"
echo "  Run specific case:          uv run pytest -n auto -k case_3"
echo "  Use different model:        uv run pytest -n auto --model claude-4.5-sonnet"
echo "  ^^^ In order to use a different model, ensure that the API key is added to the .env file. Additionally, ensure that the model is supported. ^^^"
echo ""
echo "  Start web UI:               cd web && npm install && npm run dev"
echo ""

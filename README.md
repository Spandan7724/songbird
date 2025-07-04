# Songbird

<div align="center">

<pre style="color: #4A90E2;">
███████╗ ██████╗ ███╗   ██╗ ██████╗ ██████╗ ██╗██████╗ ██████╗ 
██╔════╝██╔═══██╗████╗  ██║██╔════╝ ██╔══██╗██║██╔══██╗██╔══██╗
███████╗██║   ██║██╔██╗ ██║██║  ███╗██████╔╝██║██████╔╝██║  ██║
╚════██║██║   ██║██║╚██╗██║██║   ██║██╔══██╗██║██╔══██╗██║  ██║
███████║╚██████╔╝██║ ╚████║╚██████╔╝██████╔╝██║██║  ██║██████╔╝
╚══════╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═╝╚═════╝
</pre>

**A terminal-based AI coding companion with 11 professional tools, smart task management, and persistent memory**

[![CI](https://github.com/Spandan7724/songbird/workflows/CI/badge.svg)](https://github.com/Spandan7724/songbird/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/songbird-ai.svg)](https://badge.fury.io/py/songbird-ai)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)


</div>


## Downloading

### With uv (recommended)
```bash
uv tool install songbird-ai
```
### With pipx (if available)
```bash
pipx install songbird-ai
```
### With pip (traditional)
```bash
pip install songbird-ai
```


## Quick Start



### Option 1: With Gemini (Recommended)

```bash
# Install Songbird
pipx install songbird-ai

# Get your free Gemini API key
# Visit: https://aistudio.google.com/app/apikey

# Set your API key
export GEMINI_API_KEY="your-api-key-here"

# Start coding with AI
songbird

# Set your default provider (one-time setup)
songbird --default

# Continue your previous session
songbird --continue

# Resume from any previous session
songbird --resume
```

### Option 2: With GitHub Copilot

```bash
# Install Songbird
pipx install songbird-ai

# Get your GitHub Copilot access token from VS Code or JetBrains IDE
# VS Code: Command Palette → "GitHub Copilot: Generate Access Token"
# JetBrains: Settings → Tools → GitHub Copilot → Generate Token

# Set your access token
export COPILOT_ACCESS_TOKEN="your-copilot-token-here"

# Start coding with GitHub Copilot
songbird --provider copilot

# Set Copilot as your default (one-time setup)
songbird default copilot

# Continue previous session with Copilot
songbird --provider copilot --continue
```

### Option 3: With Local Ollama

```bash
# Install Songbird
pipx install songbird-ai

# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama and pull a model
ollama serve
ollama pull devstral:latest

# Start coding with AI
songbird --provider ollama

# Set Ollama as your default (one-time setup)  
songbird default ollama

# Continue previous session with Ollama
songbird --provider ollama --continue
```

## Features


**11 Professional Tools** for complete development workflows:
- **Enhanced File Operations**: `file_search`, `file_read`, `file_create`, `file_edit` with syntax highlighting and diff previews
- **Smart Task Management**: `todo_read`, `todo_write` with automatic prioritization and session persistence
- **Advanced File Discovery**: `glob` pattern matching, `grep` regex search, enhanced `ls` directory listing
- **Atomic Operations**: `multi_edit` for safe bulk file changes with rollback capabilities
- **Shell Integration**: `shell_exec` with live output streaming and cross-platform support

### **Intelligent Task Management**
- **LLM-Powered Auto-Completion**: Automatically detects and completes tasks from natural language - just say "I implemented the JWT tokens" and the system intelligently marks related todos as complete
- **Session-Aware Todos**: Create, track, and complete development tasks with automatic priority assignment
- **Smart Prioritization**: AI analyzes task content to assign appropriate priority levels
- **Clean Visual Display**: Simple bullet points with strikethrough for completed tasks
- **Semantic Understanding**: The LLM understands context - "JWT token system" matches "JWT tokens for authentication"

**Smart Todo Management Example:**
```
# Create todos naturally
"I need to implement JWT authentication and user registration"
✓ Creates: "Implement JWT authentication" and "Add user registration"

# Complete todos intelligently  
"I finished the JWT token system and it's working"
✓ Auto-completes: "Implement JWT authentication" (semantic match)
✓ Shows updated list with strikethrough for completed items

# No manual marking needed - just describe what you did!
``` 

### **Advanced File Discovery & Search**
- **Glob Patterns**: Find files with patterns like `**/*.py`, `src/**/*.js`, `*test*.{py,js}`
- **Regex Content Search**: Powerful regex search with context lines and highlighting
- **Enhanced Directory Listing**: Rich formatted output with sorting and metadata
- **Smart File Detection**: Automatically detects filename vs content searches
- **Type-Specific Search**: Filter by file extensions (py, js, md, txt, json, yaml, etc.)

### **Atomic Multi-File Operations**
- **Bulk Editing**: Edit multiple files simultaneously with safety guarantees
- **Beautiful Previews**: Unified diff display for all changes before applying
- **Rollback Protection**: Automatic rollback if any operation fails
- **Atomic Transactions**: All-or-nothing approach ensures consistency

### **Persistent Memory System**
- **Session Persistence**: Automatic conversation saving with project-aware storage
- **Seamless Continuation**: Resume exactly where you left off with `--continue`
- **Session Browser**: Interactive menu to select from previous sessions with `--resume`
- **Project Isolation**: Each git repository gets separate session storage
- **Visual Replay**: Perfect restoration of conversation history with tool outputs

### **Dynamic Command System**
- **In-Chat Commands**: Type `/` for instant command access without leaving conversation
- **Real-Time Model Switching**: Change models with `/model` command - no session restart needed
- **Model Persistence**: Model changes automatically save and restore across sessions
- **Help System**: Comprehensive `/help` command with examples and documentation
- **Session Management**: `/clear` command for conversation management

### **Multi-Provider AI Support**
- **6 AI Providers**: OpenAI, Anthropic Claude, Google Gemini, GitHub Copilot, Ollama, and OpenRouter
- **Automatic Provider Selection**: Intelligent fallback based on available API keys
- **Cloud & Local**: Use powerful cloud models or private local models
- **Dynamic Switching**: Switch models and providers instantly during conversations

### **Safety & Security**
- **Repository Sandboxing**: Cannot access files outside your project
- **Diff Previews**: Review all changes before applying with beautiful unified diffs
- **Atomic Operations**: Safe multi-file editing with automatic rollback
- **Input Validation**: Comprehensive validation for all tool operations


## Installation

### Recommended: pipx (for CLI tools)

```bash
# Install with pipx (isolated, globally available)
pipx install songbird-ai

# Verify installation
songbird --help
```

### Alternative: uv (fast package manager)

```bash
# Install with uv
uv tool install songbird-ai

# Verify installation
songbird --help
```

### Traditional: pip

```bash
# Install with pip (may conflict with other packages)
pip install songbird-ai
```

##  Getting Started

### 1. Install Ollama

<details>
<summary> Linux/WSL</summary>

```bash
curl -fsSL https://ollama.ai/install.sh | sh
```
</details>

<details>
<summary> macOS</summary>

```bash
# Using Homebrew
brew install ollama

# Or download from https://ollama.ai/download
```
</details>

<details>
<summary>Windows</summary>

Download and install from [https://ollama.ai/download](https://ollama.ai/download)
</details>

### 2. Start Ollama Server

```bash
ollama serve
```

### 3. Pull a Coding Model

```bash
# Recommended: Devstral (enhanced coding capabilities)
ollama pull devstral:latest

# Alternatives
ollama pull codellama:7b        # Meta's CodeLlama
ollama pull llama3.2:3b         # General purpose, faster
ollama pull deepseek-coder:6.7b # DeepSeek Coder
```

### 4. Start Songbird

```bash
# Launch interactive chat (uses Gemini if API key is set, otherwise Ollama)
songbird

# Use specific provider
songbird --provider gemini
songbird --provider ollama

# Use specific model (or change models during conversation with /model)
/model gemini-2.0-flash-001    # Switch models in conversation
/model qwen2.5-coder:7b        # No restart needed

# Check available providers
songbird --list-providers

# Check version and commands
songbird --help
songbird version
```

For detailed setup instructions, model comparisons, and troubleshooting for all providers, see the **[Complete Provider Guide](docs/providers.md)**.

## Usage Examples

```bash
# Basic chat session (auto-selects best provider)
songbird

# Use Gemini (powerful, cloud-based)
songbird --provider gemini

# Use GitHub Copilot (subscription-based)
songbird --provider copilot

# Use Ollama (private, local)
songbird --provider ollama

# List available providers
songbird --list-providers

# Set default provider (no need to specify --provider every time)
songbird --default               # Interactive menu to set defaults
songbird default gemini          # Set Gemini as default provider
songbird default copilot gpt-4o  # Set Copilot with specific model
songbird default ollama qwen2.5-coder:7b  # Set Ollama with specific model

# After setting defaults, just use:
songbird                 # Uses your configured defaults

# Session management
songbird --continue      # Continue latest session
songbird --resume        # Pick from previous sessions

# Print mode - One-off commands with clean output
songbird -p "What is 2+2?"                    # Shows tool execution + answer
songbird -p "Create a Python hello world"     # Transparent mode (default)
songbird -p "List files in current directory" # Shows tools used

# Ultra-quiet mode - Final answer only (perfect for scripting)
songbird -p "What is 2+2?" --quiet           # Only shows: "4"
songbird -p "Create hello.py" --quiet         # Only shows: "File created successfully..."
songbird -p "Current time" --quiet            # Clean output for automation

# Show available commands
songbird --help

# Display version
songbird version
```

### In-Chat Commands

Once in a conversation, use these powerful commands:

```bash
# Model switching (no session restart needed!)
/model                    # See available models and switch interactively
/model devstral:latest    # Switch to specific model directly
/model gemini-2.0-flash-001  # Switch to Gemini model

# Help and information
/help                     # Show all available commands
/help model               # Get help for specific command
/                         # Quick command menu

# Session management
/clear                    # Clear conversation history
/clear --force            # Clear without confirmation
```

## Configuration

### Default Provider & Model Setup

Songbird lets you set default providers and models so you don't have to specify them every time:

```bash
# Interactive setup - shows menu to choose provider and model
songbird --default

# Direct setup - set provider only (uses provider's default model)
songbird default gemini
songbird default copilot  
songbird default ollama

# Direct setup - set both provider and specific model
songbird default openai gpt-4o-mini
songbird default claude claude-3-5-sonnet-20241022
songbird default gemini gemini-2.0-flash-001
songbird default ollama qwen2.5-coder:7b
songbird default copilot gpt-4.1-2025-04-14

# After setting defaults, simply run:
songbird  # Uses your configured provider and model
```

### Configuration File

Songbird stores your preferences in `~/.songbird/config.json`:

```json
{
  "llm": {
    "default_provider": "gemini",
    "default_models": {
      "openai": "gpt-4o",
      "claude": "claude-3-5-sonnet-20241022", 
      "gemini": "gemini-2.0-flash-001",
      "ollama": "qwen2.5-coder:7b",
      "copilot": "gpt-4.1-2025-04-14"
    }
  }
}
```

### Environment Variable Overrides

You can override any configuration with environment variables:

```bash
export SONGBIRD_DEFAULT_PROVIDER="gemini"
export SONGBIRD_MAX_TOKENS=8192
export SONGBIRD_TEMPERATURE=0.3
```



## Development

### Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Setup

```bash
# Clone the repository
git clone https://github.com/Spandan7724/songbird
cd songbird

# Install with uv (recommended)
uv sync
uv pip install -e .

# Or with traditional tools
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=songbird

# Run specific test file
pytest tests/test_cli.py -v

# Run LLM integration tests (requires Ollama)
pytest tests/llm/ -v
```

### Building

```bash
# Build wheel and source distribution
python -m build

# Test local installation
uv tool install ./dist/songbird_ai-*.whl
```



## Troubleshooting

<details>
<summary>Ollama Connection Issues</summary>

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama service
ollama serve

# Check available models
ollama list
```
</details>

<details>
<summary>Model Not Found Errors</summary>

```bash
# Pull the required model
ollama pull qwen2.5-coder:7b

# List available models
ollama list
```
</details>

<details>
<summary>Gemini API Issues</summary>

```bash
# Check if API key is set
echo $GEMINI_API_KEY

# Get a free API key
# Visit: https://aistudio.google.com/app/apikey

# Set API key permanently
echo 'export GEMINI_API_KEY="your-key-here"' >> ~/.bashrc
source ~/.bashrc

# Test Gemini provider
songbird --provider gemini
```
</details>

<details>
<summary>GitHub Copilot Issues</summary>

```bash
# Check if access token is set
echo $COPILOT_ACCESS_TOKEN

# Get access token from VS Code
# Command Palette → "GitHub Copilot: Generate Access Token"

# Get access token from JetBrains IDE
# Settings → Tools → GitHub Copilot → Generate Token

# Set token temporarily
export COPILOT_ACCESS_TOKEN="ghu_xxxxxxxxxxxxxxxxxxxx"

# Set token permanently
echo 'export COPILOT_ACCESS_TOKEN="your-token-here"' >> ~/.bashrc
source ~/.bashrc

# Test Copilot provider
songbird --provider copilot

# Check available models
songbird --provider copilot --list-providers
```
</details>

<details>
<summary>Installation Issues</summary>

```bash
# Update pipx
pipx upgrade songbird-ai

# Or reinstall
pipx uninstall songbird-ai
pipx install songbird-ai
```
</details>

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Ollama](https://ollama.ai) - Local LLM runtime
- [Typer](https://typer.tiangolo.com) - CLI framework
- [Rich](https://rich.readthedocs.io) - Terminal formatting
- [ripgrep](https://github.com/BurntSushi/ripgrep) - Fast text search

---


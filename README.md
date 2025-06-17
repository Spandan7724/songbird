# Songbird

<div align="center">

```
███████╗ ██████╗ ███╗   ██╗ ██████╗ ██████╗ ██╗██████╗ ██████╗ 
██╔════╝██╔═══██╗████╗  ██║██╔════╝ ██╔══██╗██║██╔══██╗██╔══██╗
███████╗██║   ██║██╔██╗ ██║██║  ███╗██████╔╝██║██████╔╝██║  ██║
╚════██║██║   ██║██║╚██╗██║██║   ██║██╔══██╗██║██╔══██╗██║  ██║
███████║╚██████╔╝██║ ╚████║╚██████╔╝██████╔╝██║██║  ██║██████╔╝
╚══════╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═╝╚═════╝
```

**A terminal-first AI coding companion with persistent memory and enhanced search capabilities**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Powered by Ollama](https://img.shields.io/badge/Powered%20by-Ollama-ff6b6b.svg)](https://ollama.ai)

</div>

## Quick Start

### Option 1: With Gemini (Recommended)

```bash
# Install Songbird
pipx install songbird-ai

# Get your free Gemini API key
# Visit: https://aistudio.google.com/app/apikey

# Set your API key
export GOOGLE_API_KEY="your-api-key-here"

# Start coding with AI
songbird

# Continue your previous session
songbird --continue

# Resume from any previous session
songbird --resume
```

### Option 2: With Local Ollama

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

# Continue previous session with Ollama
songbird --provider ollama --continue
```

## Features\n\n### **Persistent Memory System** 🧠\n- **Session Persistence**: Automatic conversation saving with project-aware storage\n- **Seamless Continuation**: Resume exactly where you left off with `--continue`\n- **Session Browser**: Interactive menu to select from previous sessions with `--resume`\n- **Project Isolation**: Each git repository gets separate session storage\n- **Visual Replay**: Perfect restoration of conversation history with tool outputs\n\n### **Enhanced Search & Navigation** 🔍\n- **Smart File Search**: Type-specific search with `file_type` parameters (py, js, md, etc.)\n- **Glob Patterns**: Find files with patterns like `*.py`, `*test*.py`, `config.*`\n- **Rich Display**: Beautiful table output with file statistics and match counts\n- **Filename Detection**: Automatically detects filename vs content searches\n- **Cross-Platform**: Ripgrep integration with Python fallback

### **Flexible AI Options**
- **Cloud AI**: Use Google's powerful Gemini models for best performance and latest features
- **Local AI**: Run models locally with Ollama for privacy and offline use
- **Multiple Models**: Support for Gemini 2.0 Flash, Qwen2.5-Coder, CodeLlama, and more
- **Easy Switching**: Switch between providers with simple command flags

### **Developer Tools Integration**
- **File Search**: Lightning-fast code search with ripgrep integration
- **Smart Diffs**: Generate and preview code changes with colored diffs
- **Shell Integration**: Execute commands safely with built-in sandboxing
- **Git Workflow**: Seamless integration with version control

### **Safety & Security**
- **Repository Sandboxing**: Cannot access files outside your project
- **Diff Previews**: Review all changes before applying
- **Secret Filtering**: Automatically redact API keys and sensitive data
- **Command Allowlists**: Safe execution of shell commands

###  **Built for Quality**
- **Test-Driven Development**: Comprehensive test suite with >90% coverage
- **Type Safety**: Full type hints and static analysis
- **Modern Python**: Built with Python 3.10+ and modern packaging

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

# Use specific model
songbird --provider gemini --model gemini-2.0-flash-001
songbird --provider ollama --model qwen2.5-coder:7b

# Check available providers
songbird --list-providers

# Check version and commands
songbird --help
songbird version
```

## Usage Examples

```bash
# Basic chat session (auto-selects best provider)
songbird

# Use Gemini (powerful, cloud-based)
songbird --provider gemini

# Use Ollama (private, local)
songbird --provider ollama

# List available providers
songbird --list-providers

# Use specific models
songbird --provider gemini --model gemini-2.0-flash-001
songbird --provider ollama --model qwen2.5-coder:7b

# Show available commands
songbird --help

# Display version
songbird version
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

##  Roadmap

Songbird follows a **test-driven, phase-based development** approach:

- [x] **Phase 1**: LLM Provider Layer 
- [x] **Phase 2**: File Search (enhanced with type filtering and smart detection)
- [x] **Phase 3**: Patch Generation & Apply
- [x] **Phase 4**: Shell Execution (live streaming and cross-platform)
- [x] **Phase 5**: Conversation Orchestrator
- [x] **Phase 6**: Advanced UI/UX (interactive menus and rich displays)
- [x] **Phase 7**: Session Memory (complete with project-aware storage)
- [ ] **Phase 8**: MCP Server Protocol
- [ ] **Phase 9**: Model & Provider Management
- [ ] **Phase 10**: Safety & Permissions
- [ ] **Phase 11**: Plugin System



## Current Status

**Production Ready** - Songbird has completed **Phase 7** with persistent memory and enhanced capabilities.

**What works now:**
- ✅ **Persistent Memory**: Session management with project-aware storage
- ✅ **Enhanced Search**: File type filtering, glob patterns, and smart detection
- ✅ **Dual AI Providers**: Gemini AI and Ollama with seamless switching
- ✅ **Interactive Tools**: File operations with diff previews and confirmation menus
- ✅ **Live Shell Execution**: Real-time command output streaming
- ✅ **Cross-Platform**: Windows, macOS, and Linux support
- ✅ **Modern CLI**: Rich interface with syntax highlighting and visual feedback
- ✅ **Comprehensive Test Suite**: >90% coverage with TDD approach

**Coming soon:**
- MCP Server Protocol integration
- Advanced model and provider management
- Enhanced safety and permissions system
- Multiple LLM providers (OpenAI, Anthropic)


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
echo $GOOGLE_API_KEY

# Get a free API key
# Visit: https://aistudio.google.com/app/apikey

# Set API key permanently
echo 'export GOOGLE_API_KEY="your-key-here"' >> ~/.bashrc
source ~/.bashrc

# Test Gemini provider
songbird --provider gemini
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


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

**A terminal-first AI coding companion that runs primarily on local LLMs**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Powered by Ollama](https://img.shields.io/badge/Powered%20by-Ollama-ff6b6b.svg)](https://ollama.ai)

</div>

## Quick Start

```bash
# Install Songbird
pipx install songbird-ai

# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama and pull a model
ollama serve
ollama pull qwen2.5-coder:7b

# Start coding with AI
songbird chat
```

## Features

### **Local AI Power**
- **Privacy-First**: Run AI models locally with Ollama - no data leaves your machine
- **Offline Capable**: Work without internet connection once models are downloaded
- **Multiple Models**: Support for coding-optimized models like Qwen2.5-Coder, CodeLlama, and more

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
# Recommended: Qwen2.5-Coder (excellent for coding tasks)
ollama pull qwen2.5-coder:7b

# Alternatives
ollama pull codellama:7b        # Meta's CodeLlama
ollama pull llama3.2:3b         # General purpose, faster
ollama pull deepseek-coder:6.7b # DeepSeek Coder
```

### 4. Start Songbird

```bash
# Launch interactive chat
songbird chat

# Check version and commands
songbird --help
songbird version
```

## Usage Examples

```bash
# Basic chat session
songbird chat

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

- [x] **Phase 1**: LLM Provider Layer ✅
- [ ] **Phase 2**: File Search (ripgrep integration)
- [ ] **Phase 3**: Patch Generation & Apply
- [ ] **Phase 4**: Shell Execution
- [ ] **Phase 5**: Conversation Orchestrator
- [ ] **Phase 6**: MCP Server Protocol
- [ ] **Phase 7**: Session Memory
- [ ] **Phase 8**: Model & Provider Management
- [ ] **Phase 9**: Safety & Permissions
- [ ] **Phase 10**: Plugin System



## Current Status

**Early Development** - Songbird is currently at **Phase 1** with basic LLM integration complete.

**What works now:**
- ✅ CLI 
- ✅ Ollama LLM provider integration
- ✅ Basic chat functionality
- ✅ Modern Python packaging (pipx/uv support)
- ✅ Comprehensive test suite

**Coming soon:**
- File search and code analysis
- Intelligent code patching
- Advanced conversation memory
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
songbird models list
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


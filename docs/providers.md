# Songbird AI Provider Guide

This comprehensive guide covers all AI providers supported by Songbird, including setup instructions, available models, features, and troubleshooting.

## Table of Contents

- [Overview](#overview)
- [Provider Comparison](#provider-comparison)
- [Setup Guides](#setup-guides)
  - [Google Gemini (Recommended)](#google-gemini-recommended)
  - [GitHub Copilot](#github-copilot)
  - [OpenAI](#openai)
  - [Anthropic Claude](#anthropic-claude)
  - [OpenRouter](#openrouter)
  - [Ollama (Local)](#ollama-local)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Overview

Songbird supports **6 AI providers** offering a total of **100+ models** ranging from free local options to powerful cloud-based solutions. The system automatically selects the best available provider based on your configured API keys.

### Provider Priority (Auto-Selection Order)
1. **Gemini** (free, powerful, excellent tool calling)
2. **Claude** (subscription, outstanding coding capabilities)
3. **OpenAI** (subscription, reliable, fast)
4. **OpenRouter** (pay-per-use, multiple providers)
5. **GitHub Copilot** (subscription, IDE integration)
6. **Ollama** (free, local, privacy-focused)

## Provider Comparison

| Provider | Cost | Tool Calling | Best For | Models Available |
|----------|------|-------------|----------|------------------|
| **Gemini** | Free (generous limits) | Excellent | General coding, beginners | 4 models |
| **GitHub Copilot** | $10/month | Excellent | IDE integration, existing Copilot users | 30+ models |
| **OpenAI** | Pay-per-use | Excellent | Reliable workflows, enterprise | 10+ models |
| **Claude** | Pay-per-use | Outstanding | Complex coding, reasoning | 5 models |
| **OpenRouter** | Pay-per-use | Good | Cost optimization, model variety | 50+ models |
| **Ollama** | Free | Variable | Privacy, offline work | 100+ models |

## Setup Guides

### Google Gemini (Recommended)

**Why Gemini?** Free tier with generous limits, excellent function calling, and fast performance.

#### Setup Steps

1. **Get your free API key**
   ```bash
   # Visit Google AI Studio
   open https://aistudio.google.com/app/apikey
   ```

2. **Set environment variable**
   ```bash
   # Temporary (current session)
   export GEMINI_API_KEY="your-api-key-here"
   
   # Permanent (add to ~/.bashrc or ~/.zshrc)
   echo 'export GEMINI_API_KEY="your-api-key-here"' >> ~/.bashrc
   source ~/.bashrc
   ```

3. **Test the setup**
   ```bash
   songbird --provider gemini
   ```

#### Available Models
- `gemini-2.0-flash-001` (default) - Latest, fastest
- `gemini-1.5-pro` - More capable, slower
- `gemini-1.5-flash` - Balanced performance
- `gemini-1.0-pro` - Legacy, stable

#### Features
- ✅ Function calling (excellent)
- ✅ Streaming responses
- ✅ Usage tracking
- ✅ Large context window (1M+ tokens)
- ✅ Free tier: 15 requests/minute, 1 million tokens/minute

---

### GitHub Copilot

**Why Copilot?** Seamless integration with existing GitHub Copilot subscription, access to multiple model providers.

#### Prerequisites
- Active GitHub Copilot subscription ($10/month)
- VS Code with GitHub Copilot extension OR JetBrains IDE with Copilot plugin

#### Setup Steps

1. **Generate access token**

   **From VS Code:**
   ```bash
   # Open Command Palette (Ctrl+Shift+P / Cmd+Shift+P)
   # Type: "GitHub Copilot: Generate Access Token"
   # Copy the generated token
   ```

   **From JetBrains IDE:**
   ```bash
   # Go to Settings → Tools → GitHub Copilot
   # Click "Generate Token"
   # Copy the generated token
   ```

2. **Set environment variable**
   ```bash
   # Temporary (current session)
   export COPILOT_ACCESS_TOKEN="ghu_xxxxxxxxxxxxxxxxxxxx"
   
   # Permanent (add to ~/.bashrc or ~/.zshrc)
   echo 'export COPILOT_ACCESS_TOKEN="your-token-here"' >> ~/.bashrc
   source ~/.bashrc
   ```

3. **Test the setup**
   ```bash
   songbird --provider copilot
   ```

#### Available Models
Copilot provides access to 30+ models including:
- `gpt-4o` (default) - OpenAI's latest
- `gpt-4o-mini` - Faster, cost-effective
- `claude-3.5-sonnet` - Anthropic's best
- `claude-3.7-sonnet` - Enhanced reasoning
- Plus many more via dynamic discovery

#### Features
- ✅ Function calling (excellent)
- ✅ Streaming responses
- ✅ Usage tracking
- ✅ Multiple model providers
- ✅ Automatic model discovery (30+ models)

#### Token Management
- Tokens typically last several hours
- Refresh by generating new token in your IDE
- System shows clear error messages when token expires

---

### OpenAI

**Why OpenAI?** Industry standard, reliable performance, excellent documentation.

#### Setup Steps

1. **Get API key**
   ```bash
   # Visit OpenAI Platform
   open https://platform.openai.com/api-keys
   ```

2. **Set environment variable**
   ```bash
   # Temporary
   export OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxx"
   
   # Permanent
   echo 'export OPENAI_API_KEY="your-api-key-here"' >> ~/.bashrc
   source ~/.bashrc
   ```

3. **Test the setup**
   ```bash
   songbird --provider openai
   ```

#### Available Models
- `gpt-4o` (default) - Latest, multimodal
- `gpt-4o-mini` - Fast, cost-effective
- `gpt-4-turbo` - Enhanced capabilities
- `gpt-4` - Proven reliability
- `gpt-3.5-turbo` - Budget-friendly

#### Features
- ✅ Function calling (excellent)
- ✅ Streaming responses
- ✅ Usage tracking
- ✅ Reliable performance
- ✅ Fast response times

#### Pricing
- GPT-4o: $5.00/1M input tokens, $15.00/1M output tokens
- GPT-4o-mini: $0.15/1M input tokens, $0.60/1M output tokens
- Check latest pricing at [OpenAI Pricing](https://openai.com/api/pricing/)

---

### Anthropic Claude

**Why Claude?** Outstanding coding capabilities, excellent reasoning, large context windows.

#### Setup Steps

1. **Get API key**
   ```bash
   # Visit Anthropic Console
   open https://console.anthropic.com/account/keys
   ```

2. **Set environment variable**
   ```bash
   # Temporary
   export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxxxxxxxxxx"
   
   # Permanent
   echo 'export ANTHROPIC_API_KEY="your-api-key-here"' >> ~/.bashrc
   source ~/.bashrc
   ```

3. **Test the setup**
   ```bash
   songbird --provider claude
   ```

#### Available Models
- `claude-3-5-sonnet-20241022` (default) - Best overall
- `claude-3-5-haiku-20241022` - Fast, efficient
- `claude-3-opus-20240229` - Most capable
- `claude-3-sonnet-20240229` - Balanced
- `claude-3-haiku-20240307` - Fastest

#### Features
- ✅ Function calling (outstanding)
- ✅ Streaming responses
- ✅ Usage tracking
- ✅ Large context (200K tokens)
- ✅ Excellent code understanding

#### Pricing
- Claude 3.5 Sonnet: $3.00/1M input tokens, $15.00/1M output tokens
- Claude 3.5 Haiku: $0.25/1M input tokens, $1.25/1M output tokens
- Check latest pricing at [Anthropic Pricing](https://www.anthropic.com/api)

---

### OpenRouter

**Why OpenRouter?** Access to multiple providers through one API, pay-per-use pricing, cost optimization.

#### Setup Steps

1. **Get API key**
   ```bash
   # Visit OpenRouter
   open https://openrouter.ai/keys
   ```

2. **Set environment variable**
   ```bash
   # Temporary
   export OPENROUTER_API_KEY="sk-or-xxxxxxxxxxxxxxxxxxxx"
   
   # Permanent
   echo 'export OPENROUTER_API_KEY="your-api-key-here"' >> ~/.bashrc
   source ~/.bashrc
   ```

3. **Test the setup**
   ```bash
   songbird --provider openrouter
   ```

#### Available Models
OpenRouter provides access to 50+ models from multiple providers:
- `anthropic/claude-3.5-sonnet` (default)
- `openai/gpt-4o`
- `google/gemini-2.0-flash-001`
- `deepseek/deepseek-chat-v3-0324:free` (free)
- `meta-llama/llama-3.2-90b-vision-instruct`
- Many more with automatic discovery

#### Features
- ✅ Function calling (varies by model)
- ✅ Streaming responses
- ✅ Usage tracking
- ✅ Multiple providers
- ✅ Competitive pricing

#### Benefits
- Access models from multiple providers with one API key
- Pay only for what you use
- Free models available
- Often lower costs than direct provider pricing

---

### Ollama (Local)

**Why Ollama?** Complete privacy, no API costs, offline capability, full control.

#### Setup Steps

1. **Install Ollama**

   **Linux/WSL:**
   ```bash
   curl -fsSL https://ollama.ai/install.sh | sh
   ```

   **macOS:**
   ```bash
   brew install ollama
   ```

   **Windows:**
   ```bash
   # Download from https://ollama.ai/download
   ```

2. **Start Ollama server**
   ```bash
   ollama serve
   ```

3. **Pull a coding model**
   ```bash
   # Recommended for coding
   ollama pull qwen2.5-coder:7b
   
   # Alternatives
   ollama pull deepseek-coder:6.7b
   ollama pull codellama:7b
   ollama pull llama3.2:latest
   ```

4. **Test the setup**
   ```bash
   songbird --provider ollama
   ```

#### Recommended Models for Coding
- `qwen2.5-coder:7b` (default) - Excellent coding capabilities
- `qwen2.5-coder:14b` - More capable, requires more RAM
- `deepseek-coder:6.7b` - Strong code understanding
- `codellama:7b` - Meta's coding specialist
- `llama3.2:latest` - General purpose, good balance

#### Features
- ✅ Function calling (varies by model)
- ✅ Streaming responses
- ✅ Usage tracking
- ✅ Complete privacy
- ✅ No API costs

#### System Requirements
- **Minimum:** 8GB RAM for 7B models
- **Recommended:** 16GB RAM for 14B models, 32GB for 32B models
- **Storage:** 4-20GB per model
- **OS:** Linux, macOS, Windows

#### Model Management
```bash
# List available models
ollama list

# Pull new models
ollama pull model-name

# Remove models
ollama rm model-name

# Update models
ollama pull model-name  # pulls latest version
```

## Advanced Configuration

### Custom API Base URLs

You can configure custom API endpoints for any provider:

```bash
# Custom OpenAI endpoint
songbird --provider openai --provider-url https://your-custom-api.com/v1

# Custom OpenRouter endpoint
songbird --provider openrouter --provider-url https://custom-router.example.com/api/v1
```

### Model Switching During Conversations

Songbird supports dynamic model switching without restarting sessions:

```bash
# Interactive model menu
/model

# Switch directly
/model gpt-4o
/model claude-3.5-sonnet-20241022
/model qwen2.5-coder:7b

# Refresh model cache
/model --refresh
```

### Session Management with Providers

```bash
# Continue with specific provider
songbird --provider claude --continue

# Resume with different provider
songbird --provider openai --resume
```

## Troubleshooting

### Common Issues

#### Authentication Errors

**Gemini:**
```bash
# Check API key
echo $GEMINI_API_KEY

# Test with curl
curl -H "x-goog-api-key: $GEMINI_API_KEY" \
  "https://generativelanguage.googleapis.com/v1/models"
```

**OpenAI:**
```bash
# Check API key format (should start with sk-)
echo $OPENAI_API_KEY | grep "^sk-"

# Test with curl
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  "https://api.openai.com/v1/models"
```

**Claude:**
```bash
# Check API key format (should start with sk-ant-)
echo $ANTHROPIC_API_KEY | grep "^sk-ant-"

# Test with curl
curl -H "x-api-key: $ANTHROPIC_API_KEY" \
  "https://api.anthropic.com/v1/models"
```

**GitHub Copilot:**
```bash
# Check token format (should start with ghu_)
echo $COPILOT_ACCESS_TOKEN | grep "^ghu_"

# If expired, generate new token from VS Code/IDE
# VS Code: Command Palette → "GitHub Copilot: Generate Access Token"
```

**Ollama:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve

# Check available models
ollama list
```

#### Connection Issues

```bash
# Check internet connectivity
ping api.openai.com

# Check firewall/proxy settings
curl -v https://api.openai.com/v1/models

# For corporate networks, check proxy configuration
export https_proxy=http://your-proxy:port
```

#### Model Not Available

```bash
# Refresh model discovery
songbird --provider YOUR_PROVIDER
/model --refresh

# For Ollama, pull the model
ollama pull model-name

# Check provider status
songbird --list-providers
```

### Error Messages and Solutions

| Error | Solution |
|-------|----------|
| "API key not found" | Set the appropriate environment variable |
| "Model not available" | Use `/model` to see available models |
| "Rate limit exceeded" | Wait and retry, or switch providers |
| "Connection timeout" | Check internet connection and firewall |
| "Token expired" (Copilot) | Generate new token from IDE |
| "Ollama not running" | Start with `ollama serve` |

## Best Practices

### Provider Selection

1. **Start with Gemini** - Free, reliable, excellent for learning
2. **Use Copilot** if you already have a subscription
3. **Choose Claude** for complex coding tasks
4. **Use OpenAI** for enterprise/production workflows
5. **Try OpenRouter** for cost optimization
6. **Use Ollama** for privacy-sensitive projects

### Cost Optimization

1. **Use free tiers first** (Gemini, Ollama)
2. **Monitor usage** with `/model` command
3. **Switch to cheaper models** for simple tasks
4. **Use OpenRouter** for competitive pricing
5. **Local models** for development/testing

### Performance Tips

1. **Cache results** with session continuation (`--continue`)
2. **Use appropriate models** for task complexity
3. **Monitor response times** and switch if needed
4. **Local models** for low-latency requirements

### Security Considerations

1. **Never commit API keys** to version control
2. **Use environment variables** for key storage
3. **Rotate keys regularly** per provider recommendations
4. **Use local models** for sensitive code
5. **Monitor usage** for unauthorized access

---

## Quick Reference

### Environment Variables
```bash
export GEMINI_API_KEY="your-key"
export COPILOT_ACCESS_TOKEN="your-token"
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export OPENROUTER_API_KEY="your-key"
# Ollama requires no API key
```

### Basic Commands
```bash
# Auto-select provider
songbird

# Specific provider
songbird --provider PROVIDER_NAME

# List providers and models
songbird --list-providers

# Continue/resume sessions
songbird --continue
songbird --resume

# In-chat model switching
/model
/model MODEL_NAME
```

### Getting Help
```bash
# Command help
songbird --help

# In-chat help
/help
/help model

# Check provider status
songbird --list-providers
```

Need more help? Check the [main README](../README.md) or [open an issue](https://github.com/Spandan7724/songbird/issues) on GitHub.
# Ollama Integration for Str33tRace

This document provides information about using Ollama with Str33tRace.

## Overview

The Ollama integration allows you to use locally running Ollama models with the Str33tRace tooling framework. Ollama provides access to various open-source large language models that can be run locally on your machine.

## Setup

### Installing Ollama

1. Install Ollama by following the instructions at [ollama.ai](https://ollama.ai)
2. Pull a model you'd like to use: `ollama pull llama3:8b` (or another model of your choice)

### Configuration

The Ollama integration supports the following configuration options:

- `OLLAMA_API_URL`: The URL where your Ollama server is running (defaults to `http://localhost:11434`)

### Running with Ollama

There are several ways to start Str33tRace with Ollama:

```bash
# Use Ollama explicitly
python main.py --provider ollama

# Use a specific Ollama model
python main.py --provider ollama --model llama3:70b

# Use Ollama with a specific API endpoint
OLLAMA_API_URL=http://myollama:11434 python main.py --provider ollama
```

## Supported Models

The Ollama integration should work with any Ollama model that supports the chat API and function calling, including:

- `llama3` - This is the default model if none is specified
- `mixtral`
- `gemma`
- `mistral`
- And other models with tool/function calling support

Note that tool calling support may vary by model. Models with native tool/function calling capabilities will work best.

## Limitations

- Local models may not perform as well as cloud-based models like Anthropic or Gemini
- Some models may have limited context windows compared to commercial models
- Token counting is estimated rather than precise
- Tool/function calling is implemented following the OpenAI format, which some models may support with varying degrees of effectiveness

## Troubleshooting

If you encounter issues with the Ollama integration:

1. Make sure Ollama is running locally: `ollama serve`
2. Verify you can call the model directly: `ollama run llama3`
3. Check that the model supports function/tool calling
4. Examine the log files for detailed error messages
5. Try a different model if one model isn't performing well

For any persistent issues, please open an issue on the project repository.
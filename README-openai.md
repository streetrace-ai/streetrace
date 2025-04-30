# OpenAI Integration for Str33tRace

This integration allows you to use OpenAI's models (like GPT-4 Turbo) with the Str33tRace framework.

## Setup

1. Make sure you have an OpenAI API key. If you don't have one, sign up at [OpenAI Platform](https://platform.openai.com).

2. Set your API key as an environment variable:
   ```bash
   export OPENAI_API_KEY=your_openai_api_key_here
   ```

3. (Optional) If you're using a custom API endpoint, set it as an environment variable:
   ```bash
   export OPENAI_API_BASE=your_custom_api_endpoint
   ```

4. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

You can use the OpenAI integration with the `--provider` flag:

```bash
python main.py --provider openai
```

Or you can specify a specific model:

```bash
python main.py --provider openai --model gpt-4-turbo-2024-04-09
```

Available models include:
- `gpt-4-turbo-2024-04-09` (default)
- `gpt-4-1106-preview`
- `gpt-4o-2024-05-13`
- `gpt-3.5-turbo`

You can also provide a prompt directly:

```bash
python main.py --provider openai --prompt "Create a simple Python function to calculate factorial"
```

## Custom System Message

You can customize the system message by creating a file at `.streetrace/system.md`. This message will be used as the system prompt for the AI.

## Troubleshooting

1. **API Key Issues**: Ensure your API key is set correctly in the environment variables.

2. **Model Limitations**: Different models have different token limits and capabilities. If you're experiencing issues, try switching to a more capable model.

3. **Rate Limits**: OpenAI has rate limits on API requests. If you're hitting rate limits, the tool will retry with exponential backoff, but you might need to wait or upgrade your OpenAI account.

4. **Tool Calling Issues**: If the model is not correctly calling tools, ensure you're using a model that supports tool calling (like `gpt-4-turbo` or `gpt-4o`).

5. **Output Quality**: If you're not satisfied with the output quality, try using a more powerful model or adjusting your prompt.

## API Documentation

For more information on the OpenAI API, visit the [OpenAI API Documentation](https://platform.openai.com/docs/api-reference).
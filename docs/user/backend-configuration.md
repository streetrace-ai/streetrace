# Backend Configuration Guide

This guide explains how to configure Streetrace with various LLM backends. Streetrace uses LiteLLM to access different LLM providers through a unified interface. Visit [LiteLLM documentation](https://docs.litellm.ai/docs/providers) for further details.

## Overview

Streetrace supports multiple LLM backends through LiteLLM. Each backend requires:

1. **Backend Configuration**: Setting up API keys and access through the provider's platform
2. **Streetrace Configuration**: Configuring environment variables and model names
3. **Model Examples**: Using specific models with Streetrace

## OpenAI

### Backend Configuration

1. **Create OpenAI Account**: Visit [platform.openai.com](https://platform.openai.com) and sign up
2. **Generate API Key**: Go to API Keys section and create a new secret key
3. **Set Usage Limits**: Configure billing limits in the Usage section (recommended)

### Streetrace Configuration

Set your OpenAI API key as an environment variable:

```bash
export OPENAI_API_KEY="sk-your-openai-api-key-here"
```

### Model Examples

```bash
# GPT-4o (latest)
streetrace --model=gpt-4o

# GPT-4 Turbo
streetrace --model=gpt-4-turbo

# GPT-3.5 Turbo
streetrace --model=gpt-3.5-turbo
```

## OpenAI-Compatible Endpoints

### Backend Configuration

Many providers offer OpenAI-compatible endpoints. Examples include:

- **Together AI**: Get API key from [api.together.ai](https://api.together.ai)
- **Groq**: Get API key from [console.groq.com](https://console.groq.com)
- **Perplexity**: Get API key from [perplexity.ai](https://perplexity.ai)
- **DeepSeek**: Get API key from [platform.deepseek.com](https://platform.deepseek.com)

### Streetrace Configuration

For Together AI:

```bash
export TOGETHERAI_API_KEY="your-together-ai-api-key"
```

For Groq:

```bash
export GROQ_API_KEY="your-groq-api-key"
```

For Perplexity:

```bash
export PERPLEXITYAI_API_KEY="your-perplexity-api-key"
```

For DeepSeek:

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
```

For custom OpenAI-compatible endpoints, you can also set:

```bash
export OPENAI_BASE_URL="https://your-custom-endpoint.com/v1"
export OPENAI_API_KEY="your-api-key"
```

### Model Examples

```bash
# DeepSeek models via DeepSeek API
streetrace --model=deepseek/deepseek-chat
streetrace --model=deepseek/deepseek-coder

# Models via Together AI
streetrace --model=together_ai/meta-llama/Llama-3.2-70B-Instruct-Turbo
streetrace --model=together_ai/mistralai/Codestral-22B-v0.1

# Models via Groq
streetrace --model=groq/llama-3.1-70b-versatile
streetrace --model=groq/mixtral-8x7b-32768
```

## Azure OpenAI

### Backend Configuration

1. **Create Azure Account**: Sign up at [portal.azure.com](https://portal.azure.com)

2. **Create OpenAI Resource**:

   ```bash
   # Using Azure CLI
   az login
   az account set --subscription "your-subscription-id"

   # Create resource group (if needed)
   az group create --name "rg-openai-streetrace" --location "eastus"

   # Create Azure OpenAI resource
   az cognitiveservices account create \
     --name "openai-streetrace" \
     --resource-group "rg-openai-streetrace" \
     --location "eastus" \
     --kind "OpenAI" \
     --sku "S0" \
     --subscription "your-subscription-id"
   ```

3. **Assign Required Roles**:

   ```bash
   # Get your user principal ID
   USER_ID=$(az ad signed-in-user show --query id -o tsv)

   # Assign Cognitive Services OpenAI User role
   az role assignment create \
     --assignee "$USER_ID" \
     --role "Cognitive Services OpenAI User" \
     --scope "/subscriptions/your-subscription-id/resourceGroups/rg-openai-streetrace/providers/Microsoft.CognitiveServices/accounts/openai-streetrace"
   ```

4. **Deploy Models**:

   ```bash
   # Deploy GPT-4o
   az cognitiveservices account deployment create \
     --resource-group "rg-openai-streetrace" \
     --account-name "openai-streetrace" \
     --deployment-name "gpt-4o-deployment" \
     --model-name "gpt-4o" \
     --model-version "2024-08-06" \
     --sku-capacity 10 \
     --sku-name "Standard"

   # Deploy GPT-4 Turbo
   az cognitiveservices account deployment create \
     --resource-group "rg-openai-streetrace" \
     --account-name "openai-streetrace" \
     --deployment-name "gpt-4-turbo-deployment" \
     --model-name "gpt-4" \
     --model-version "turbo-2024-04-09" \
     --sku-capacity 10 \
     --sku-name "Standard"
   ```

5. **Get Credentials**:

   ```bash
   # Get API key
   az cognitiveservices account keys list \
     --resource-group "rg-openai-streetrace" \
     --name "openai-streetrace" \
     --query "key1" -o tsv

   # Get endpoint
   az cognitiveservices account show \
     --resource-group "rg-openai-streetrace" \
     --name "openai-streetrace" \
     --query "properties.endpoint" -o tsv
   ```

### Streetrace Configuration

```bash
export AZURE_API_KEY="your-azure-openai-api-key"
export AZURE_API_BASE="https://your-resource-name.openai.azure.com/"
export AZURE_API_VERSION="2024-02-01"
```

### Model Examples

```bash
# GPT-4o (use your deployment name)
streetrace --model=azure/your-gpt-4o-deployment

# GPT-4 Turbo
streetrace --model=azure/your-gpt-4-turbo-deployment

# GPT-3.5 Turbo
streetrace --model=azure/your-gpt-35-turbo-deployment
```

## Azure AI Studio

### Backend Configuration

1. **Access Azure AI Studio**: Go to [ai.azure.com](https://ai.azure.com)

2. **Create Hub and Project**:

   ```bash
   # Create an AI Hub first
   az ml workspace create \
     --resource-group "rg-openai-streetrace" \
     --name "ai-hub-streetrace" \
     --location "eastus" \
     --kind "Hub"

   # Create an AI Project under the hub
   az ml workspace create \
     --resource-group "rg-openai-streetrace" \
     --name "ai-project-streetrace" \
     --location "eastus" \
     --kind "Project" \
     --hub-id "/subscriptions/your-subscription-id/resourceGroups/rg-openai-streetrace/providers/Microsoft.MachineLearningServices/workspaces/ai-hub-streetrace"
   ```

3. **Assign Required Roles**:

   ```bash
   # Get your user principal ID
   USER_ID=$(az ad signed-in-user show --query id -o tsv)

   # Assign Azure AI Developer role
   az role assignment create \
     --assignee "$USER_ID" \
     --role "Azure AI Developer" \
     --scope "/subscriptions/your-subscription-id/resourceGroups/rg-openai-streetrace/providers/Microsoft.MachineLearningServices/workspaces/ai-project-streetrace"

   # Assign Cognitive Services OpenAI User role for model access
   az role assignment create \
     --assignee "$USER_ID" \
     --role "Cognitive Services OpenAI User" \
     --scope "/subscriptions/your-subscription-id/resourceGroups/rg-openai-streetrace"
   ```

4. **Deploy Models via CLI** (Alternative to web interface):

   ```bash
   # Create deployment configuration file
   cat > deployment.yml << EOF
   name: gpt-4o-deployment
   model: gpt-4o
   model_version: 2024-08-06
   instance_type: Standard_DS3_v2
   instance_count: 1
   EOF

   # Deploy the model
   az ml model deploy \
     --resource-group "rg-openai-streetrace" \
     --workspace-name "ai-project-streetrace" \
     --file deployment.yml
   ```

5. **Get Connection Details**:

   ```bash
   # List deployed models and their endpoints
   az ml online-endpoint list \
     --resource-group "rg-openai-streetrace" \
     --workspace-name "ai-project-streetrace"

   # Get specific endpoint details
   az ml online-endpoint show \
     --resource-group "rg-openai-streetrace" \
     --workspace-name "ai-project-streetrace" \
     --name "gpt-4o-deployment"
   ```

### Streetrace Configuration

```bash
export AZURE_API_KEY="your-azure-ai-studio-api-key"
export AZURE_API_BASE="https://your-endpoint.inference.ai.azure.com"
```

### Model Examples

```bash
# Models available through Azure AI Studio Model Catalog
streetrace --model=azure_ai/gpt-4o
streetrace --model=azure_ai/gpt-4-turbo
streetrace --model=azure_ai/mistral-large
```

## Vertex AI

### Backend Configuration

1. **Create Google Cloud Project**:

   ```bash
   # Install gcloud CLI first: https://cloud.google.com/sdk/docs/install
   gcloud auth login

   # Create a new project
   gcloud projects create streetrace-vertex-ai --name="Streetrace Vertex AI"

   # Set the project as active
   gcloud config set project streetrace-vertex-ai

   # Link billing account (required for API usage)
   gcloud billing projects link streetrace-vertex-ai --billing-account="YOUR-BILLING-ACCOUNT-ID"
   ```

2. **Enable Required APIs**:

   ```bash
   # Enable Vertex AI API
   gcloud services enable aiplatform.googleapis.com

   # Enable additional APIs for model access
   gcloud services enable ml.googleapis.com
   gcloud services enable compute.googleapis.com
   gcloud services enable generativeai.googleapis.com
   ```

3. **Create Service Account and Assign Roles**:

   ```bash
   # Create service account
   gcloud iam service-accounts create streetrace-vertex-sa \
     --description="Service account for Streetrace Vertex AI access" \
     --display-name="Streetrace Vertex AI"

   # Get project ID
   PROJECT_ID=$(gcloud config get-value project)

   # Assign required roles
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:streetrace-vertex-sa@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/aiplatform.user"

   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:streetrace-vertex-sa@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/ml.developer"

   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:streetrace-vertex-sa@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/serviceusage.serviceUsageConsumer"
   ```

4. **Generate Service Account Key**:

   ```bash
   # Create and download service account key
   gcloud iam service-accounts keys create ~/streetrace-vertex-key.json \
     --iam-account=streetrace-vertex-sa@$PROJECT_ID.iam.gserviceaccount.com

   # Alternative: Use application default credentials (recommended for development)
   gcloud auth application-default login
   ```

5. **Enable Model Access** (for specific models):

   ```bash
   # Enable Claude models in Vertex AI Model Garden (requires manual approval in console)
   echo "Visit https://console.cloud.google.com/vertex-ai/model-garden to enable Claude models"

   # List available models
   gcloud ai models list --region=us-central1
   ```

6. **Set Location/Region**:
   ```bash
   # Set default region for Vertex AI
   gcloud config set ai/region us-central1
   ```

### Streetrace Configuration

Using service account:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
export VERTEXAI_PROJECT="your-gcp-project-id"
export VERTEXAI_LOCATION="us-central1"
```

Using gcloud auth:

```bash
gcloud auth application-default login
export VERTEXAI_PROJECT="your-gcp-project-id"
export VERTEXAI_LOCATION="us-central1"
```

### Model Examples

```bash
# Claude models via Vertex AI Model Garden
streetrace --model=vertex_ai/claude-3-5-sonnet@20241022
streetrace --model=vertex_ai/claude-3-haiku@20240307

# Gemini models
streetrace --model=vertex_ai/gemini-1.5-pro
streetrace --model=vertex_ai/gemini-1.5-flash

# Codestral via Vertex AI Model Garden
streetrace --model=vertex_ai/codestral-22b
```

## Gemini (Google AI Studio)

### Backend Configuration

1. **Set up Google Cloud Project** (if not already done):

   ```bash
   # Install gcloud CLI: https://cloud.google.com/sdk/docs/install
   gcloud auth login

   # Create project (or use existing)
   gcloud projects create streetrace-gemini --name="Streetrace Gemini"
   gcloud config set project streetrace-gemini

   # Link billing account (required)
   gcloud billing projects link streetrace-gemini --billing-account="YOUR-BILLING-ACCOUNT-ID"
   ```

2. **Enable Generative AI API**:

   ```bash
   # Enable the required API
   gcloud services enable generativelanguage.googleapis.com
   ```

3. **Create API Key via CLI**:

   ```bash
   # Create API key for Gemini
   gcloud alpha services api-keys create \
     --display-name="Streetrace Gemini API Key" \
     --api-target=service=generativelanguage.googleapis.com

   # Get the API key value (save this securely)
   gcloud alpha services api-keys get-key-string API_KEY_ID
   ```

4. **Alternative: Get API Key via Web Interface**:

   - Visit [aistudio.google.com](https://aistudio.google.com)
   - Click "Get API key" → "Create API key in new project"
   - Select your project and create the key
   - Copy and securely store the API key

5. **Test API Access**:
   ```bash
   # Test the API key works
   curl -X POST \
     -H "Content-Type: application/json" \
     -H "x-goog-api-key: YOUR-API-KEY" \
     -d '{"contents":[{"parts":[{"text":"Hello"}]}]}' \
     "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
   ```

### Streetrace Configuration

```bash
export GEMINI_API_KEY="your-gemini-api-key"
# Alternative:
export GOOGLE_API_KEY="your-gemini-api-key"
```

### Model Examples

```bash
# Gemini models
streetrace --model=gemini/gemini-1.5-pro
streetrace --model=gemini/gemini-1.5-flash
streetrace --model=gemini/gemini-1.0-pro
```

## Anthropic

### Backend Configuration

1. **Create Account**: Sign up at [console.anthropic.com](https://console.anthropic.com)
2. **Generate API Key**: Go to API Keys section and create a new key
3. **Set Usage Limits**: Configure spending limits if desired

### Streetrace Configuration

```bash
export ANTHROPIC_API_KEY="sk-ant-your-anthropic-api-key"
```

### Model Examples

```bash
# Claude models
streetrace --model=claude-3-5-sonnet-20241022
streetrace --model=claude-3-5-haiku-20241022
streetrace --model=claude-3-opus-20240229
```

## Amazon Bedrock

### Backend Configuration

There are **two options** to access Amazon Bedrock models:

- Using the Bedrock API Key
- Or using the AWS credentials

**Request Model Access**:
**Note:** Before using Amazon Bedrock, you must enable required models in your AWS Account. See [Amazon Bedrock documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access-modify.html).  

#### Using the Amazon Bedrock API Key

Create a Bedrock API Key by going to AWS Console -> Amazon Bedrock -> API Keys, and create the
API Key. Then export the key in your environment:

```bash
export AWS_BEARER_TOKEN_BEDROCK="your-bedrock-api-key"
```
See [Amazon Bedrock documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html) for further details and security considerations.

#### Using AWS Credentials

1. **Create IAM User and Policy for Bedrock**:

   ```bash
   # Create IAM user for Streetrace
   aws iam create-user --user-name streetrace-bedrock-user

   # Create policy for Bedrock access
   cat > bedrock-policy.json << 'EOF'
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "bedrock:InvokeModel*",
           "bedrock:InvokeModelWithResponseStream"
         ],
         "Resource": "arn:aws:bedrock:*:*:foundation-model/*"
       },
       {
         "Effect": "Allow",
         "Action": [
           "bedrock:ListFoundationModels",
           "bedrock:GetFoundationModel"
         ],
         "Resource": "*"
       }
     ]
   }
   EOF

   # Create the policy
   aws iam create-policy \
     --policy-name StreetraceBedrockAccessPolicy \
     --policy-document file://bedrock-policy.json

   # Get AWS account ID
   ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

   # Attach policy to user
   aws iam attach-user-policy \
     --user-name streetrace-bedrock-user \
     --policy-arn "arn:aws:iam::$ACCOUNT_ID:policy/StreetraceBedrockAccessPolicy"
   ```

3. **Create Access Keys**:

   ```bash
   # Create access keys for the user
   aws iam create-access-key --user-name streetrace-bedrock-user
   # Save the AccessKeyId and SecretAccessKey from the output
   ```

**Important Note:** Amazon highly recommends using short-term access keys when possible to make programmatic calls to AWS or to use the AWS Command Line Interface. Always check [AWS documentation](https://docs.aws.amazon.com/IAM/latest/UserGuide/security-creds-programmatic-access.html#security-creds-alternatives-to-long-term-access-keys) for the latest security considerations and best practices.
   
### Streetrace Configuration

Using AWS credentials:

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION_NAME="us-east-1"
```

Using AWS CLI profile:
**Note:** Check [AWS documentation](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-quickstart.html#getting-started-quickstart-new) on how to create credentials profile  

```bash
export AWS_PROFILE_NAME="your-profile-name"
export AWS_REGION_NAME="us-east-1"
```

### Model Examples

```bash
# Claude models
streetrace --model=bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0
streetrace --model=bedrock/us.anthropic.claude-3-7-sonnet-20250219-v1:0 # Using inference profile

# Mistral models including Codestral
streetrace --model=bedrock/mistral.mistral-7b-instruct-v0:2
streetrace --model=bedrock/mistral.codestral-22b-instruct-v1:0
```

### Troubleshooting

```
LLM error: litellm.BadRequestError: BedrockException - {"message":"Invocation of model ID anthropic.claude-sonnet-4-20250514-v1:0 with on-demand throughput isn’t supported. Retry your request with the ID or ARN of an inference profile that contains this model."}
```

Go to AWS Bedrock console -> Cross-region inference -> copy the CRIS ARN of the model in your region and use it as `--model=bedrock/ARN` parameter when running Streetrace.

## LiteLLM Proxy

### Backend Configuration

1. **Install LiteLLM**: `pip install litellm[proxy]`
2. **Create Config**: Create a `config.yaml` file with your model configurations
3. **Start Proxy**: Run `litellm --config config.yaml`

Example config.yaml:

```yaml
model_list:
  - model_name: claude-3-sonnet
    litellm_params:
      model: anthropic/claude-3-sonnet-20240229
      api_key: os.environ/ANTHROPIC_API_KEY
  - model_name: gemini-pro
    litellm_params:
      model: gemini/gemini-1.5-pro
      api_key: os.environ/GOOGLE_API_KEY
  - model_name: gpt-4
    litellm_params:
      model: openai/gpt-4
      api_key: os.environ/OPENAI_API_KEY
  - model_name: deepseek-chat
    litellm_params:
      model: deepseek/deepseek-chat
      api_key: os.environ/DEEPSEEK_API_KEY
  - model_name: codestral
    litellm_params:
      model: mistral/codestral-22b-instruct-v1:0
      api_key: os.environ/MISTRAL_API_KEY
```

### Streetrace Configuration

```bash
export OPENAI_API_BASE="http://localhost:4000"  # LiteLLM proxy URL
export OPENAI_API_KEY="anything"  # Can be anything for local proxy
```

### Model Examples

```bash
# Models through your LiteLLM proxy (use names from your config)
streetrace --model=claude-3-sonnet
streetrace --model=gemini-pro
streetrace --model=gpt-4
streetrace --model=deepseek-chat
streetrace --model=codestral
```

## Cohere

### Backend Configuration

1. **Create Account**: Sign up at [dashboard.cohere.ai](https://dashboard.cohere.ai)
2. **Generate API Key**: Go to API Keys section and create a new key
3. **Choose Plan**: Select appropriate pricing plan

### Streetrace Configuration

```bash
export COHERE_API_KEY="your-cohere-api-key"
```

### Model Examples

```bash
# Cohere models
streetrace --model=cohere/command-r-plus
streetrace --model=cohere/command-r
streetrace --model=cohere/command-light
```

## Ollama

### Backend Configuration

1. **Install Ollama**: Download from [ollama.ai](https://ollama.ai)
2. **Start Ollama**: Run `ollama serve`
3. **Pull Models**: Use `ollama pull <model-name>` to download models

Example:

```bash
ollama pull llama3.1
ollama pull codellama
ollama pull deepseek-coder
ollama pull mistral
```

### Streetrace Configuration

```bash
export OLLAMA_API_BASE="http://localhost:11434"  # Default Ollama URL
```

### Model Examples

```bash
# DeepSeek models
streetrace --model=ollama/deepseek-coder
streetrace --model=ollama/deepseek-llm

# Codestral (if available)
streetrace --model=ollama/codestral

# Other popular models
streetrace --model=ollama/llama3.1
streetrace --model=ollama/codellama
streetrace --model=ollama/mistral
```

## Nebius AI Studio

### Backend Configuration

1. **Create Account**: Sign up at [studio.nebius.ai](https://studio.nebius.ai)
2. **Generate API Key**: Create API key in your account settings
3. **Choose Models**: Select from available models in the catalog

### Streetrace Configuration

```bash
export NEBIUS_API_KEY="your-nebius-api-key"
export NEBIUS_API_BASE="https://api.studio.nebius.ai/v1"
```

### Model Examples

```bash
# Models available through Nebius AI Studio (check current catalog)
streetrace --model=nebius/llama-3.1-70b-instruct
streetrace --model=nebius/mistral-7b-instruct
streetrace --model=nebius/deepseek-coder-33b-instruct
```

## General Usage Tips

### Environment Variables

You can create a `.env` file in your project root:

```bash
# .env file
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
GOOGLE_API_KEY=your-gemini-key
DEEPSEEK_API_KEY=your-deepseek-key
# Add other keys as needed
```

### Model Selection

Always check the latest model names and availability:

- Provider documentation for current model names
- Use `streetrace --model=<model-name>` format
- Some models may require specific regions or additional setup

### Troubleshooting

Common issues:

1. **Invalid API Key**: Verify the key is correct and has proper permissions
2. **Model Not Found**: Check if the model name is correct and available
3. **Rate Limiting**: Some providers have rate limits; wait or upgrade your plan
4. **Region Restrictions**: Some models may not be available in all regions

For more detailed troubleshooting, check the LiteLLM documentation and your provider's API documentation.

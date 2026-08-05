# Agent Gateway Ingress Client (`client_agent.py`)

This directory contains the Ingress client ADK agent script that connects to  Google Search & Analysis Agent in the GCP Agent Registry via the Agent-to-Agent (A2A) Gateway.

## Files
* `client_agent.py`: Asynchronous client script using `google.adk.integrations.agent_registry.AgentRegistry` and `InMemoryRunner` to stream responses from the remote A2A agent.

## Features
* **Automatic Discovery**: Queries `GCP Agent Registry` for the deployed agent matching `TARGET_DISPLAY_NAME` (`"Google Search & Analysis Agent"` by default).
* **ADK `_clean_name` Monkeypatch**: Solves regex validation issues in `google-adk` when agent names include special characters or spaces.
* **mTLS Compatibility**: Automatically disables client certificate checks (`should_use_client_cert = lambda: False`) to prevent `SSLCertVerificationError` on macOS local development environments.
* **Streaming Responses**: Streams real-time tokens received from the remote agent over the A2A Gateway.

## Usage

Run from the project root using `uv`:

```bash
uv run python3 agent_gateway/ingress/client_agent.py
```

Or pass a custom query as a command-line argument:

```bash
uv run python3 agent_gateway/ingress/client_agent.py "Gemini 2.5 Flash 모델의 특징을 설명해줘."
```

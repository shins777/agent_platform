Please build a Google ADK (Agent Development Kit) Search Agent platform on Google Cloud Platform with Vertex AI Agent Engine and GCP Agent Registry A2A protocol support. Implement all the following files step by step under `agent_gateway/agent/`:

1. `agent_gateway/agent/agent.py`:
- Import `Agent` from `google.adk.agents` and `GoogleSearchTool` from `google.adk.tools`.
- Import `to_a2a` from `google.adk.a2a.utils.agent_to_a2a`.
- Instantiate `google_search = GoogleSearchTool()`.
- Create `root_agent = Agent(model="gemini-2.5-flash", name="search_agent_0805", description="An agent that searches and analyzes user requests using Google Search.", instruction="Search for and analyze the user's request using Google Search.", tools=[google_search])`.
- Wrap `root_agent` with A2A protocol compliance: `a2a_app = to_a2a(root_agent)`.

2. `agent_gateway/agent/deploy_agent.py`:
- Implement a 3-step deployment pipeline:
  - Step 1 (`step1_get_adk_agent`): Load `root_agent` and `a2a_app` from `agent_gateway.agent.agent`.
  - Step 2 (`step2_create_agent_engine`): Initialize Vertex AI SDK (`vertexai.init`), check for and replace any existing ReasoningEngine matching display name "Search_Agent-0805", and deploy the agent engine via `vertexai.agent_engines.create(agent_engine=adk_agent, display_name="Search_Agent-0805", description=..., requirements=["google-cloud-aiplatform[agent-engines]>=1.70.0", "cloudpickle>=3.0.0", "google-adk[agent-identity,a2a]>=1.31.0", "google-genai>=1.0.0", "httpx>=0.20.0"])`.
  - Step 3 (`step3_register_in_agent_registry`): Register/patch the A2A Agent Card in GCP Agent Registry (`https://agentregistry.googleapis.com/v1/projects/{PROJECT_ID}/locations/global/services`) with `type: "A2A_AGENT_CARD"`, `protocolVersion: "0.3.0"`, and `url: f"https://{LOCATION}-aiplatform.googleapis.com/v1/{resource_name}"` to synchronize the Target URL with the active Reasoning Engine.
- Call step1, step2, step3 sequentially in `main()`.

3. `agent_gateway/agent/deploy.sh`:
- Create an executable bash script setting `PROJECT_ID="ai-hangsik"`, `LOCATION="us-central1"`, `STAGING_BUCKET="gs://ai-hangsik-adk-staging"`, `DISPLAY_NAME="Search_Agent-0805"`.
- Run `gcloud config set project "$PROJECT_ID"`.
- Execute `python3 deploy_agent.py`.

4. `agent_gateway/agent/call_agent_directly.py`:
- Create a script that initializes Vertex AI SDK (`vertexai.init`), finds the active ReasoningEngine named "Search_Agent-0805" via `vertexai.agent_engines.list()`, creates a session (`create_session`), calls `stream_query`, and prints the final grounded text and search citations.

5. `agent_gateway/agent/call_agent_registry.py`:
- Create a script that uses ADK `AgentRegistry` SDK (`from google.adk.integrations.agent_registry.agent_registry import AgentRegistry`).
- Monkeypatch `AgentRegistry._clean_name` to handle hyphenated names: `AgentRegistry._clean_name = lambda self, name_str: re.sub(r"[^\w]", "_", name_str).strip("_") or "resolved_gcp_agent"`.
- Initialize `registry = AgentRegistry(project_id="ai-hangsik", location="global")`.
- Call `registry.list_agents()`, find "Search_Agent-0805", call `registry.get_agent_info()`, extract the Target URL, connect to Vertex AI Agent Engine (`vertexai.agent_engines.get`), create a session, stream query results, and print search citations.

6. `agent_gateway/agent/README.md`:
- Document the architecture, 3-step deployment pipeline, file roles, and how to execute deployment and caller scripts.

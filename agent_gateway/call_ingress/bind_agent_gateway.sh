#!/bin/bash
# ==============================================================================
# 🌐 Attach Agent Gateway to Vertex AI Reasoning Engine (Ingress)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PROJECT_ID="${PROJECT_ID:-ai-hangsik}"
REGION="${REGION:-us-central1}"
AGENT_GATEWAY_NAME="${AGENT_GATEWAY_NAME:-search-ag-0805}"
RESOURCE_ID="${1:-$RESOURCE_ID}"

# If RESOURCE_ID is not provided as an argument, look up active Reasoning Engine ID via Python SDK
if [ -z "$RESOURCE_ID" ]; then
    echo "🔍 RESOURCE_ID가 지정되지 않아 active Agent Engine 탐색 중..."
    RESOURCE_ID=$("$PROJECT_ROOT/.venv/bin/python3" -c "
import vertexai
from vertexai import agent_engines
vertexai.init(project='$PROJECT_ID', location='$REGION')
engines = list(agent_engines.list())
if engines:
    print(getattr(engines[0], 'resource_name', str(engines[0])).split('/')[-1])
" 2>/dev/null || true)
fi

if [ -z "$RESOURCE_ID" ]; then
    echo "❌ Error: RESOURCE_ID를 지정해야 합니다. 사용법: ./bind_agent_gateway.sh [RESOURCE_ID]"
    exit 1
fi

echo "========================================================================="
echo " 🌐 Agent Gateway 바인딩 (PATCH spec.deploymentSpec.agentGatewayConfig)"
echo "========================================================================="
echo "  Project ID         : $PROJECT_ID"
echo "  Region             : $REGION"
echo "  Resource ID        : $RESOURCE_ID"
echo "  Agent Gateway Name : $AGENT_GATEWAY_NAME"
echo "========================================================================="

TOKEN=$(PATH="/Users/hangsik/gcloud/google-cloud-sdk/bin:$PATH" gcloud auth print-access-token 2>/dev/null || gcloud auth print-access-token)

curl -X PATCH \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d "{
    \"spec\": {
      \"deploymentSpec\": {
        \"agentGatewayConfig\": {
          \"clientToAgentConfig\": {
            \"agentGateway\": \"projects/${PROJECT_ID}/locations/${REGION}/agentGateways/${AGENT_GATEWAY_NAME}\"
          }
        }
      }
    }
  }" \
  "https://${REGION}-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_ID}/locations/${REGION}/reasoningEngines/${RESOURCE_ID}?updateMask=spec.deploymentSpec.agentGatewayConfig"

echo ""
echo "✅ Agent Gateway 바인딩 요청 완료!"

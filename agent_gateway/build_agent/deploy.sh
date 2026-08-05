#!/bin/bash
# ==============================================================================
# 🚀 GCP ADK Agent -> Agent Engine -> Agent Registry 배포 실행 스크립트
# ==============================================================================
set -e

# 스크립트가 위치한 디렉토리 및 프로젝트 루트 디렉토리 절대경로 파악
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 환경 변수 기본값 설정
export PATH="/Users/hangsik/gcloud/google-cloud-sdk/bin:$PATH"
export CLOUDSDK_PYTHON="${CLOUDSDK_PYTHON:-/Library/Frameworks/Python.framework/Versions/3.12/bin/python3}"
export PROJECT_ID="${PROJECT_ID:-ai-hangsik}"
export LOCATION="${LOCATION:-us-central1}"
export STAGING_BUCKET="${STAGING_BUCKET:-gs://ai-hangsik-adk-staging}"
export DISPLAY_NAME="${DISPLAY_NAME:-Search_Agent-0805}"
export DESCRIPTION="${DESCRIPTION:-ADK agent that searches and analyzes user requests using Google Search.}"

echo "========================================================================="
echo " 🚀 ADK 에이전트 배포 파이프라인 (Agent Gateway)"
echo "========================================================================="
echo "  구글 클라우드 프로젝트 (Project ID) : $PROJECT_ID"
echo "  대상 리전 (Location)               : $LOCATION"
echo "  스테이징 버킷 (Staging Bucket)     : $STAGING_BUCKET"
echo "  에이전트 표시 이름 (Display Name)   : $DISPLAY_NAME"
echo "========================================================================="

# 1. GCP CLI 바인딩 프로젝트 확인
echo ""
echo "1. GCP 프로젝트 설정 활성화..."
gcloud config set project "$PROJECT_ID"

# 2. Python 배포 파이프라인 스크립트 실행 ($SCRIPT_DIR/deploy_agent.py)
echo ""
echo "2. deploy_agent.py 실행 중..."
cd "$PROJECT_ROOT"
if command -v uv >/dev/null 2>&1; then
    uv run python3 "$SCRIPT_DIR/deploy_agent.py"
elif [ -f "$PROJECT_ROOT/.venv/bin/python3" ]; then
    "$PROJECT_ROOT/.venv/bin/python3" "$SCRIPT_DIR/deploy_agent.py"
else
    python3 "$SCRIPT_DIR/deploy_agent.py"
fi

echo ""
echo "========================================================================="
echo " 🎉 모든 단계가 성공적으로 실행 완료되었습니다!"
echo "========================================================================="

#!/usr/bin/env bash
# =============================================================================
# J2LAB Platform - EC2 CLI deploy via AWS SSM
# =============================================================================
# Usage:
#   AWS_REGION=ap-northeast-2 EC2_INSTANCE_ID=i-xxxx ./scripts/deploy-ec2-cli.sh
#   AWS_REGION=ap-northeast-2 EC2_INSTANCE_ID=i-xxxx ./scripts/deploy-ec2-cli.sh status
#   AWS_REGION=ap-northeast-2 EC2_INSTANCE_ID=i-xxxx ./scripts/deploy-ec2-cli.sh logs
#
# Optional env:
#   AWS_PROFILE=my-profile
#   DEPLOY_PATH=/home/ubuntu/j2lab-platform
#   BRANCH=main
#   COMMIT_SHA=<git sha>
#   RUN_SEED=false
#   RUN_BACKUP=true
#   BUILD_SERVICES="api-server frontend keyword-worker campaign-worker"
#   LOG_TAIL=200
# =============================================================================

set -euo pipefail

ACTION="${1:-deploy}"
AWS_REGION="${AWS_REGION:?AWS_REGION is required}"
EC2_INSTANCE_ID="${EC2_INSTANCE_ID:?EC2_INSTANCE_ID is required}"
DEPLOY_PATH="${DEPLOY_PATH:-/home/ubuntu/j2lab-platform}"
BRANCH="${BRANCH:-main}"
COMMIT_SHA="${COMMIT_SHA:-}"
RUN_SEED="${RUN_SEED:-false}"
RUN_BACKUP="${RUN_BACKUP:-true}"
BUILD_SERVICES="${BUILD_SERVICES:-}"
LOG_TAIL="${LOG_TAIL:-200}"

AWS_ARGS=(--region "$AWS_REGION")
if [[ -n "${AWS_PROFILE:-}" ]]; then
    AWS_ARGS+=(--profile "$AWS_PROFILE")
fi

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Missing required command: %s\n' "$1" >&2
        exit 1
    fi
}

require_cmd aws
require_cmd python3

run_ssm_commands() {
    local comment="$1"
    shift

    local params_file
    params_file="$(mktemp)"

    python3 - "$params_file" "$@" <<'PY'
import json
import sys

path = sys.argv[1]
commands = sys.argv[2:]
with open(path, "w", encoding="utf-8") as fp:
    json.dump({"commands": commands}, fp)
PY

    local command_id
    command_id="$(aws "${AWS_ARGS[@]}" ssm send-command \
        --instance-ids "$EC2_INSTANCE_ID" \
        --document-name "AWS-RunShellScript" \
        --comment "$comment" \
        --parameters "file://$params_file" \
        --query 'Command.CommandId' \
        --output text)"

    rm -f "$params_file"

    printf 'SSM command started: %s\n' "$command_id"
    set +e
    aws "${AWS_ARGS[@]}" ssm wait command-executed \
        --command-id "$command_id" \
        --instance-id "$EC2_INSTANCE_ID"
    set -e

    local status
    status="$(aws "${AWS_ARGS[@]}" ssm get-command-invocation \
        --command-id "$command_id" \
        --instance-id "$EC2_INSTANCE_ID" \
        --query 'Status' \
        --output text)"

    printf '\n[stdout]\n'
    aws "${AWS_ARGS[@]}" ssm get-command-invocation \
        --command-id "$command_id" \
        --instance-id "$EC2_INSTANCE_ID" \
        --query 'StandardOutputContent' \
        --output text || true

    printf '\n[stderr]\n'
    aws "${AWS_ARGS[@]}" ssm get-command-invocation \
        --command-id "$command_id" \
        --instance-id "$EC2_INSTANCE_ID" \
        --query 'StandardErrorContent' \
        --output text || true

    if [[ "$status" != "Success" ]]; then
        printf '\nSSM command failed with status: %s\n' "$status" >&2
        exit 1
    fi
}

deploy_commands=(
    "set -euo pipefail"
    "cd '$DEPLOY_PATH'"
    "test -d .git"
    "test -f .env"
    "for key in DB_PASSWORD SECRET_KEY INTERNAL_API_SECRET; do grep -Eq \"^\\${key}=.+\" .env || { echo \"Missing \\${key} in .env\"; exit 1; }; done"
    "git fetch --all --tags"
)

if [[ -n "$COMMIT_SHA" ]]; then
    deploy_commands+=(
        "git checkout '$COMMIT_SHA'"
        "git rev-parse --short HEAD"
    )
else
    deploy_commands+=(
        "git checkout '$BRANCH'"
        "git pull --ff-only origin '$BRANCH'"
        "git rev-parse --short HEAD"
    )
fi

if [[ "$RUN_BACKUP" == "true" ]]; then
    deploy_commands+=("bash ./scripts/backup-db.sh")
fi

if [[ -n "$BUILD_SERVICES" ]]; then
    deploy_commands+=("docker compose build $BUILD_SERVICES")
else
    deploy_commands+=("docker compose build")
fi

deploy_commands+=(
    "docker compose up -d db"
    "for i in \\$(seq 1 30); do docker compose exec -T db true >/dev/null 2>&1 && break; sleep 2; done"
    "docker compose run --rm api-server alembic upgrade head"
    "docker compose up -d --remove-orphans"
)

if [[ "$RUN_SEED" == "true" ]]; then
    deploy_commands+=("bash ./scripts/seed-data.sh")
fi

deploy_commands+=(
    "docker compose ps"
    "grep -Eq '^DRY_RUN=false' .env || echo 'WARN: DRY_RUN is not false in .env'"
    "curl -fsS http://localhost/health"
)

status_commands=(
    "set -euo pipefail"
    "cd '$DEPLOY_PATH'"
    "docker compose ps"
    "curl -fsS http://localhost/health"
)

log_commands=(
    "set -euo pipefail"
    "cd '$DEPLOY_PATH'"
    "docker compose logs --tail=$LOG_TAIL"
)

case "$ACTION" in
    deploy)
        run_ssm_commands "j2lab deploy" "${deploy_commands[@]}"
        ;;
    status)
        run_ssm_commands "j2lab status" "${status_commands[@]}"
        ;;
    logs)
        run_ssm_commands "j2lab logs" "${log_commands[@]}"
        ;;
    *)
        printf 'Usage: %s {deploy|status|logs}\n' "$0" >&2
        exit 1
        ;;
esac

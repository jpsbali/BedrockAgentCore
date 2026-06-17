#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_DIR="$REPO_ROOT/.claude/skills"

usage() {
    echo "Usage: $0 <module_number|all>"
    echo ""
    echo "Runs skill setup scripts to copy scaffold code into the working directory."
    echo ""
    echo "  $0 1       # Module 1: Consolidation Agent"
    echo "  $0 2       # Module 2: MCP Server"
    echo "  $0 3       # Module 3: Research Agents"
    echo "  $0 4       # Module 4: Terraform Deploy"
    echo "  $0 5       # Module 5: CLI"
    echo "  $0 7       # Module 7: Cleanup (terraform destroy)"
    echo "  $0 all     # Modules 1-5"
    exit 1
}

generate_env() {
    cd "$REPO_ROOT/terraform" && terraform output -json | jq -r 'to_entries[] | "\(.key | ascii_upcase)=\(.value.value)"' > "$REPO_ROOT/.env" && cd "$REPO_ROOT"
    echo "✓ Terraform outputs saved to .env"
}

run_module() {
    local n=$1
    case $n in
        1) echo "=== Module 1: Consolidation Agent ===" && bash "$SKILLS_DIR/module-1-consolidation-agent/scripts/setup.sh" ;;
        2) echo "=== Module 2: MCP Server ===" && bash "$SKILLS_DIR/module-2-mcp-server/scripts/setup.sh" ;;
        3) echo "=== Module 3: Research Agents ===" && bash "$SKILLS_DIR/module-3-research-agents/scripts/setup.sh" ;;
        4) echo "=== Module 4: Terraform Deploy ===" && bash "$SKILLS_DIR/module-4-deploy/scripts/setup.sh" ;;
        5) echo "=== Module 5: CLI ===" && bash "$SKILLS_DIR/module-5-cli/scripts/setup.sh" ;;
        7) echo "=== Module 7: Cleanup ===" && bash "$SKILLS_DIR/module-7-cleanup/scripts/cleanup.sh" ;;
        *) echo "Error: Invalid module number: $n (valid: 1-5, 7)" && exit 1 ;;
    esac
}

[ $# -eq 0 ] && usage

if [ "$1" = "all" ]; then
    for n in 1 2 3 4; do
        run_module $n
        echo ""
    done
    generate_env
    echo ""
    run_module 5
    echo ""
    echo "✓ All modules (1-5) set up."
else
    if [ "$1" = "5" ]; then
        generate_env
    fi
    run_module "$1"
fi

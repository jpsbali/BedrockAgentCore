#!/usr/bin/env bash
set -euo pipefail

echo "=== Workshop Environment Setup ==="

# --- Install uv ---
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "uv already installed: $(uv --version)"
fi

# --- Install Terraform ---
if ! command -v terraform &>/dev/null; then
    echo "Installing Terraform..."
    TERRAFORM_VERSION="1.11.4"
    curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" -o /tmp/terraform.zip
    sudo unzip -o /tmp/terraform.zip -d /usr/local/bin/
    rm /tmp/terraform.zip
    echo "Terraform installed: $(terraform version -json | python3 -c 'import sys,json;print(json.load(sys.stdin)["terraform_version"])')"
else
    echo "Terraform already installed: $(terraform version -json | python3 -c 'import sys,json;print(json.load(sys.stdin)["terraform_version"])')"
fi

# --- VS Code settings ---
VSCODE_DIRS=(
    "$HOME/sagemaker-code-editor-server-data/data/User"
    "$HOME/.vscode-server/data/Machine"
    "$HOME/.config/Code/User"
)

SETTINGS_CONTENT='{
    "workbench.notifications.doNotDisturbMode": true,
    "workbench.editorAssociations": {
        "*.md": "vscode.markdown.preview.editor"
    },
    "workbench.editor.enablePreview": false,
    "remote.autoForwardPorts": false
}'

SETTINGS_WRITTEN=false
for dir in "${VSCODE_DIRS[@]}"; do
    if [ -d "$(dirname "$dir")" ]; then
        mkdir -p "$dir"
        SETTINGS_FILE="$dir/settings.json"
        if [ -f "$SETTINGS_FILE" ]; then
            python3 -c "
import json, re, sys
with open('$SETTINGS_FILE') as f:
    raw = f.read()
# Strip single-line comments and trailing commas (JSONC -> JSON)
raw = re.sub(r'//[^\n]*', '', raw)
raw = re.sub(r',\s*([}\]])', r'\1', raw)
settings = json.loads(raw)
settings['workbench.notifications.doNotDisturbMode'] = True
settings.setdefault('workbench.editorAssociations', {})['*.md'] = 'vscode.markdown.preview.editor'
settings['workbench.editor.enablePreview'] = False
with open('$SETTINGS_FILE', 'w') as f:
    json.dump(settings, f, indent=4)
"
        else
            echo "$SETTINGS_CONTENT" > "$SETTINGS_FILE"
        fi
        echo "VS Code settings written to $SETTINGS_FILE"
        SETTINGS_WRITTEN=true
    fi
done

if [ "$SETTINGS_WRITTEN" = false ]; then
    mkdir -p "$HOME/sagemaker-code-editor-server-data/data/User"
    echo "$SETTINGS_CONTENT" > "$HOME/sagemaker-code-editor-server-data/data/User/settings.json"
    echo "VS Code settings written to $HOME/sagemaker-code-editor-server-data/data/User/settings.json"
fi

# --- VS Code extensions ---
EXTENSIONS_DIR="/home/sagemaker-user/sagemaker-code-editor-server-data/extensions/"

echo "Removing Amazon Q extension..."
sagemaker-code-editor --uninstall-extension amazonwebservices.amazon-q-vscode --extensions-dir "$EXTENSIONS_DIR" 2>/dev/null || true

echo "Removing AWS Toolkit extension..."
sagemaker-code-editor --uninstall-extension amazonwebservices.aws-toolkit-vscode --extensions-dir "$EXTENSIONS_DIR" 2>/dev/null || true

# Install extensions directly into the extensions directory
echo "Installing Mermaid preview extension..."
sagemaker-code-editor --install-extension bierner.markdown-mermaid --extensions-dir "$EXTENSIONS_DIR" 2>/dev/null || true

echo "Installing PDF viewer extension..."
sagemaker-code-editor --install-extension anwar.papyrus-pdf --extensions-dir "$EXTENSIONS_DIR" 2>/dev/null || true

echo "Installing Terraform extension..."
sagemaker-code-editor --install-extension hashicorp.terraform --extensions-dir "$EXTENSIONS_DIR" 2>/dev/null || true

echo "=== Setup Complete ==="
echo "  uv:        $(uv --version 2>/dev/null || echo 'not found')"
echo "  terraform: $(terraform version -json 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin)["terraform_version"])' 2>/dev/null || echo 'not found')"


# --- Install Claude Code ---
echo "Installing Claude Code..."
curl -fsSL https://claude.ai/install.sh | bash

# --- Add PATH to .bashrc ---
if ! grep -q '$HOME/.local/bin' "$HOME/.bashrc" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    echo "Added PATH to .bashrc"
fi

# --- Claude Code environment variables ---
CLAUDE_VARS=(
    'export CLAUDE_CODE_USE_BEDROCK=1'
    'export ANTHROPIC_DEFAULT_SONNET_MODEL=global.anthropic.claude-sonnet-4-6'
    'export ANTHROPIC_DEFAULT_HAIKU_MODEL=global.anthropic.claude-haiku-4-5-20251001-v1:0'
    'export ANTHROPIC_DEFAULT_OPUS_MODEL=global.anthropic.claude-opus-4-6-v1'
    'export CLAUDE_CODE_EFFORT_LEVEL=medium'
)

for var in "${CLAUDE_VARS[@]}"; do
    key=$(echo "$var" | sed 's/export \([^=]*\)=.*/\1/')
    if ! grep -q "^export $key=" "$HOME/.bashrc" 2>/dev/null; then
        echo "$var" >> "$HOME/.bashrc"
    fi
done
echo "Claude Code environment variables written to .bashrc"


# --- Configure Claude Code settings ---
cat > /home/sagemaker-user/.claude.json << 'EOF'
{
   "numStartups":0,
   "installMethod":"native",
   "autoUpdates":false,
   "tipsHistory":{
      "new-user-warmup":1,
      "plan-mode-for-complex-tasks":1,
      "terminal-setup":2,
      "shift-enter-setup":2
   },
   "firstStartTime":"2026-05-11T18:20:08.445Z",
   "opusProMigrationComplete":true,
   "sonnet1m45MigrationComplete":true,
   "seenNotifications":{

   },
   "migrationVersion":13,
   "changelogLastFetched":1778523608651,
   "autoUpdatesProtectedForNative":true,
   "hasCompletedOnboarding":true,
   "lastOnboardingVersion":"2.1.138",
   "lastReleaseNotesSeen":"2.1.138",
   "officialMarketplaceAutoInstallAttempted":true,
   "officialMarketplaceAutoInstalled":true,
   "hasIdeOnboardingBeenShown":{
      "vscode":true
   },
   "mcpServers":{
      "bedrock-agentcore-mcp-server":{
         "command":"uvx",
         "args":[
            "awslabs.amazon-bedrock-agentcore-mcp-server@latest"
         ],
         "env":{
            "FASTMCP_LOG_LEVEL":"ERROR",
            "AGENTCORE_ENABLE_TOOLS":"search_agentcore_docs,fetch_agentcore_doc"
         },
         "disabled":false,
         "autoApprove":[

         ]
      },
      "strands-agents":{
         "command":"uvx",
         "args":[
            "strands-agents-mcp-server"
         ],
         "env":{
            "FASTMCP_LOG_LEVEL":"INFO"
         },
         "disabled":false,
         "autoApprove":[
            "search_docs",
            "fetch_doc"
         ]
      },
      "awslabs.aws-documentation-mcp-server":{
         "command":"uvx",
         "args":[
            "awslabs.aws-documentation-mcp-server@latest"
         ],
         "env":{
            "FASTMCP_LOG_LEVEL":"ERROR",
            "AWS_DOCUMENTATION_PARTITION":"aws",
            "MCP_USER_AGENT":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
         },
         "disabled":false,
         "autoApprove":[

         ]
      }
   }
}
EOF
echo "Claude Code .claude.json written"

# --- Configure oh-my-pi agent ---
mkdir -p /home/sagemaker-user/.omp/agent

cat > /home/sagemaker-user/.omp/agent/config.yml << 'EOF'
modelRoles:
  default: amazon-bedrock/global.anthropic.claude-sonnet-4-6
  smol: amazon-bedrock/eu.anthropic.claude-haiku-4-5-20251001-v1:0
EOF
echo "oh-my-pi config.yml written"

cat > /home/sagemaker-user/.omp/agent/mcp.json << 'EOF'
{
    "$schema": "https://raw.githubusercontent.com/can1357/oh-my-pi/main/packages/coding-agent/src/config/mcp-schema.json",
    "mcpServers": {
        "bedrock-agentcore-mcp-server": {
            "command": "uvx",
            "args": ["awslabs.amazon-bedrock-agentcore-mcp-server@latest"],
            "env": {
                "FASTMCP_LOG_LEVEL": "ERROR",
                "AGENTCORE_ENABLE_TOOLS": "search_agentcore_docs,fetch_agentcore_doc"
            },
            "disabled": false,
            "autoApprove": []
        },
        "strands-agents": {
            "command": "uvx",
            "args": ["strands-agents-mcp-server"],
            "env": {
                "FASTMCP_LOG_LEVEL": "INFO"
            },
            "disabled": false,
            "autoApprove": ["search_docs", "fetch_doc"]
        }
    }
}
EOF
echo "oh-my-pi mcp.json written"

# --- Git config ---
git config --global user.email "workshop@workshop.com"
git config --global user.name "Workshop User"


# --- Remove global skills ---
rm -rf /home/sagemaker-user/.claude/skills || true

# --- Default working directory ---
if ! grep -q 'cd /home/sagemaker-user/workshop' "$HOME/.bashrc" 2>/dev/null; then
    echo 'cd /home/sagemaker-user/workshop' >> "$HOME/.bashrc"
fi

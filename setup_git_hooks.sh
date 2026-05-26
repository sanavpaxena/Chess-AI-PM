#!/bin/bash

HOOK_DIR=".git/hooks"
PRE_COMMIT_FILE="$HOOK_DIR/pre-commit"

if [ ! -d "$HOOK_DIR" ]; then
    echo "Error: Not a git repository (or .git/hooks doesn't exist). Please run 'git init' first."
    exit 1
fi

cat << 'EOF' > "$PRE_COMMIT_FILE"
#!/bin/bash

echo "⏳ Running pre-commit tests..."

# Run the test script
./run_tests.sh

# Capture exit code
if [ $? -ne 0 ]; then
    echo "🚫 Tests failed! Commit rejected."
    echo "Fix the failing tests and try again, or use 'git commit --no-verify' to bypass."
    exit 1
fi

echo "✅ Tests passed! Proceeding with commit."
EOF

chmod +x "$PRE_COMMIT_FILE"
echo "✅ pre-commit hook installed successfully at $PRE_COMMIT_FILE!"

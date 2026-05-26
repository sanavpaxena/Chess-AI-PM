#!/bin/bash

# Ensure PYTHONPATH is set so modules can be imported
export PYTHONPATH="$(pwd)"

echo "♟ Running Grandmaster.AI Test Suite..."
echo "======================================"

# Run pytest with coverage reporting
pytest tests/ -v --cov=app --cov-report=term-missing

TEST_RESULT=$?

if [ $TEST_RESULT -eq 0 ]; then
    echo "======================================"
    echo "✅ All tests passed!"
else
    echo "======================================"
    echo "❌ Some tests failed. Please fix before committing."
fi

exit $TEST_RESULT

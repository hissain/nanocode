#!/bin/bash

# Test script for Gemini support
# Usage: ./test_gemini.sh

echo "Testing Gemini support..."
echo ""

if [ -z "$GEMINI_API_KEY" ]; then
    echo "❌ GEMINI_API_KEY not set"
    echo "Please set it with: export GEMINI_API_KEY='your-key'"
    exit 1
fi

echo "✓ GEMINI_API_KEY is set"
echo ""
echo "Starting nanocode with Gemini..."
echo "Try asking: 'list files in this directory'"
echo ""

python3.11 nanocode.py

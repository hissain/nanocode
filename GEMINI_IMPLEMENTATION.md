# Gemini Support Implementation Summary

## What was added

### 1. **Provider Detection System**
- Automatically detects which API to use based on environment variables
- Priority: `GEMINI_API_KEY` > `OPENROUTER_API_KEY` > `ANTHROPIC_API_KEY`
- Sets appropriate API URL and default model based on provider

### 2. **Gemini API Integration**
- Added support for Google Gemini API (v1beta)
- Default model: `gemini-2.0-flash-exp`
- API endpoint: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`

### 3. **Format Conversion Functions**

#### `convert_messages_to_gemini(messages, system_prompt)`
Converts Anthropic's message format to Gemini's format:
- Maps `user` → `user`, `assistant` → `model` roles
- Converts text content to Gemini's `parts` structure
- Transforms `tool_use` to `functionCall`
- Transforms `tool_result` to `functionResponse`

#### `convert_gemini_response(gemini_response)`
Converts Gemini's response back to Anthropic format:
- Extracts text from `candidates[0].content.parts`
- Converts `functionCall` back to `tool_use`
- Maintains compatibility with existing tool execution flow

### 4. **Schema Generation Updates**
Enhanced `make_schema()` to generate provider-specific schemas:
- **Gemini format**: Uses `OBJECT`, `STRING`, `NUMBER`, `BOOLEAN` types
- **Anthropic format**: Uses `object`, `string`, `number`, `integer`, `boolean` types
- Gemini uses `functionDeclarations` with `parameters`
- Anthropic uses `input_schema`

### 5. **Updated call_api() Function**
Now routes to appropriate API based on `PROVIDER`:
- Gemini: Uses conversion functions + Gemini API format
- Anthropic/OpenRouter: Uses existing format (unchanged)

## Usage

### Basic Usage
```bash
export GEMINI_API_KEY="your-gemini-api-key"
python nanocode.py
```

### Using Different Gemini Models
```bash
export GEMINI_API_KEY="your-key"
export MODEL="gemini-2.0-flash-thinking-exp"
python nanocode.py
```

### Available Gemini Models
- `gemini-2.0-flash-exp` (default)
- `gemini-2.0-flash-thinking-exp`
- `gemini-pro`
- `gemini-pro-vision`

## Key Features Maintained

✅ **Zero new dependencies** - Only uses Python stdlib
✅ **Tool/function calling** - Full support for all 6 tools (read, write, edit, glob, grep, bash)
✅ **Agentic loop** - Multi-turn tool execution works seamlessly
✅ **Conversation history** - Maintains context across turns
✅ **Minimal philosophy** - ~120 lines added for full Gemini support

## Technical Details

### Message Flow
1. User input → Anthropic format (internal)
2. If Gemini: Convert to Gemini format → Call Gemini API
3. Gemini response → Convert back to Anthropic format
4. Process tools using existing tool execution logic
5. Continue agentic loop as normal

### Tool Execution
- Tools are executed using the same `run_tool()` function
- Results are formatted back into provider-specific format
- No changes needed to individual tool implementations

## Testing

To test Gemini support:
```bash
./test_gemini.sh
```

Or manually:
```bash
export GEMINI_API_KEY="your-key"
python3.11 nanocode.py
```

Then try commands like:
- "list files in this directory"
- "read the README file"
- "create a hello.py file that prints hello world"

## Files Modified
- `nanocode.py` - Main implementation (+171 lines, -29 lines)
- `README.md` - Usage documentation
- `test_gemini.sh` - Test script (new)

## Compatibility
- Works alongside existing Anthropic and OpenRouter support
- Maintains backward compatibility
- No breaking changes to existing functionality

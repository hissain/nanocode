#!/usr/bin/env python3
"""nanocode - minimal claude code alternative"""

import glob as globlib, json, os, platform, re, shutil, subprocess, sys, urllib.request

# API configuration
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Determine provider and setup
if GEMINI_KEY:
    PROVIDER = "gemini"
    MODEL = os.environ.get("MODEL", "gemini-2.0-flash-exp")
    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
elif OPENROUTER_KEY:
    PROVIDER = "openrouter"
    MODEL = os.environ.get("MODEL", "anthropic/claude-opus-4.5")
    API_URL = "https://openrouter.ai/api/v1/messages"
else:
    PROVIDER = "anthropic"
    MODEL = os.environ.get("MODEL", "claude-opus-4-5")
    API_URL = "https://api.anthropic.com/v1/messages"

# ANSI colors
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
BLUE, CYAN, GREEN, YELLOW, RED = (
    "\033[34m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
)


# --- System information ---


def get_system_info():
    """Gather system information to help LLM provide contextually appropriate responses."""
    info_parts = []
    
    # Operating system
    os_name = platform.system()
    info_parts.append(f"OS: {os_name}")
    
    # Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    info_parts.append(f"Python: {py_version}")
    
    # Shell
    shell = os.environ.get("SHELL", os.environ.get("COMSPEC", "unknown"))
    shell_name = os.path.basename(shell) if shell != "unknown" else "unknown"
    info_parts.append(f"Shell: {shell_name}")
    
    # Current working directory
    info_parts.append(f"CWD: {os.getcwd()}")
    
    # Check for common development tools
    tools = ["git", "npm", "node", "pip", "docker", "make"]
    available = [t for t in tools if shutil.which(t)]
    if available:
        info_parts.append(f"Tools: {', '.join(available)}")
    
    return " | ".join(info_parts)


# --- Tool implementations ---


def read(args):
    lines = open(args["path"]).readlines()
    offset = args.get("offset", 0)
    limit = args.get("limit", len(lines))
    selected = lines[offset : offset + limit]
    return "".join(f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected))


def write(args):
    with open(args["path"], "w") as f:
        f.write(args["content"])
    return "ok"


def edit(args):
    text = open(args["path"]).read()
    old, new = args["old"], args["new"]
    if old not in text:
        return "error: old_string not found"
    count = text.count(old)
    if not args.get("all") and count > 1:
        return f"error: old_string appears {count} times, must be unique (use all=true)"
    replacement = (
        text.replace(old, new) if args.get("all") else text.replace(old, new, 1)
    )
    with open(args["path"], "w") as f:
        f.write(replacement)
    return "ok"


def glob(args):
    pattern = (args.get("path", ".") + "/" + args["pat"]).replace("//", "/")
    files = globlib.glob(pattern, recursive=True)
    files = sorted(
        files,
        key=lambda f: os.path.getmtime(f) if os.path.isfile(f) else 0,
        reverse=True,
    )
    return "\n".join(files) or "none"


def grep(args):
    pattern = re.compile(args["pat"])
    hits = []
    for filepath in globlib.glob(args.get("path", ".") + "/**", recursive=True):
        try:
            for line_num, line in enumerate(open(filepath), 1):
                if pattern.search(line):
                    hits.append(f"{filepath}:{line_num}:{line.rstrip()}")
        except Exception:
            pass
    return "\n".join(hits[:50]) or "none"


def bash(args):
    proc = subprocess.Popen(
        args["cmd"], shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True
    )
    output_lines = []
    try:
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                print(f"  {DIM}│ {line.rstrip()}{RESET}", flush=True)
                output_lines.append(line)
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        output_lines.append("\n(timed out after 30s)")
    return "".join(output_lines).strip() or "(empty)"


# --- Tool definitions: (description, schema, function) ---

TOOLS = {
    "read": (
        "Read file with line numbers (file path, not directory)",
        {"path": "string", "offset": "number?", "limit": "number?"},
        read,
    ),
    "write": (
        "Write content to file",
        {"path": "string", "content": "string"},
        write,
    ),
    "edit": (
        "Replace old with new in file (old must be unique unless all=true)",
        {"path": "string", "old": "string", "new": "string", "all": "boolean?"},
        edit,
    ),
    "glob": (
        "Find files by pattern, sorted by mtime",
        {"pat": "string", "path": "string?"},
        glob,
    ),
    "grep": (
        "Search files for regex pattern",
        {"pat": "string", "path": "string?"},
        grep,
    ),
    "bash": (
        "Run shell command",
        {"cmd": "string"},
        bash,
    ),
}


def run_tool(name, args):
    try:
        return TOOLS[name][2](args)
    except Exception as err:
        return f"error: {err}"


def make_schema():
    """Generate tool schema in provider-specific format."""
    result = []
    for name, (description, params, _fn) in TOOLS.items():
        properties = {}
        required = []
        for param_name, param_type in params.items():
            is_optional = param_type.endswith("?")
            base_type = param_type.rstrip("?")
            prop_def = {"type": "integer" if base_type == "number" else base_type}
            
            # Gemini requires type in uppercase for some types
            if PROVIDER == "gemini" and base_type == "string":
                prop_def["type"] = "STRING"
            elif PROVIDER == "gemini" and base_type == "number":
                prop_def["type"] = "NUMBER"
            elif PROVIDER == "gemini" and base_type == "boolean":
                prop_def["type"] = "BOOLEAN"
                
            properties[param_name] = prop_def
            if not is_optional:
                required.append(param_name)
        
        if PROVIDER == "gemini":
            # Gemini format
            result.append({
                "name": name,
                "description": description,
                "parameters": {
                    "type": "OBJECT",
                    "properties": properties,
                    "required": required,
                }
            })
        else:
            # Anthropic/OpenRouter format
            result.append({
                "name": name,
                "description": description,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })
    return result


def convert_messages_to_gemini(messages, system_prompt):
    """Convert Anthropic message format to Gemini format."""
    contents = []
    
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        
        if isinstance(msg["content"], str):
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        elif isinstance(msg["content"], list):
            parts = []
            for item in msg["content"]:
                if item["type"] == "text":
                    parts.append({"text": item["text"]})
                elif item["type"] == "tool_use":
                    parts.append({
                        "functionCall": {
                            "name": item["name"],
                            "args": item["input"]
                        }
                    })
                elif item["type"] == "tool_result":
                    parts.append({
                        "functionResponse": {
                            "name": "tool_result",
                            "response": {"result": item["content"]}
                        }
                    })
            if parts:
                contents.append({"role": role, "parts": parts})
    
    return contents


def convert_gemini_response(gemini_response):
    """Convert Gemini response format to Anthropic format."""
    content_blocks = []
    
    if "candidates" not in gemini_response or not gemini_response["candidates"]:
        return {"content": [{"type": "text", "text": "No response from Gemini."}]}
    
    candidate = gemini_response["candidates"][0]
    if "content" not in candidate:
        return {"content": [{"type": "text", "text": "Empty response from Gemini."}]}
    
    parts = candidate["content"].get("parts", [])
    
    for part in parts:
        if "text" in part:
            content_blocks.append({"type": "text", "text": part["text"]})
        elif "functionCall" in part:
            fc = part["functionCall"]
            content_blocks.append({
                "type": "tool_use",
                "id": fc.get("name", "unknown") + "_call",
                "name": fc["name"],
                "input": fc.get("args", {})
            })
    
    return {"content": content_blocks}


def call_api(messages, system_prompt):
    """Call the appropriate API based on provider."""
    if PROVIDER == "gemini":
        # Gemini API format
        contents = convert_messages_to_gemini(messages, system_prompt)
        
        payload = {
            "contents": contents,
            "tools": [{"functionDeclarations": make_schema()}],
            "systemInstruction": {"parts": [{"text": system_prompt}]}
        }
        
        url = f"{API_URL}?key={GEMINI_KEY}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        response = urllib.request.urlopen(request)
        gemini_response = json.loads(response.read())
        return convert_gemini_response(gemini_response)
    else:
        # Anthropic/OpenRouter API format
        request = urllib.request.Request(
            API_URL,
            data=json.dumps(
                {
                    "model": MODEL,
                    "max_tokens": 8192,
                    "system": system_prompt,
                    "messages": messages,
                    "tools": make_schema(),
                }
            ).encode(),
            headers={
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
                **({"Authorization": f"Bearer {OPENROUTER_KEY}"} if OPENROUTER_KEY else {"x-api-key": ANTHROPIC_KEY}),
            },
        )
        response = urllib.request.urlopen(request)
        return json.loads(response.read())


def separator():
    return f"{DIM}{'─' * min(os.get_terminal_size().columns, 80)}{RESET}"


def render_markdown(text):
    return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)


def main():
    system_info = get_system_info()
    provider_name = PROVIDER.capitalize()
    print(f"{BOLD}nanocode{RESET} | {DIM}{MODEL} ({provider_name}) | {os.getcwd()}{RESET}\n")
    messages = []
    system_prompt = f"""Concise coding assistant.
{system_info}
Provide OS-appropriate commands and file paths based on the system information above."""

    while True:
        try:
            print(separator())
            user_input = input(f"{BOLD}{BLUE}❯{RESET} ").strip()
            print(separator())
            if not user_input:
                continue
            if user_input in ("/q", "exit"):
                break
            if user_input == "/c":
                messages = []
                print(f"{GREEN}⏺ Cleared conversation{RESET}")
                continue
            if user_input == "/i":
                print(f"{CYAN}⏺ System Info:{RESET}\n  {system_info}")
                continue

            messages.append({"role": "user", "content": user_input})

            # agentic loop: keep calling API until no more tool calls
            while True:
                response = call_api(messages, system_prompt)
                content_blocks = response.get("content", [])
                tool_results = []

                for block in content_blocks:
                    if block["type"] == "text":
                        print(f"\n{CYAN}⏺{RESET} {render_markdown(block['text'])}")

                    if block["type"] == "tool_use":
                        tool_name = block["name"]
                        tool_args = block["input"]
                        arg_preview = str(list(tool_args.values())[0])[:50]
                        print(
                            f"\n{GREEN}⏺ {tool_name.capitalize()}{RESET}({DIM}{arg_preview}{RESET})"
                        )

                        result = run_tool(tool_name, tool_args)
                        result_lines = result.split("\n")
                        preview = result_lines[0][:60]
                        if len(result_lines) > 1:
                            preview += f" ... +{len(result_lines) - 1} lines"
                        elif len(result_lines[0]) > 60:
                            preview += "..."
                        print(f"  {DIM}⎿  {preview}{RESET}")

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block["id"],
                                "content": result,
                            }
                        )

                messages.append({"role": "assistant", "content": content_blocks})

                if not tool_results:
                    break
                messages.append({"role": "user", "content": tool_results})

            print()

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as err:
            print(f"{RED}⏺ Error: {err}{RESET}")


if __name__ == "__main__":
    main()

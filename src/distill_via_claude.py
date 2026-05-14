"""Distill one gene by wrapping the call inside Claude Code headless (`claude --print`),
routed to z.ai's Anthropic-compatible endpoint. This stays within Z.ai's officially-supported
tooling envelope (Coding Plan TOS §4.2).

Architecture: bundle → embed system+user prompt in a single user message → `claude --print
--output-format json` with env vars routing to z.ai/api/anthropic → parse `result` from
the wrapper JSON → write bullets.json as before.

Multi-key load balancing: ZAI_API_KEYS in .env (comma-separated) round-robins per call.

Usage:
  python3 src/distill_via_claude.py FBgn0003068
"""
import json
import os
import shlex
import subprocess
import sys
import time
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict:
    out = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


ENV = load_env()
BASE_URL = ENV.get("ZAI_BASE_URL", "https://api.z.ai/api/anthropic")
MODEL = ENV.get("ZAI_MODEL", "glm-5.1")
KEYS = [k.strip() for k in ENV.get("ZAI_API_KEYS", ENV.get("ZAI_API_KEY", "")).split(",") if k.strip()]
if not KEYS:
    sys.exit("Need ZAI_API_KEY or ZAI_API_KEYS in .env")

# Round-robin key state
_lock = threading.Lock()
_key_idx = 0


def next_key() -> str:
    global _key_idx
    with _lock:
        k = KEYS[_key_idx % len(KEYS)]
        _key_idx += 1
        return k


def build_user_prompt(bundle: dict) -> str:
    """Re-use distill.py's bundle→prompt construction so output schema is identical."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("distill", ROOT / "src" / "distill.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    user_content = mod.build_input_message(bundle)
    system_prompt = (ROOT / "prompts" / "distill_system.md").read_text()
    # Claude Code headless takes ONE prompt — embed system as a preamble
    return (
        "SYSTEM INSTRUCTIONS — read first, do NOT echo back:\n"
        f"{system_prompt}\n\n"
        "================ END INSTRUCTIONS ================\n\n"
        f"{user_content}\n\n"
        "Now produce the JSON output as specified."
    )


def call_claude_headless(prompt: str, api_key: str, timeout_s: int = 600) -> dict:
    """Invoke `claude --print --output-format json`. Prompt goes on stdin to bypass
    shell command-line length limits (some gene bundles are 100k+ chars)."""
    env = dict(os.environ)
    env.update({
        "ANTHROPIC_BASE_URL": BASE_URL,
        "ANTHROPIC_AUTH_TOKEN": api_key,
        "ANTHROPIC_DEFAULT_OPUS_MODEL": MODEL,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": MODEL,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": MODEL,
        "CLAUDE_CONFIG_DIR": str(Path.home() / ".glm-fly-distill"),
    })
    # Use a deadline-aware subprocess.run with input= for stdin
    proc = subprocess.run(
        [
            "claude",
            "--print",
            "--model", MODEL,
            "--output-format", "json",
            "--permission-mode", "bypassPermissions",
        ],
        input=prompt,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr[:500]}")
    return json.loads(proc.stdout)


def strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
    return s.strip()


def distill_one(fbgn: str) -> dict:
    bundle = json.loads((ROOT / "data" / "cache" / fbgn / "bundle.json").read_text())
    prompt = build_user_prompt(bundle)
    in_chars = len(prompt)
    print(f"  input: {in_chars} chars (~{in_chars // 4} tokens)", flush=True)

    api_key = next_key()
    short = api_key[:8] + "..." + api_key[-4:]
    print(f"  using key: {short}", flush=True)

    t0 = time.time()
    wrapper = call_claude_headless(prompt, api_key)
    dt = time.time() - t0
    text = wrapper.get("result", "")
    usage = wrapper.get("usage", {})
    print(
        f"  Claude Code wrapper: {dt:.1f}s wall, "
        f"input_tokens={usage.get('input_tokens')}, "
        f"output_tokens={usage.get('output_tokens')}, "
        f"cache_read={usage.get('cache_read_input_tokens')}",
        flush=True,
    )

    out_dir = ROOT / "output" / fbgn
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "raw_response_claude.txt").write_text(text)
    (out_dir / "request_meta_claude.json").write_text(
        json.dumps(
            {
                "model": MODEL,
                "harness": "claude_code_headless",
                "elapsed_s": dt,
                "input_chars": in_chars,
                "usage": usage,
                "wrapper_meta": {
                    "duration_ms": wrapper.get("duration_ms"),
                    "duration_api_ms": wrapper.get("duration_api_ms"),
                    "num_turns": wrapper.get("num_turns"),
                    "total_cost_usd": wrapper.get("total_cost_usd"),
                },
            },
            indent=2,
        )
    )

    parsed = None
    try:
        parsed = json.loads(strip_fences(text))
    except Exception as e:
        print(f"  ! JSON parse failed: {e}", flush=True)
    if parsed:
        (out_dir / "bullets_claude.json").write_text(json.dumps(parsed, indent=2))
        n = len(parsed.get("bullets", []))
        cats = {b.get("category") for b in parsed.get("bullets", [])}
        print(f"  parsed OK: {n} bullets across {len(cats)} categories", flush=True)
    return {"fbgn": fbgn, "parsed_ok": parsed is not None, "elapsed_s": dt, "usage": usage}


def main():
    fbgn = sys.argv[1] if len(sys.argv) > 1 else "FBgn0003068"
    print(f"distilling {fbgn} via Claude Code headless (model={MODEL}, keys={len(KEYS)})")
    distill_one(fbgn)


if __name__ == "__main__":
    main()

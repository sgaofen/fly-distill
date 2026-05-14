"""Distill one gene via OpenAI Codex CLI (`codex exec`), using Stephen's ChatGPT
subscription. Output schema is identical to distill_via_claude.py — drop-in
replacement, just a different LLM backend.

Use case: third parallel pipeline alongside GLM (z.ai) and Sonnet (Max OAuth)
to triple effective throughput. Uses ChatGPT/Codex quota, independent from
both z.ai and Anthropic.

Usage:
  python3 src/distill_via_codex.py FBgn0003068
"""
import json
import os
import subprocess
import sys
import tempfile
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
MODEL = ENV.get("CODEX_MODEL", "gpt-5.5")   # default for ChatGPT-account Codex 0.130


def build_user_prompt(bundle: dict) -> str:
    """Re-use distill.py's bundle→prompt construction so output schema is identical."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("distill", ROOT / "src" / "distill.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    user_content = mod.build_input_message(bundle)
    prompt_file = os.environ.get("DISTILL_PROMPT_FILE", "distill_system.md")
    system_prompt = (ROOT / "prompts" / prompt_file).read_text()
    return (
        "SYSTEM INSTRUCTIONS — read first, do NOT echo back:\n"
        f"{system_prompt}\n\n"
        "================ END INSTRUCTIONS ================\n\n"
        f"{user_content}\n\n"
        "Now produce the JSON output as specified. Output ONLY the JSON, no commentary."
    )


def call_claude_headless(prompt: str, _unused_key: str = "", timeout_s: int = 1200) -> dict:
    """Invoke `codex exec` with the prompt on stdin. Mirrors the shape of
    distill_via_claude.call_claude_headless so pipeline.py is agnostic about
    which backend is used.

    Returns a dict shaped like the Claude Code JSON wrapper:
        {
          "result": "<text>",      # the assistant's final message (JSON)
          "is_error": bool,        # set if codex exited non-zero
          "duration_ms": int,
          "usage": {},             # (codex doesn't expose tokens the same way)
          "error_text": "...",     # populated on failure
        }
    """
    with tempfile.NamedTemporaryFile("r", suffix=".txt", delete=False) as f:
        last_msg_path = f.name

    cmd = [
        "codex", "exec",
        "--model", MODEL,
        "-c", 'model_reasoning_effort="medium"',
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox", "read-only",
        "--color", "never",
        "-o", last_msg_path,
        "-",        # read prompt from stdin
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd, input=prompt, env=os.environ.copy(),
            capture_output=True, text=True, timeout=timeout_s,
        )
    finally:
        pass
    dt_ms = int((time.time() - t0) * 1000)

    # Read the last assistant message (the JSON we asked for)
    last_msg = ""
    try:
        if os.path.exists(last_msg_path):
            with open(last_msg_path) as f:
                last_msg = f.read()
    except Exception:
        pass
    try:
        os.unlink(last_msg_path)
    except Exception:
        pass

    if proc.returncode != 0:
        # Save debug snapshot
        try:
            dbg = ROOT / "runs" / "claude_failures"
            dbg.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%dT%H%M%S")
            (dbg / f"{stamp}_codex_rc{proc.returncode}.txt").write_text(
                f"=== returncode: {proc.returncode}\n"
                f"=== stderr ({len(proc.stderr or '')} chars):\n{proc.stderr or ''}\n"
                f"=== stdout ({len(proc.stdout or '')} chars):\n{(proc.stdout or '')[:20000]}\n"
                f"=== last_msg ({len(last_msg)} chars):\n{last_msg[:5000]}\n"
            )
        except Exception:
            pass
        # Surface 429-ish + quota signals. CRITICAL: codex echoes the entire prompt
        # to stderr before its actual error message, so stderr can be 10-100k chars
        # and the real error is at the TAIL. Take the last 2KB of stderr to capture
        # the actual error (e.g. "You've hit your usage limit. ... try again at 5:07 AM").
        stderr_tail = (proc.stderr or "")[-3000:]
        combined = stderr_tail + "\n" + (proc.stdout or "") + "\n" + (last_msg or "")
        low = combined.lower()
        api_error_status = None
        if "429" in combined or "rate_limit_exceeded" in low or "rate limit" in low:
            api_error_status = 429
        return {
            "result": last_msg,
            "is_error": True,
            "api_error_status": api_error_status,
            "duration_ms": dt_ms,
            "duration_api_ms": 0,
            "usage": {},
            "error_text": stderr_tail or (proc.stdout or "")[-2000:],
        }

    return {
        "result": last_msg,
        "is_error": False,
        "api_error_status": None,
        "duration_ms": dt_ms,
        "duration_api_ms": dt_ms,
        "usage": {},
        "total_cost_usd": 0,
    }


def strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
    return s.strip()


_dummy_lock = threading.Lock()
def next_key() -> str:
    return "CHATGPT"


def main():
    fbgn = sys.argv[1] if len(sys.argv) > 1 else "FBgn0003068"
    bundle = json.loads((ROOT / "data" / "cache" / fbgn / "bundle.json").read_text())
    prompt = build_user_prompt(bundle)
    print(f"distilling {fbgn} via Codex ({MODEL}), prompt={len(prompt)} chars")
    t0 = time.time()
    wrapper = call_claude_headless(prompt, "")
    print(f"  elapsed={time.time()-t0:.1f}s  is_error={wrapper.get('is_error')}")
    if not wrapper.get("is_error"):
        text = wrapper.get("result", "")
        try:
            parsed = json.loads(strip_fences(text))
            print(f"  bullets={len(parsed.get('bullets', []))}")
        except Exception as e:
            print(f"  JSON parse failed: {e}")
            print(f"  raw (first 400): {text[:400]}")
    else:
        print(f"  error: {wrapper.get('error_text', '')[:300]}")


if __name__ == "__main__":
    main()

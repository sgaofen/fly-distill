"""Distill one gene via Google Gemini CLI in headless mode.

Uses `gemini -p <prompt> --output-format json --approval-mode plan` against
Stephen's free-tier Gemini account (~1000 prompts/day). Output schema is identical
to the other harnesses so canonicalize.py is backend-agnostic.

Free tier currently routes through gemini-3-flash-preview (~1.3s/call).

Usage:
  python3 src/distill_via_gemini.py FBgn0003068
"""
import json
import os
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
MODEL = os.environ.get("GEMINI_MODEL") or ENV.get("GEMINI_MODEL") or ""  # "" → CLI default


_GEMINI_STRICT_SUFFIX = """

================ ADDITIONAL EVIDENCE RULES (CRITICAL) ================

QUOTE INTEGRITY:
- Every string inside quotes ('...' or "...") in an `evidence` field MUST be a verbatim, character-for-character substring of the source you are citing.
- DO NOT insert annotations in brackets like [implied], [Bet1/Slh], or [including X] inside a quoted string. These are LLM additions and are FORBIDDEN.
- If the source does not name the fly gene explicitly, do NOT cite that source with a quote — instead express the bullet as inference with confidence="low" and direction="unknown", and use evidence prefix "INFERENCE:" (no quote).
- If a quote needs to be shortened, use "..." between two verbatim substrings — but both substrings must still appear in the source exactly as quoted.

THINK BEFORE WRITING:
- Before producing the JSON, internally check each evidence quote: does this exact string appear in the bundle text I was given? If unsure, drop the quote and reword as inference.
- Aim for tight, verifiable evidence; you lose 0 quality marks for skipping a weak bullet but lose substantial marks for fabricating quoted evidence."""


def build_user_prompt(bundle: dict) -> str:
    import importlib.util
    spec = importlib.util.spec_from_file_location("distill", ROOT / "src" / "distill.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    user_content = mod.build_input_message(bundle)
    prompt_file = os.environ.get("DISTILL_PROMPT_FILE", "distill_system.md")
    system_prompt = (ROOT / "prompts" / prompt_file).read_text()
    return (
        "SYSTEM INSTRUCTIONS — read first, do NOT echo back:\n"
        f"{system_prompt}"
        f"{_GEMINI_STRICT_SUFFIX}\n\n"
        "================ END INSTRUCTIONS ================\n\n"
        f"{user_content}\n\n"
        "Now produce the JSON output as specified. Output ONLY the JSON, no commentary."
    )


def call_claude_headless(prompt: str, _unused_key: str = "", timeout_s: int = 900) -> dict:
    """Invoke `gemini -p`. Returns a wrapper dict matching the shape that pipeline.py
    expects from claude --print (so distill_with_retry treats us identically):
      {is_error: bool, result: <text>, api_error_status?: str, usage: {...}}
    """
    env = dict(os.environ)
    args = [
        "gemini",
        "-p", prompt,
        "--output-format", "json",
        "--approval-mode", "plan",  # read-only, no file tool calls
    ]
    if MODEL:
        args.extend(["-m", MODEL])

    proc = subprocess.run(
        args,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )

    if proc.returncode != 0:
        try:
            dbg = ROOT / "runs" / "claude_failures"
            dbg.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%dT%H%M%S")
            (dbg / f"{stamp}_gemini_rc{proc.returncode}.txt").write_text(
                f"=== returncode: {proc.returncode}\n"
                f"=== stderr ({len(proc.stderr or '')} chars):\n{proc.stderr or ''}\n"
                f"=== stdout ({len(proc.stdout or '')} chars):\n{(proc.stdout or '')[:20000]}\n"
            )
        except Exception:
            pass
        combined = (proc.stderr or "") + "\n" + (proc.stdout or "")
        # Detect quota / rate-limit signatures
        is_quota = "exceeded" in combined.lower() or "quota" in combined.lower() or "rate limit" in combined.lower() or "RESOURCE_EXHAUSTED" in combined
        return {
            "is_error": True,
            "api_error_status": "429" if is_quota else str(proc.returncode),
            "result": combined[:2000],
            "error_text": combined[:2000],
            "usage": {},
        }

    # Parse gemini json wrapper: {session_id, response, stats: {models: {model_id: {tokens: {...}}}}}
    try:
        wrapper = json.loads(proc.stdout)
    except Exception as e:
        return {
            "is_error": True,
            "api_error_status": "parse_error",
            "result": f"gemini stdout not JSON: {e}: {proc.stdout[:500]}",
            "usage": {},
        }

    response_text = wrapper.get("response", "")
    # Aggregate usage across all models in stats
    usage_total = {"input_tokens": 0, "output_tokens": 0}
    stats_models = (wrapper.get("stats") or {}).get("models") or {}
    for _mid, mstats in stats_models.items():
        tk = (mstats or {}).get("tokens") or {}
        usage_total["input_tokens"] += tk.get("input", 0) or tk.get("prompt", 0) or 0
        usage_total["output_tokens"] += tk.get("candidates", 0) or 0

    return {
        "is_error": False,
        "result": response_text,
        "usage": usage_total,
        "session_id": wrapper.get("session_id"),
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
    return "GEMINI"


def main():
    fbgn = sys.argv[1] if len(sys.argv) > 1 else "FBgn0003068"
    bundle = json.loads((ROOT / "data" / "cache" / fbgn / "bundle.json").read_text())
    prompt = build_user_prompt(bundle)
    print(f"distilling {fbgn} via Gemini ({MODEL or 'default'}), prompt={len(prompt)} chars")
    t0 = time.time()
    wrapper = call_claude_headless(prompt, "")
    print(f"  elapsed={time.time()-t0:.1f}s  is_error={wrapper.get('is_error')}")
    if not wrapper.get("is_error"):
        text = wrapper.get("result", "")
        try:
            parsed = json.loads(strip_fences(text))
            print(f"  bullets={len(parsed.get('bullets', []))}")
            print(f"  usage: in={wrapper['usage'].get('input_tokens')} out={wrapper['usage'].get('output_tokens')}")
        except Exception as e:
            print(f"  parse failed: {e}")
            print(f"  raw[:500]: {text[:500]}")
    else:
        print(f"  error: {wrapper.get('result','')[:500]}")


if __name__ == "__main__":
    main()

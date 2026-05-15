"""Distill one gene via Claude Code headless routed to Xiaomi MiMo's
Anthropic-compatible endpoint (`token-plan-cn.xiaomimimo.com/anthropic`).

Uses Stephen's Pro-tier Token Plan key (~7 billion tokens free). Same
prompt/output schema as the GLM/Sonnet harnesses so canonicalize.py is
backend-agnostic.

Architecture mirrors distill_via_claude.py:
  bundle → claude --print with ANTHROPIC_BASE_URL=MiMo + MIMO_API_KEY
       → JSON wrapper → parse → bullets.json

Usage:
  MIMO_API_KEY=tp-... python3 src/distill_via_mimo.py FBgn0003068
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
BASE_URL = os.environ.get("MIMO_BASE_URL") or ENV.get("MIMO_BASE_URL") or "https://token-plan-sgp.xiaomimimo.com/anthropic"
MODEL = os.environ.get("MIMO_MODEL") or ENV.get("MIMO_MODEL") or "mimo-v2.5-pro"
API_KEY = os.environ.get("MIMO_API_KEY") or ENV.get("MIMO_API_KEY") or ""
if not API_KEY:
    sys.exit("Need MIMO_API_KEY env var (Xiaomi Token Plan tp-... key)")


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
        f"{system_prompt}\n\n"
        "================ END INSTRUCTIONS ================\n\n"
        f"{user_content}\n\n"
        "Now produce the JSON output as specified."
    )


def call_claude_headless(prompt: str, _unused_key: str = "", timeout_s: int = 900) -> dict:
    """Invoke claude --print routed to MiMo endpoint via env vars.
    900s ceiling because MiMo-V2.5-Pro is a 1.02T MoE with 1M context; very large
    bundles can take a while to stream."""
    env = dict(os.environ)
    env.update({
        "ANTHROPIC_BASE_URL": BASE_URL,
        "ANTHROPIC_AUTH_TOKEN": API_KEY,
        "ANTHROPIC_MODEL": MODEL,
        "ANTHROPIC_DEFAULT_OPUS_MODEL": MODEL,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": MODEL,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": MODEL,
        # isolate auth state so MiMo doesn't collide with z.ai or Max OAuth
        "CLAUDE_CONFIG_DIR": str(Path.home() / ".mimo-fly-distill"),
    })

    proc = subprocess.run(
        [
            "claude",
            "--print",
            "--model", MODEL,
            "--output-format", "json",
            "--permission-mode", "bypassPermissions",
            "--disallowedTools",
            "Task,Bash,Read,Edit,Write,WebFetch,WebSearch,Glob,Grep,NotebookEdit",
        ],
        input=prompt,
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
            (dbg / f"{stamp}_mimo_rc{proc.returncode}.txt").write_text(
                f"=== returncode: {proc.returncode}\n"
                f"=== stderr ({len(proc.stderr or '')} chars):\n{proc.stderr or ''}\n"
                f"=== stdout ({len(proc.stdout or '')} chars):\n{(proc.stdout or '')[:20000]}\n"
            )
        except Exception:
            pass
        try:
            return json.loads(proc.stdout)
        except Exception:
            pass
        raise RuntimeError(
            f"claude(mimo) exited {proc.returncode}: "
            f"stderr={proc.stderr[:400]!r} stdout_head={(proc.stdout or '')[:600]!r}"
        )
    return json.loads(proc.stdout)


def strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
    return s.strip()


_dummy_lock = threading.Lock()
def next_key() -> str:
    return "TP-PRO"


def main():
    fbgn = sys.argv[1] if len(sys.argv) > 1 else "FBgn0003068"
    bundle = json.loads((ROOT / "data" / "cache" / fbgn / "bundle.json").read_text())
    prompt = build_user_prompt(bundle)
    print(f"distilling {fbgn} via MiMo ({MODEL}), prompt={len(prompt)} chars")
    t0 = time.time()
    wrapper = call_claude_headless(prompt, "")
    print(f"  elapsed={time.time()-t0:.1f}s  is_error={wrapper.get('is_error')}")
    if not wrapper.get("is_error"):
        text = wrapper.get("result", "")
        parsed = json.loads(strip_fences(text))
        print(f"  bullets={len(parsed.get('bullets', []))}")


if __name__ == "__main__":
    main()

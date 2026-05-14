"""Distill one gene via Claude Code headless (`claude --print`) using the user's
Max-plan OAuth — NO z.ai routing. Output schema is identical to distill_via_claude.py
so canonicalize.py / pipeline.py treat it the same.

Use case: parallel pipeline alongside the GLM-based one to use Anthropic Max quota
on top of z.ai quota, doubling effective throughput.

Usage:
  python3 src/distill_via_sonnet.py FBgn0003068
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
# Default: Sonnet 4.6 via Stephen's Max OAuth (~/.claude.json credentials).
# Default to Opus 4.7 — Sonnet 4.6 was getting silent throttle from Anthropic
# (HTTP 200 + empty stream + stop_sequence + 0 tokens), causing 15-20 min hangs
# until subprocess timeout. Opus pool is less contended and exits cleanly on error.
MODEL = ENV.get("ANTHROPIC_DISTILL_MODEL", "claude-opus-4-7")


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
        "Now produce the JSON output as specified."
    )


def call_claude_headless(prompt: str, _unused_key: str = "", timeout_s: int = 360) -> dict:
    """Invoke `claude --print --model <Opus/Sonnet>` using Stephen's Max OAuth.

    Tight 360s subprocess timeout (vs 1200 for z.ai): Anthropic's silent throttle
    returns HTTP 200 with stop_sequence + 0 output_tokens. claude --print
    misinterprets this as a successful empty response and may hang waiting for
    additional events. Fail fast instead of bleeding Max quota on dead requests."""
    env = dict(os.environ)
    # Strip any z.ai env that might leak in from a parent shell
    for k in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN",
              "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
              "ANTHROPIC_DEFAULT_HAIKU_MODEL",
              "CLAUDE_CONFIG_DIR"):
        env.pop(k, None)

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
            (dbg / f"{stamp}_sonnet_rc{proc.returncode}.txt").write_text(
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
            f"claude(sonnet) exited {proc.returncode}: "
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


# Dummy key rotator — pipeline expects this symbol but Sonnet uses OAuth, no key
_dummy_lock = threading.Lock()
def next_key() -> str:
    return "OAUTH"


def main():
    fbgn = sys.argv[1] if len(sys.argv) > 1 else "FBgn0003068"
    bundle = json.loads((ROOT / "data" / "cache" / fbgn / "bundle.json").read_text())
    prompt = build_user_prompt(bundle)
    print(f"distilling {fbgn} via Sonnet ({MODEL}), prompt={len(prompt)} chars")
    t0 = time.time()
    wrapper = call_claude_headless(prompt, "")
    print(f"  elapsed={time.time()-t0:.1f}s  is_error={wrapper.get('is_error')}")
    if not wrapper.get("is_error"):
        text = wrapper.get("result", "")
        parsed = json.loads(strip_fences(text))
        print(f"  bullets={len(parsed.get('bullets', []))}")


if __name__ == "__main__":
    main()

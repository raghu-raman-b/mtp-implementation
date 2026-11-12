"""Start the model server of a config and keep it running (on the EC2), or check it with one request.

    cd ~/pipeline
    python3 -m scripts.llm.serve configs/qwen38_27b_vllm.json            # runs until Ctrl-C (use tmux), then stops
    python3 -m scripts.llm.serve configs/qwen38_27b_vllm.json --smoke    # start, one request, stop

The pipeline runs on the local PC and attaches to the server through an SSH port forward (pipeline/ec2.md). The
config files are the same on both sides: locally they attach only ("launch": false); here the server is started
from them whatever "launch" says, so the server and the requests always agree on the model name and its flags.
Needs only the standard library and the vLLM (or llama.cpp) binary the config names.
"""
from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # the pipeline folder
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts.llm import LLM, LLMConfig  # noqa: E402

SMOKE_PROMPT = "What is 17 times 23? Answer with the number only."


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config", help="LLMConfig file (.json or .toml)")
    ap.add_argument("--smoke", action="store_true", help="start the server, send one request, stop it")
    a = ap.parse_args()
    cfg = LLMConfig.load(a.config).with_(launch=True, url="", attach_wait_s=0)
    llm = LLM(cfg)
    llm.start()
    if not llm.server.launched:
        print(f"a server already answers at {cfg.base_url} (serving {llm.server.served_models()}); nothing started")
        return
    try:
        if a.smoke:
            r = llm.generate(SMOKE_PROMPT, max_tokens=2048)
            print(f"smoke test: {r.content!r} (391 expected), {r.output_tokens} tokens, {r.latency_s:.1f} s, "
                  f"thinking {len(r.reasoning)} chars, errors {r.errors or 'none'}")
            if not r.ok or "391" not in r.content:
                sys.exit(1)
            return
        print(f"serving {llm.model} at {cfg.base_url}; Ctrl-C stops it", flush=True)
        for sig in (signal.SIGTERM, signal.SIGHUP):    # tmux kill-session sends SIGHUP: stop vLLM too, not orphan it
            signal.signal(sig, lambda *_: sys.exit(0))
        while llm.server.proc.poll() is None:
            time.sleep(5)
        print(f"the server exited (code {llm.server.proc.returncode}); see its log")
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    finally:
        llm.stop()


if __name__ == "__main__":
    main()

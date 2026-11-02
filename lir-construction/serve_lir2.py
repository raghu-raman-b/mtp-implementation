#!/usr/bin/env python3
"""Start the LIR v2 model server(s) from lir2_config.toml and leave them running, so two runs can share them.

    python3 serve_lir2.py            # start (waits until ready), then e.g.
    python3 generate_lir2.py --lecture ../dataset/virtual_and_augmented_reality --slots 0-47 &
    python3 generate_lir2.py --lecture ../dataset/mit_6_7960_deep_learning   --slots 48-95 &
    python3 serve_lir2.py --stop

Uses the same command line as the pipeline (pipeline/llm.py Server.command), so cached answers stay valid.
Logs: logs/<role>_server.log.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pipeline.config import load  # noqa: E402
from pipeline.llm import Server, stop_port  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=HERE / "lir2_config.toml")
    ap.add_argument("--stop", action="store_true", help="stop the servers")
    args = ap.parse_args()
    cfg = load(args.config)
    specs = {}
    for spec in (cfg.generator, cfg.verifier, cfg.judge):
        if spec is not None and spec.local:
            specs.setdefault(spec.name, spec)           # roles naming the same model share one server
    for spec in specs.values():
        srv = Server(spec, cfg, HERE / "logs")
        if args.stop:
            stop_port(srv.port)
            print(f"stopped {spec.role} (port {srv.port})")
            continue
        if srv.health():
            print(f"{spec.role}: already running on port {srv.port}")
            continue
        srv.log_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = srv.command()
        print(f"{spec.role}: {spec.name}, {spec.slots} slots, {spec.kv_tokens:,}-token KV pool, port {srv.port}")
        print("  " + " ".join(cmd))
        proc = subprocess.Popen(cmd, stdout=open(srv.log_path, "a"), stderr=subprocess.STDOUT,
                                start_new_session=True, env=srv.env(cmd))
        t0 = time.time()
        while not srv.health():
            if proc.poll() is not None:
                sys.exit(f"server exited ({proc.returncode}); see {srv.log_path}")
            time.sleep(2)
        print(f"  ready in {time.time() - t0:.0f}s (pid {proc.pid}); log {srv.log_path}")


if __name__ == "__main__":
    main()

"""Server: start a vLLM or llama.cpp server for an LLMConfig, or attach to one that is already running.

Both engines serve the OpenAI chat API (/v1/chat/completions) and a /health endpoint, so the client is the same.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from .config import LLMConfig

LOG_DIR = Path(__file__).resolve().parents[2] / "output" / "logs"   # the pipeline's output/logs

LLAMA_THINK_END = "I have thought enough; now I give the final answer."


class Server:
    def __init__(self, cfg: LLMConfig, log=print):
        self.cfg, self.log = cfg, log
        self.proc: subprocess.Popen | None = None
        self.launched = False          # True when this object started the server (and so stops it)
        self.model_name = cfg.model or (cfg.model_path if cfg.engine == "vllm" else "")
        self.startup_s = 0.0

    @property
    def url(self) -> str:
        return self.cfg.base_url

    # ------------------------------------------------------------------ command
    def command(self) -> list[str]:
        """The command line that starts the server (shown in the notebook; nothing is run)."""
        return self._vllm() if self.cfg.engine == "vllm" else self._llamacpp()

    def _vllm(self) -> list[str]:
        c = self.cfg
        if not (c.model_path or c.model):
            raise ValueError("vLLM needs model_path (a Hugging Face repo id or a local folder)")
        cmd = [str(Path(c.binary or "vllm").expanduser()), "serve", c.model_path or c.model,
               "--served-model-name", self.model_name or c.model_path,
               "--host", c.host, "--port", str(c.port),
               "--max-model-len", str(c.context_length), "--max-num-seqs", str(c.slots),
               "--gpu-memory-utilization", str(c.gpu_memory_utilization),
               "--tensor-parallel-size", str(c.tensor_parallel_size), "--seed", str(c.seed),
               "--enable-prefix-caching" if c.prefix_caching else "--no-enable-prefix-caching"]
        for flag, value in (("--dtype", c.dtype), ("--quantization", c.quantization),
                            ("--kv-cache-dtype", c.kv_cache_dtype), ("--reasoning-parser", c.reasoning_parser)):
            if value:
                cmd += [flag, value]
        if c.max_num_batched_tokens:
            cmd += ["--max-num-batched-tokens", str(c.max_num_batched_tokens)]
        if c.think_end:
            cmd += ["--reasoning-config", json.dumps({"reasoning_end_str": c.think_end})]
        return cmd + [str(x) for x in c.extra_args]

    def _llamacpp(self) -> list[str]:
        c = self.cfg
        mp = c.model_path
        if not mp:
            raise ValueError("llama.cpp needs model_path (a .gguf file, 'org/repo:file.gguf' or 'org/repo:QUANT')")
        local = Path(mp).expanduser()
        if local.exists() or (mp.endswith(".gguf") and ":" not in mp):
            model = ["-m", str(local)]                       # a file on disk
        elif ":" in mp and mp.split(":", 1)[1].endswith(".gguf"):
            repo, file = mp.split(":", 1)
            model = ["-hfr", repo, "-hff", file]             # one file of a Hugging Face repo
        else:
            model = ["-hf", mp]                              # "org/repo" or "org/repo:QUANT"
        prefix = ["toolbox", "run", "-c", c.toolbox] if c.toolbox and not Path("/run/.toolboxenv").exists() else []
        cmd = prefix + [str(Path(c.binary or "llama-server").expanduser()), *model,
                        "-c", str(c.context_length), "-np", str(c.slots), "-ngl", str(c.gpu_layers),
                        "-fa", "on" if c.flash_attn else "off", "--seed", str(c.seed),
                        "--host", c.host, "--port", str(c.port), "--metrics"]
        if c.kv_unified:
            cmd.append("--kv-unified")
        if c.jinja:
            cmd.append("--jinja")
        if c.model:
            cmd += ["--alias", c.model]
        if c.thinking:
            cmd += ["--reasoning", "on", "--reasoning-format", c.reasoning_format]
            if c.think_budget:
                cmd += ["--reasoning-budget", str(c.think_budget),
                        "--reasoning-budget-message", c.think_end or LLAMA_THINK_END]
        else:
            cmd += ["--reasoning", "off"]
        return cmd + [str(x) for x in c.extra_args]

    # ------------------------------------------------------------------ state
    def healthy(self) -> bool:
        try:
            with urllib.request.urlopen(self.url + "/health", timeout=3) as r:
                return r.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def served_models(self) -> list[str]:
        with urllib.request.urlopen(self.url + "/v1/models", timeout=10) as r:
            return [m["id"] for m in json.load(r).get("data", [])]

    # ------------------------------------------------------------------ start / stop
    def start(self):
        """Attach to a server that answers at the URL, or start one (when cfg.launch). Waits until it is ready."""
        if self.healthy():
            self.log(f"attached to the server at {self.url}")
        elif self.cfg.launch and not self.cfg.url:
            self._launch()
        elif self.cfg.attach_wait_s > 0:
            self._wait_for_server()
        else:
            raise RuntimeError(f"no server answers at {self.url} (launch is off or url points elsewhere)")
        if not self.model_name:
            models = self.served_models()
            if not models:
                raise RuntimeError(f"the server at {self.url} serves no model")
            self.model_name = models[0]
        elif not self.launched and not self.cfg.launch:
            # attach only: the port must serve this config's model, or its answers would be cached under this
            # config's hash (a forwarded port can reach whichever server runs on the EC2)
            models = self.served_models()
            if self.model_name not in models:
                raise RuntimeError(f"the server at {self.url} serves {models}, not {self.model_name!r}: "
                                   f"another model is running on this port")
        return self

    def _wait_for_server(self):
        """Attach only: wait until a server answers (someone starts or swaps it), up to cfg.attach_wait_s."""
        t0, next_note = time.time(), 0.0
        while not self.healthy():
            waited = time.time() - t0
            if waited > self.cfg.attach_wait_s:
                raise TimeoutError(f"no server answered at {self.url} within {self.cfg.attach_wait_s} s")
            if waited >= next_note:
                self.log(f"  {time.strftime('%H:%M:%S')}  waiting for {self.model_name or 'a server'} at {self.url} "
                         f"({waited:.0f} of {self.cfg.attach_wait_s} s; start it on the EC2, see pipeline/ec2.md)")
                next_note += 60
            time.sleep(3)
        self.log(f"attached to the server at {self.url} after waiting {time.time() - t0:.0f} s")

    def _launch(self):
        c = self.cfg
        cmd = self.command()
        if c.toolbox and cmd[0] == "toolbox" and not shutil.which("toolbox"):
            raise RuntimeError("toolbox is set in the config but the toolbox command is not installed")
        env = dict(os.environ)
        if c.engine == "vllm" and os.sep in cmd[0]:   # vLLM compiles kernels with tools from its own venv and CUDA
            env["PATH"] = f"{Path(cmd[0]).parent}:/usr/local/cuda/bin:{env.get('PATH', '')}"
        env.update({k: str(v) for k, v in c.env.items()})
        log_path = Path(c.server_log) if c.server_log else LOG_DIR / f"llm_server_{c.port}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log(f"starting {c.engine}: {' '.join(cmd)}\n  server log: {log_path}")
        t0 = time.time()
        log_start = log_path.stat().st_size if log_path.exists() else 0
        self.proc = subprocess.Popen(cmd, stdout=open(log_path, "ab"), stderr=subprocess.STDOUT, env=env,
                                     start_new_session=True)
        self.launched = True
        next_note = t0 + 30
        while not self.healthy():
            if time.time() >= next_note:     # every 30 s: how long, and what the server is doing (its last log line)
                next_note += 30
                self.log(f"  {time.strftime('%H:%M:%S')}  … starting {c.engine} ({time.time() - t0:.0f} s): "
                         f"{self._last_log_line(log_path, log_start)}")
            if self.proc.poll() is not None:
                tail = "\n".join(log_path.read_text(errors="replace").splitlines()[-30:])
                self.launched = False
                raise RuntimeError(f"the server exited (code {self.proc.returncode}); end of {log_path}:\n{tail}")
            if time.time() - t0 > c.startup_timeout_s:
                self.stop()
                raise TimeoutError(f"the server was not ready after {c.startup_timeout_s} s; see {log_path}")
            time.sleep(2)
        self.startup_s = time.time() - t0
        self.log(f"server ready in {self.startup_s:.0f} s at {self.url}")

    @staticmethod
    def _last_log_line(path: Path, start: int = 0, width: int = 110) -> str:
        """The last line this launch wrote to the server log (from byte `start`; the log is appended to), without
        vLLM's process prefix; progress bars keep their latest state."""
        try:
            with open(path, "rb") as f:
                f.seek(max(start, f.seek(0, 2) - 4096))
                tail = f.read().decode(errors="replace")
        except OSError:
            return ""
        lines = [x for x in tail.replace("\r", "\n").splitlines() if x.strip()]
        last = lines[-1] if lines else ""
        last = re.sub(r"^\((?:APIServer|EngineCore)[^)]*\)\s*", "", last)
        last = re.sub(r"^(?:INFO|WARNING|DEBUG)\s+\S+\s+\S+\s+\[[^\]]*\]\s*", "", last)
        return last[:width]

    def stop(self):
        """Stop the server if this object started it (an attached server is left running)."""
        if not self.launched or self.proc is None:
            return
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            os.killpg(self.proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if self.cfg.toolbox:   # inside a toolbox the server is not in our process group
            exe = "llama-server" if self.cfg.engine == "llamacpp" else "vllm serve"
            subprocess.run(["pkill", "-f", f"{exe}.*--port {self.cfg.port}"], check=False)
        self.launched, self.proc = False, None
        self.log("server stopped")

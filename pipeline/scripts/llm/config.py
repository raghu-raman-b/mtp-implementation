"""LLMConfig: one model server (which engine, which model, how it is started) and how requests are sent to it."""
from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

ENGINES = ("vllm", "llamacpp")


@dataclass
class LLMConfig:
    # ---------------------------------------------------------------- model
    engine: str = "llamacpp"        # "vllm" or "llamacpp"
    model: str = ""                 # the name requests use (vLLM --served-model-name, llama.cpp --alias);
                                    # empty: model_path for vLLM, or whatever an attached server reports
    model_path: str = ""            # where the weights are. vLLM: Hugging Face repo id or local folder.
                                    # llama.cpp: local .gguf file, "org/repo:file.gguf", or "org/repo:QUANT"

    # ---------------------------------------------------------------- server
    launch: bool = True             # True: start a server when none answers at the URL; False: attach only
    host: str = "127.0.0.1"
    port: int = 8000
    url: str = ""                   # a server elsewhere, e.g. "http://10.0.0.5:8000" (overrides host and port)
    binary: str = ""                # vllm or llama-server executable; empty: "vllm" / "llama-server" on PATH
    toolbox: str = ""               # run the server inside this toolbox container (Fedora), e.g. "llm-engine"
    env: dict = field(default_factory=dict)   # extra environment variables for the server process
    startup_timeout_s: int = 1800   # loading a large model (and vLLM's compile step) can take many minutes
    server_log: str = ""            # server output goes here; empty: llm_server_<port>.log in the working folder

    # ---------------------------------------------------------------- engine (both)
    context_length: int = 32768     # longest prompt + answer. vLLM --max-model-len; llama.cpp -c (shared by all
                                    # slots with kv_unified, else divided between them)
    slots: int = 8                  # requests the server runs at once: vLLM --max-num-seqs, llama.cpp -np
    seed: int = 0
    extra_args: list = field(default_factory=list)   # more server flags, passed as they are

    # ---------------------------------------------------------------- engine: vLLM only
    gpu_memory_utilization: float = 0.90
    tensor_parallel_size: int = 1
    dtype: str = ""                 # e.g. "bfloat16"; empty: vLLM's default
    quantization: str = ""          # e.g. "fp8"; empty: from the checkpoint
    kv_cache_dtype: str = ""        # e.g. "fp8"; empty: same as the model
    prefix_caching: bool = True     # requests that share a prompt start reuse its KV cache
    max_num_batched_tokens: int = 0  # 0: vLLM's default
    reasoning_parser: str = ""      # e.g. "qwen3": thinking is returned apart from the answer
    think_end: str = ""             # words that close the thinking when it reaches think_budget
                                    # (vLLM --reasoning-config reasoning_end_str; llama.cpp --reasoning-budget-message)

    # ---------------------------------------------------------------- engine: llama.cpp only
    gpu_layers: int = 99            # -ngl: layers on the GPU
    flash_attn: bool = True         # -fa on
    kv_unified: bool = True         # one KV pool shared by all slots
    jinja: bool = True              # use the model's own chat template
    reasoning_format: str = "deepseek"   # thinking returned apart from the answer

    # ---------------------------------------------------------------- sampling (a Request can override each)
    temperature: float = 0.6
    top_p: float = 0.95
    top_k: int = 20
    min_p: float = 0.0
    presence_penalty: float = 0.0
    repetition_penalty: float = 1.0
    max_tokens: int = 8192          # thinking + answer; 0: no cap (up to the context length)

    # ---------------------------------------------------------------- thinking
    thinking: bool = True           # chat_template_kwargs enable_thinking
    think_budget: int = 0           # cap on thinking tokens, 0: none. vLLM: per request (thinking_token_budget);
                                    # llama.cpp: per server (--reasoning-budget), fixed when the server starts

    # ---------------------------------------------------------------- client
    concurrency: int = 0            # parallel mode: requests in flight; 0: slots
    timeout_s: int = 3600           # one request
    retries: int = 2                # more attempts when an answer fails its check (each with the next seed)
    cache_file: str = ""            # answers cached by request hash (JSON lines); empty: no cache
    log_file: str = ""              # one JSON line per attempt (tokens, time, finish, errors); empty: no log

    def __post_init__(self):
        if self.engine not in ENGINES:
            raise ValueError(f"engine must be one of {ENGINES}, not {self.engine!r}")

    # -----------------------------------------------------------------
    @property
    def base_url(self) -> str:
        return (self.url or f"http://{self.host}:{self.port}").rstrip("/")

    def sampling(self) -> dict:
        return {k: getattr(self, k) for k in
                ("temperature", "top_p", "top_k", "min_p", "presence_penalty", "repetition_penalty")}

    def with_(self, **changes) -> "LLMConfig":
        """A copy with some fields changed: cfg.with_(temperature=0, think_budget=4096)."""
        return replace(self, **changes)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str | Path):
        """Write the config as JSON (load it back with LLMConfig.load)."""
        Path(path).write_text(json.dumps(self.to_dict(), indent=1) + "\n")

    @classmethod
    def load(cls, path: str | Path) -> "LLMConfig":
        """Read a config from .json or .toml (top-level keys are the field names)."""
        p = Path(path)
        d = tomllib.loads(p.read_text()) if p.suffix == ".toml" else json.loads(p.read_text())
        known = {f.name for f in fields(cls)}
        unknown = set(d) - known
        if unknown:
            raise ValueError(f"unknown config keys in {p}: {sorted(unknown)}")
        return cls(**d)

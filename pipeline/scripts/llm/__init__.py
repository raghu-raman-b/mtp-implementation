"""LLM calling for the pipeline: vLLM or llama.cpp, sequential or parallel. See pipeline.ipynb for examples.

    from scripts.llm import LLM, LLMConfig, Request
    cfg = LLMConfig(engine="llamacpp", model_path="unsloth/gemma-4-E4B-it-GGUF:Q8_0", context_length=32768)
    with LLM(cfg) as llm:
        print(llm.generate("Say hi").content)
"""
from .client import LLM, Request, RequestRejected, Result
from .config import LLMConfig
from .server import Server

__all__ = ["LLM", "LLMConfig", "Request", "Result", "RequestRejected", "Server"]

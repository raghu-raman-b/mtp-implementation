"""Question answering over a course's knowledge layer (pipeline v3, block 6).

    from qa import answer
    answer("What is an HMD?", course="nptel_vr", lecture="4")
    -> {"answer": str, "citations": [{"fact", "lecture", "segment", "start", "end", "text"}],
        "steps": [{"tool", "args", "result_summary"}], "covered": bool}

    python -m qa "What is an HMD?" [--lecture 4] [--course nptel_vr] [--config configs/...json] [--json]

qa/knowledge.py reads output/<course>/knowledge/ (or $QA_OUTPUT/<course>/knowledge/); qa/tools.py holds the five tools
(check_concept, fact_lookup, lecture_dependencies, lecture_overview, course_goals); qa/answer.py the tool loop. The
prompts are prompts/qa_system.txt and prompts/qa_tools.json.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent      # the pipeline folder: qa uses its scripts/ package
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from .answer import answer, get_llm, warm  # noqa: E402
from .knowledge import Knowledge  # noqa: E402
from .tools import run_tool, tool_specs  # noqa: E402

__all__ = ["answer", "get_llm", "warm", "Knowledge", "run_tool", "tool_specs"]

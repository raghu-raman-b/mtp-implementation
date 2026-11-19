#!/bin/bash
# Every GPU step of the comparison, in order (timed systems first, one at a time; then the GraphRAG index).
set -x
cd "$(dirname "$0")"
R="not_covered where prerequisite structure formula"
python3 run_systems.py ours abl_facts abl_graph rag_think
for r in 2 3; do python3 run_systems.py ours rag rag_think --run $r --categories $R; done
python3 graphrag_build.py extract
python3 graphrag_build.py graph
python3 run_systems.py graphrag_notext graphrag_text
echo ALL_DONE

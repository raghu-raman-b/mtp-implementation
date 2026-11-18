#!/bin/bash
# routes.sh BASE: time + size of each route (identity and gzip)
B=$1
for r in /api/course /api/lecture/62 /data/knowledge/concepts.json /data/knowledge/facts.json /data/knowledge/relations.json /data/knowledge/lecture_graph.json /api/home /api/view/5 /api/view/62 /api/glossary /api/coursemap /api/concept/C0002 /api/review; do
  a=$(curl -s -o /dev/null -w "%{http_code} %{size_download} %{time_total}" $B$r)
  g=$(curl -s -o /dev/null -H 'Accept-Encoding: gzip' -w "%{size_download} %{time_total}" $B$r)
  printf "%-36s %s | gzip %s\n" "$r" "$a" "$g"
done

"""The "what fails where" table of the Evaluation part, from analysis/failures/inventory.json.

The counts and the handling come from the inventory (analysis/failures/inventory.py: code rules, the pipeline's own
check files and judge verdicts, stored similarities; no model and no agent decided what a failure is). What is written
here is only the last column, how each row is handled, in a few words; its numbers are the inventory's notes.
A row of the inventory that is neither described here nor in SKIP stops the build, so a new failure kind cannot go
missing from the docs.
"""
import html
import json

E = html.escape

# rows left out of the docs on purpose (the user's scope for the docs update of 2026-11-18: nothing on part titles)
SKIP = {"seg.part_titles"}

# (stage shown, inventory id, how it is handled), in pipeline order
REPORTED_2A = "Report-only flag in 2a; the 2b judge, which would act on it, was not run."
REPORTED_2C = "Report-only flag in 2c; stages 3 and 4a use the concepts as extracted."
NO_SIGNAL = ("Found by a code rule. The pipeline has no signal for which concept or name is right, so nothing "
             "removes or merges them.")
ROWS = [
    ("0a", "fact.0a.null_start", "By design: a sentence that begins inside a subtitle cue has no start time. 1b places "
     "boundaries inside the cue; 4d fills the facts' times (2026-11-13)."),
    ("1b", "seg.1b.flagged_left", "Left as reported in <code>stage_1b_verify_segments/report.json</code>."),
    ("2a", "fact.2a.long", REPORTED_2A),
    ("2a", "fact.2a.bare_acronym", REPORTED_2A),
    ("2a", "fact.2a.pointing", REPORTED_2A),
    ("2a", "fact.2a.acronym", REPORTED_2A),
    ("2a", "fact.2a.sentences_uncited", "Many are greetings, recaps and asides; the share is not a defect by itself."),
    ("2a, 4d", "seg.no_facts", "Mostly introductions and closing summaries: nothing to ask, recap or link there."),
    ("2b", "fact.2b.not_judged", "2b ran with <code>--no-judge</code>: on the gold set the fact judge caught 0 or 1 of 7 "
     "real failures, and 7 of the 8 facts it acted on were good (<a href=\"#s2b\">stage 2b</a>). The rerun with the "
     "revised prompts is pending."),
    ("2c", "con.2c.reverse", REPORTED_2C),
    ("2c", "con.2c.name_not_in_facts", REPORTED_2C),
    ("2c", "con.2c.no_triple", REPORTED_2C),
    ("2c", "con.2c.no_shared_fact", REPORTED_2C),
    ("2c", "con.2c.acronym_in_name", REPORTED_2C),
    ("2c", "con.2c.alias_not_in_facts", "Lost and added items are retried in 2c (63 retries in turn 1, 22 in turn 2, "
     "none unresolved); what is left is reported."),
    ("2c", "con.2c.fact_without_concept", REPORTED_2C),
    ("3", "con.acronym_expansion", "3b's synonym merge (262 model merges) removed most: of the MVP's six acronym and "
     "expansion twins, five now resolve to one concept. The headset family (C0005, C0075, C0735) still appears together "
     "on 7 lecture maps (11 in the MVP)."),
    ("3", "con.generic_modifier", NO_SIGNAL),
    ("3", "con.embedding_similar", "The 3b model judged these pairs and kept them apart, except 8 that 3b's cap (12 "
     "candidates per cluster) left unjudged."),
    ("3, 2c", "con.shared_key", "100 concept pairs (alias and name 43, alias and alias 34, acronym and acronym 8, …). "
     + NO_SIGNAL),
    ("3, 2c", "con.name_is_other_alias", "A subset of the row above."),
    ("3, 2c", "con.acronym_of_other_concept", "FOV on “horizontal field of view”. " + NO_SIGNAL),
    ("3", "con.alias_shared_by_many", NO_SIGNAL),
    ("2c, 3", "con.alias_fragment", NO_SIGNAL),
    ("2c, 3", "con.alias_short", NO_SIGNAL),
    ("2c, 3", "con.alias_generic", NO_SIGNAL),
    ("4a", "con.connecting", "Signal: 4a's <code>defined</code> flag. No concept card, not in the glossary, flagged "
     "<code>connecting</code> on the maps, and the model-written sentence is never sent; question answering gets their "
     "facts only (decision of 2026-11-18)."),
    ("4a", "con.4a.defined_mismatch", "272 are <code>defined: true</code> with no defining segment (they keep a card and a "
     "glossary entry); 4 are <code>defined: false</code> with one. Reported, not acted on."),
    ("4a", "con.4a.misplaced", "Reported by 4a's checks."),
    ("4a", "con.4a.capped", "The definition was written from 40 of the concept's facts."),
    ("4a", "con.4a.definition_no_verb", "The real 4a (one call per concept, 2026-11-17) replaced the MVP's definitions, "
     "which were the first defining fact (26% read like a definition). This rule is a lower bound of what is left."),
    ("4b", "seg.4b.in_no_objective", "Mostly closing summaries."),
    ("4c", "seg.4c.assumed", "Signal: 4c's lecture graph. Listed as what a lecture builds on, not as cards; 1,806 of "
     "them are connecting concepts."),
    ("4d", "seg.4d.broken_refs", "4d's reference check, run again by <code>analysis/mvp/integrity.py</code>."),
    ("4d", "fact.no_segment", "4d's reference check."),
    ("4d", "fact.null_time", "4d fills null sentence times (2026-11-13)."),
    ("4f", "seg.cs_failed", "Code check (IDs of the segment, no duplicates), retried with the problems shown; a cut-off "
     "answer is asked again with thinking off."),
    ("4f", "seg.cs_time_fallback", "The time still points into the right segment, only less exactly."),
    ("4f", "seg.cs_run1_vs_now", "Revised prompt (explicit exclusions), <code>max_tokens</code> 8,192; run 1 kept in "
     "<code>history/run1/</code>. Counts only; the remaining noise is reported, not filtered by hand."),
    ("4d", "fact.shared_start", "A fact's time is the start of its first evidence sentence, often where the topic is "
     "introduced."),
    ("5", "act.retried", "Code checks, retried with the problem written out; 0 units left unresolved. Retries: quiz 104, "
     "recap 59, crossword 22, odd one out 9, open question 2, put in order 1."),
    ("5", "act.quiz.correct_longest", "Was 52% (751 of 1,443) in the MVP; the retry check “correct option is the "
     "longest” brought it to 14%, below the 25% a unique longest has by chance."),
    ("5", "act.crossword.clue_has_answer", "s5 blanks answer words in a clue and retries; this rule re-checks the "
     "final text."),
    ("5", "act.crossword.clue_masked", "The 5 masked crosswords of the MVP were written again in the judge run."),
    ("5", "act.judge_unresolved", "The judge and one rewrite round repaired 221 of 1,086 first-judgement failures. The "
     "865 left are handled per kind in the rows below; nothing is dropped from the data."),
    ("5", "act.quiz.judge_failed", "Hidden when it failed <code>answerable</code>, <code>clear</code>, "
     "<code>no_source_talk</code> or <code>one_answer</code>: 35 of the 102. The 67 that failed only "
     "<code>no_giveaway</code> or <code>worth_asking</code> are shown. First judgement 285, rewrite repaired 183."),
    ("5", "act.open_question.judge_failed", "Every failed item hidden (24 of 24). First judgement 62."),
    ("5", "act.odd_one_out.judge_failed", "Every failed item hidden (39 of 39)."),
    ("5", "act.put_in_order.judge_failed", "Every failed item hidden (25 of 25)."),
    ("5", "act.recap.points_failed", "Only the points the judge passed are shown (decision of 2026-11-18; display only, "
     "nothing generated again)."),
    ("5", "act.recap.text_failed", "The summary text is shown only when it passed."),
    ("5", "act.recap.no_passing_point", "The recap is not shown; that break shows only the quiz."),
    ("5", "act.crossword.clue_failed", "The grid is kept; the failed words are shown filled in and their clues are "
     "never shown."),
    ("5", "act.whole_hidden", "Per kind: put in order 24 of 41, odd one out 9 of 57, recap 6 of 347, quiz 1 of 347, "
     "open question 0 of 63."),
    ("5", "act.map.too_big", "Maps are made by code (median 71 nodes, max 159). The viewer shows about 20 key concepts, "
     "with “all N, by part” as an option (<code>0965ba9</code>)."),
    ("5", "act.units_empty_skipped", "A kind may be missing by the contract: put in order empty in 25 units, odd one out "
     "in 6; lecture 1 has no recall (no earlier concept), lecture 63 no crossword (5 facts)."),
    ("5", "act.crossword.clue_has_part", "s5 masks the words of the name; what slips through is counted."),
    ("5", "act.crossword.clue_duplicate", "Rule run; none found."),
    ("5", "act.match.truncated", "The right side is the 4a definition cut to a word cap by s5; match the pairs has no "
     "judge."),
    ("5", "act.match.term_in_definition", "s5 trims the term from the start of the definition, not from later in it."),
    ("5", "act.match.twin_rows", "Rule run; none found."),
    ("5", "act.match.bad_start", "Rule run; none found."),
    ("5", "act.map.long_edge_label", "Reported."),
    ("5", "act.completemap.blank_twice", "Rule run; none found."),
    ("5", "act.code_flags", "Report-only. Most: <code>odd_one_out.not_a_concept</code> 85, "
     "<code>recap.facts_uncovered</code> 42, <code>crossword.filled_from_used</code> 20."),
    ("QA", "qa.slow", "Thinking only in round 0 and an early exit for unknown names (2026-11-17): bench median 4.8 s, "
     "max 9.3 s."),
    ("QA", "qa.bench_slow", "Comparisons (two cards, long answers) stay the slowest."),
    ("QA", "qa.not_covered_padded", "The time is fixed (early exit when nothing close is found); the padding itself is "
     "unchanged."),
    ("QA, 4c", "qa.prereq_odd", "<code>lecture_dependencies</code> rewritten (2026-11-17): single mentions listed “in "
     "passing”, the rest ranked by uses."),
    ("QA", "qa.two_times", "A time the model writes before a citation is removed; the citation carries one time."),
    ("QA, viewer", "qa.markdown_raw", "Bold and lists rendered since 2026-11-13; formulas typeset with KaTeX, bundled "
     "for offline use, since 2026-11-18."),
]


def build(A):
    inv = json.loads((A / "failures/inventory.json").read_text())
    rows = {r["id"]: r for r in inv["rows"]}
    ours = [i for _, i, _ in ROWS]
    missing = sorted(set(rows) - set(ours) - SKIP)
    unknown = sorted(set(ours) - set(rows))
    if missing or unknown or len(ours) != len(set(ours)):
        raise SystemExit(f"failures.py out of step with inventory.json: missing {missing}, unknown {unknown}")
    handled = {}
    trs = []
    for stage, i, how in ROWS:
        r = rows[i]
        n, d = r["count"], r["denominator"]
        pct = f" ({100 * n / d:.1f}%)" if d else ""
        handled[r["handling"]] = handled.get(r["handling"], 0) + 1
        trs.append(f"<tr><td>{E(stage)}</td><td>{E(r['what_fails'])} <span class=\"small muted mono\">{E(i)}</span></td>"
                   f"<td class=\"n\">{n:,} of {d:,} {E(r['unit'])}{pct}</td><td>{E(r['handling'])}</td><td>{how}</td></tr>")
    head = ("<tr><th>Stage</th><th>What fails</th><th class=\"n\">Count</th><th>Handling</th>"
            "<th>How</th></tr>")
    table = f'<div class="tablewrap"><table>{head}{"".join(trs)}</table></div>'
    order = inv["handling_values"]
    summary = ", ".join(f"{handled[h]} {E(h)}" for h in order if h in handled)
    sc = inv["self_checks"]
    note = (f'<p class="small muted">{len(ROWS)} rows: {summary}. Counts and handling from '
            f'<code>analysis/failures/inventory.json</code>, written by <code>analysis/failures/inventory.py</code> from '
            f'<code>pipeline/output/nptel_vr/</code> (read only) and the QA records in <code>analysis/</code>; each row\'s '
            f'rule, examples and precision note are in <code>inventory.md</code>. Self-check: judge-failed items counted '
            f'there {sc["judge_failed_items_sum"]:,}, the pipeline\'s own total '
            f'{sc["pipeline_still_failed_items"]:,}. For a row handled as fixed, the count is what is left after the '
            f'fix. QA rows count the MVP test answers and the bench, not the whole course.</p>')
    hist = "".join(f"<tr><td>{E(h['date'])}</td><td>{E(h['failure'])}</td><td>{E(h['fix'])}</td></tr>"
                   for h in inv["history"])
    history = ('<details><summary>Failures found earlier and fixed before this inventory '
               '<span class="meta">inventory.json, “history”</span></summary><div class="tablewrap"><table>'
               f'<tr><th>Date</th><th>What failed</th><th>Fix</th></tr>{hist}</table></div></details>')
    return table + note + history

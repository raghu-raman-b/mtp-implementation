#!/usr/bin/env python
"""Compare segmenters on one lecture against human coarse boundaries.

    python compare/run_compare.py [--only texttiling|topictiling|tsvlt]

Methods, all on the same sentence units (texttiling.to_sentences over the SRT):
  texttiling   the pipeline's embedding TextTiling, window swept, other parameters default
  topictiling  LDA TopicTiling (Riedl & Biemann 2012), LDA trained on the other lectures of the course
  tsvlt        TSVLT/TSLVT four-stage model, trained with its own classes and default hyperparameters
               on the five sample transcripts bundled with the repo (no checkpoints are published)

Writes compare/results.json.
"""
import contextlib
import csv
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))
import texttiling as tt  # noqa: E402

COURSE = ROOT / "Virtual and Augmented Reality NPTEL course"
LEC = COURSE / "Week 1" / "Lecture 1"
SRT = sorted((LEC / "raw").glob("*.srt"))[0]
LABELS = ROOT / "lec1__P01__both.json"
TSVLT = ROOT / "TSVLT-Lecture-Topic-Segmentation"

WINDOWS = [30, 45, 60, 90, 120, 150, 180, 240, 300]
TSVLT_SEEDS = [0, 1, 2, 3, 4]
TOL = [15, 30, 60]


# ----------------------------------------------------------------- metrics
def seg_ids(gaps, n):
    ids, k = np.zeros(n, dtype=int), 0
    for i in range(n):
        ids[i] = k
        if i in gaps:
            k += 1
    return ids


def pk_wd(pred, gold, n):
    """Pk (Beeferman 1999) and WindowDiff (Pevzner & Hearst 2002) over sentence units,
    k = half the mean gold segment length."""
    k = max(2, round(n / (2 * (len(gold) + 1))))
    p, g = seg_ids(set(pred), n), seg_ids(set(gold), n)
    pk = np.mean([(p[i] == p[i + k]) != (g[i] == g[i + k]) for i in range(n - k)])
    wd = np.mean([(p[i + k] - p[i]) != (g[i + k] - g[i]) for i in range(n - k)])
    return float(pk), float(wd), k


def match_f1(pred_t, gold_t, tol):
    """One-to-one matching of boundaries within +-tol seconds."""
    used, tp = set(), 0
    for g in gold_t:
        cands = [(abs(p - g), j) for j, p in enumerate(pred_t) if j not in used and abs(p - g) <= tol]
        if cands:
            used.add(min(cands)[1])
            tp += 1
    pr = tp / len(pred_t) if pred_t else 0.0
    rc = tp / len(gold_t) if gold_t else 0.0
    return {"tp": tp, "precision": pr, "recall": rc, "f1": 2 * pr * rc / (pr + rc) if pr + rc else 0.0}


def evaluate(gaps, units, gold_gaps, gold_t):
    n = len(units)
    gaps = sorted(set(g for g in gaps if 0 <= g < n - 1))
    times = [units[g + 1].start for g in gaps]
    pk, wd, k = pk_wd(gaps, gold_gaps, n)
    durs = np.diff([units[0].start] + times + [units[-1].end])
    out = {"gaps": gaps, "times": times, "n_boundaries": len(gaps), "pk": pk, "wd": wd, "k": k,
           "seg_dur_mean": float(durs.mean()), "seg_dur_min": float(durs.min()), "seg_dur_max": float(durs.max()),
           "gold_miss_dist": float(np.mean([min(abs(p - g) for p in times) for g in gold_t])) if times else None,
           "pred_miss_dist": float(np.mean([min(abs(p - g) for g in gold_t) for p in times])) if times else None}
    for tol in TOL:
        out[f"f1@{tol}"] = match_f1(times, gold_t, tol)
    return out


# ----------------------------------------------------------------- TextTiling
def run_texttiling(emb):
    tt.embed = lambda texts, show_progress=True: emb  # every run reuses the same embeddings
    runs = []
    for min_seg in (360.0, 0.0):
        for w in WINDOWS:
            segs, gaps, meta = tt.segment(SRT, window=float(w), min_seg=min_seg, log=lambda m: None)
            runs.append({"window": w, "min_seg": min_seg, "tau": meta["tau"],
                         "gaps": [i for i, g in enumerate(gaps) if g["boundary"]],
                         "curve": [g["sim_smooth"] for g in gaps]})
    return runs


# ----------------------------------------------------------------- TopicTiling
def tokens(text):
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    return [w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in ENGLISH_STOP_WORDS]


def lda_corpus(min_words=150):
    """Paragraph chunks of every other lecture's transcript (lecture 1 is held out)."""
    docs = []
    for f in sorted(COURSE.glob("*/*/content/*.txt")):
        if f.parent.parent == LEC:
            continue
        cur = []
        for para in f.read_text(encoding="utf-8", errors="replace").splitlines():
            cur += tokens(para)
            if len(cur) >= min_words:
                docs.append(cur)
                cur = []
        if cur:
            docs.append(cur)
    return docs


def hearst_depth(s):
    d = np.zeros_like(s)
    for g in range(len(s)):
        lp = s[g]
        for i in range(g - 1, -1, -1):
            if s[i] < lp:
                break
            lp = s[i]
        rp = s[g]
        for i in range(g + 1, len(s)):
            if s[i] < rp:
                break
            rp = s[i]
        d[g] = (lp - s[g] + rp - s[g]) / 2
    return d


def run_topictiling(units, n_topics=100, train_iter=500, infer_rep=30, windows=(1, 2, 3, 5, 8, 10, 15, 20, 25, 30, 35), seed=0):
    import tomotopy as tp
    docs = lda_corpus()
    mdl = tp.LDAModel(k=n_topics, alpha=50.0 / n_topics, eta=0.01, seed=seed)
    for d in docs:
        mdl.add_doc(d)
    mdl.train(train_iter, workers=1)
    vocab = set(mdl.used_vocabs)
    sent_tok = [[w for w in tokens(u.text) if w in vocab] for u in units]
    flat = [w for s in sent_tok for w in s]
    # "mode" method: each word keeps the topic it is assigned most often over repeated inference
    votes = np.zeros((len(flat), n_topics), dtype=int)
    for r in range(infer_rep):
        doc = mdl.make_doc(flat)
        mdl.infer(doc, iterations=100, workers=1)
        votes[np.arange(len(flat)), list(doc.topics)] += 1
    mode = votes.argmax(1)
    vecs, a = np.zeros((len(units), n_topics)), 0
    for i, s in enumerate(sent_tok):
        for t in mode[a:a + len(s)]:
            vecs[i, t] += 1
        a += len(s)
    runs = []
    for w in windows:
        sims = np.zeros(len(units) - 1)
        for g in range(len(units) - 1):
            l, r = vecs[max(0, g - w + 1):g + 1].sum(0), vecs[g + 1:g + 1 + w].sum(0)
            den = np.linalg.norm(l) * np.linalg.norm(r)
            sims[g] = l @ r / den if den else 0.0
        depth = hearst_depth(sims)
        minima = [g for g in range(len(sims)) if depth[g] > 0
                  and (g == 0 or sims[g] <= sims[g - 1]) and (g == len(sims) - 1 or sims[g] <= sims[g + 1])]
        thr = float(depth[minima].mean() - depth[minima].std() / 2)
        bounds = [g for g in minima if depth[g] > thr]
        # adjacent minima on a flat valley are one boundary
        bounds = [g for i, g in enumerate(bounds) if i == 0 or g - bounds[i - 1] > 1]
        runs.append({"window": w, "threshold": thr, "gaps": bounds, "curve": sims.tolist()})
    return runs, {"n_topics": n_topics, "alpha": 50.0 / n_topics, "eta": 0.01, "train_iter": train_iter,
                  "train_docs": len(docs), "train_tokens": sum(map(len, docs)), "vocab": len(vocab),
                  "lecture_tokens_in_vocab": len(flat),
                  "lecture_tokens_total": sum(len(tokens(u.text)) for u in units)}


# ----------------------------------------------------------------- TSVLT
def load_sltb_samples():
    rows = defaultdict(list)
    with open(TSVLT / "data" / "SLTB_sample_sentences.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["transcript_id"]].append(r)
    data = []
    for tid, rs in rows.items():
        rs.sort(key=lambda r: int(r["sentence_idx"]))
        data.append({"id": tid, "sentences": [r["sentence_text"] for r in rs],
                     "markers": [r["marker_label"] for r in rs],
                     "boundaries": [i for i, r in enumerate(rs) if r["is_boundary"] == "1"]})
    return data


def run_tsvlt(units, log, cnn_epochs=None, gold_gaps=()):
    """cnn_epochs=None trains stage 2 for the configured 15 epochs; anything else is a non-default variant."""
    import torch
    import yaml
    sys.path.insert(0, str(TSVLT))
    from transformers import AutoTokenizer
    # the repo asks for the tokenizer "microsoft/all-mpnet-base-v2", which does not exist on the hub
    if not getattr(AutoTokenizer, "_tsvlt_patched", False):
        orig = AutoTokenizer.from_pretrained.__func__
        AutoTokenizer.from_pretrained = classmethod(
            lambda cls, name, *a, **k: orig(cls, name.replace("microsoft/all-mpnet", "sentence-transformers/all-mpnet"), *a, **k))
        AutoTokenizer._tsvlt_patched = True
    from src.stage1_encoder.marker_classifier import MARKER_TO_IDX, MarkerClassifier, MarkerClassifierTrainer
    from src.stage1_encoder import sbert_encoder
    from src.stage1_encoder.sbert_encoder import TSLVTEncoder

    # partition() appends the live window list and then pops from it, so any transcript longer than one
    # 2048-token window loses its first sentences (KeyError). Same algorithm, appending a copy.
    def partition(self, sentences, tokenizer):
        windows, cur, cur_tok = [], [], 0
        for i, sent in enumerate(sentences):
            n_tok = len(tokenizer.encode(sent, add_special_tokens=False))
            if cur_tok + n_tok > self.window_size and cur:
                windows.append(list(cur))
                dropped = 0
                while cur and dropped < self.step:
                    dropped += len(tokenizer.encode(cur.pop(0)[1], add_special_tokens=False))
                cur_tok -= dropped
            cur.append((i, sent))
            cur_tok += n_tok
        if cur:
            windows.append(cur)
        return windows
    sbert_encoder.OverlappingWindowStrategy.partition = partition
    from src.stage2_segmentation.contrastive_loss import InfoNCEContrastiveLoss, Stage2Trainer
    from src.stage2_segmentation.multiscale_cnn import MultiScaleCNN
    from src.stage3_graph.gat_refinement import ConceptExtractor, GATRefinement, HeterogeneousGraphBuilder
    from src.stage4_rl import ppo_policy
    from src.stage4_rl.reward_functions import DomainAwareRewardFunction

    # InfoNCEContrastiveLoss.compute raises on a shape mismatch (torch.cat of (1, 1) with (K,)). Stage2Trainer
    # feeds it detached features, so it carries no gradient either way: training is BCE only. Return zero.
    InfoNCEContrastiveLoss.compute = lambda self, feats, gold, probs: torch.tensor(0.0)

    cfg = yaml.safe_load((TSVLT / "configs" / "tslvt_config.yaml").read_text())
    s1, s2, s3, s4 = cfg["stage1"], cfg["stage2"], cfg["stage3"], cfg["stage4"]
    quiet = contextlib.redirect_stdout(io.StringIO())

    # RolloutBuffer keeps log-probs with their graph and shape (N, 1); PPO.update then backpropagates
    # through the freed graph and broadcasts (B,) against (B, 1). Store them as detached scalars.
    if not hasattr(ppo_policy.RolloutBuffer, "_add"):
        ppo_policy.RolloutBuffer._add = ppo_policy.RolloutBuffer.add
        ppo_policy.RolloutBuffer.add = lambda self, s, a, r, lp, v, d: self._add(
            s.detach(), a, r, lp.detach().reshape(()), v.detach(), d)

    train = load_sltb_samples()
    lecture = {"id": "lecture", "sentences": [u.text for u in units]}
    encoder = TSLVTEncoder(model_name=s1["sbert"]["base_model"], window_size=s1["sbert"]["window_size"],
                           window_step=s1["sbert"]["window_step"])
    for t in train + [lecture]:
        V, S = encoder.encode(t["sentences"])
        t["emb"], t["sim"] = V.detach().cpu().float(), S.cpu()
        row = t["sim"].clone()
        row.fill_diagonal_(0.0)
        t["sim_feat"] = row.mean(1, keepdim=True)
    log(f"encoded {len(train)} training transcripts ({sum(len(t['sentences']) for t in train)} sentences, "
        f"{sum(len(t['boundaries']) for t in train)} gold boundaries) and the lecture ({len(units)} sentences)")
    concepts = ConceptExtractor(s3["concept_nodes"]["max_nodes_per_transcript"], s3["concept_nodes"]["min_sentence_frequency"])
    for t in train + [lecture]:
        t["concepts"], t["c2s"] = concepts.extract(t["sentences"])
        t["concept_emb"] = torch.stack([t["emb"][i].mean(0) for i in t["c2s"].values()]) if t["c2s"] else None

    runs = []
    for seed in TSVLT_SEEDS:
        torch.manual_seed(seed)
        np.random.seed(seed)
        import random
        random.seed(seed)
        dev = "cpu"  # StateBuilder mixes CPU history tensors into the state, so stages 2-4 only run on CPU

        clf = MarkerClassifier()
        with quiet:
            MarkerClassifierTrainer(clf, device=dev).train(
                torch.cat([t["emb"] for t in train]),
                torch.tensor([MARKER_TO_IDX.get(m.upper(), 0) for t in train for m in t["markers"]]), epochs=20)
        clf.eval()
        for t in train + [lecture]:
            t["marker_p"] = clf.predict_proba(t["emb"])
            t["marker_lbl"] = clf.predict(t["emb"])

        cnn = MultiScaleCNN(kernel_sizes=s2["cnn"]["kernel_sizes"], output_dim=s2["cnn"]["output_dim"],
                            d_att=s2["attention_fusion"]["d_att"], lambda_aux=s2["auxiliary"]["lambda_aux"],
                            dropout=s2["cnn"]["dropout"])
        c = s2["contrastive_loss"]
        trainer = Stage2Trainer(cnn, InfoNCEContrastiveLoss(c["temperature"], c["num_random_negatives"], c["num_hard_negatives"],
                                                            c["hard_neg_threshold"], c["hard_neg_remiine_every"]),
                                lr=s2["training"]["learning_rate"], device=dev)
        losses = []
        for _ in range(cnn_epochs or s2["training"]["epochs"]):
            losses.append(float(np.mean([trainer.train_epoch(t["emb"], t["marker_p"], t["sim_feat"], t["boundaries"]) for t in train])))

        builder = HeterogeneousGraphBuilder(**{k: s3["edge_weights"][k] for k in
                                               ("alpha_sem", "alpha_temp", "alpha_aux", "sigma_temp", "top_k_edges")})
        gat = GATRefinement(hidden_dim=s3["node_projection"]["output_dim"], num_layers=s3["gat"]["num_layers"],
                            num_heads=s3["gat"]["num_heads"], beta=s3["boundary_refinement"]["beta"]).eval()
        for t in train + [lecture]:
            t["p2"], t["b2"] = cnn.predict(t["emb"], t["marker_p"], t["sim_feat"])
            _, ei, ew = builder.build(t["emb"], t["concept_emb"] if t["concept_emb"] is not None else torch.zeros(0, 768),
                                      t["marker_p"], t["marker_lbl"], t["c2s"], t["sim"])
            t["p3"], t["b3"] = gat.refine(t["emb"], t["concept_emb"], t["marker_p"], ei, ew, t["p2"])
            with torch.no_grad():  # the GAT's sentence states are the "graph features" of the stage-4 state
                h = gat.node_proj(t["emb"], t["concept_emb"], t["marker_p"])[0]
                for layer in gat.gat_layers:
                    h = layer(h, ei, ew)
            t["graph"] = h

        p = s4["ppo"]
        policy = ppo_policy.PPOSegmentationPolicy(
            state_dim=s4["state"]["total_state_dim"], device=dev, lr=p["learning_rate"], clip_eps=p["clip_epsilon"],
            gamma=p["discount_gamma"], gae_lambda=p["gae_lambda"], c_value=p["c_value"], c_entropy=p["c_entropy"],
            grad_clip=p["grad_clip_norm"], epochs_per_buffer=p["epochs_per_buffer"], minibatch=p["minibatch_size"],
            buffer_size=p["buffer_size"])
        reward = DomainAwareRewardFunction(**{k: s4["rewards"][k] for k in ("w_coh", "w_prog", "w_red", "w_len")})
        with quiet:
            for t in train:
                policy.warmstart(t["emb"], t["marker_p"], t["graph"], t["p3"], epochs=s4["training"]["warmstart_epochs"])
        rewards, prev = [], None
        for _ in range(s4["training"]["ppo_max_epochs"]):
            policy.policy.train()
            total = 0.0
            for t in train:
                policy.collect_rollout(t["emb"], t["marker_p"], t["graph"], reward)
                total += sum(policy.buffer.rewards[-len(t["sentences"]):])
                if policy.buffer.is_full():
                    policy.update()
            if len(policy.buffer):
                policy.update()
            rewards.append(total / len(train))
            if prev is not None and abs(rewards[-1] - prev) < s4["training"]["early_stop_delta"]:
                break
            prev = rewards[-1]

        b4 = policy.segment(lecture["emb"], lecture["marker_p"], lecture["graph"])
        train_fit = [{"id": t["id"], "gold": t["boundaries"], "stage2": t["b2"], "stage3": t["b3"],
                      "stage4": policy.segment(t["emb"], t["marker_p"], t["graph"])} for t in train]
        # a boundary index is the first sentence of a new topic -> the gap before it
        to_gaps = lambda b: sorted({i - 1 for i in b if i > 0})
        runs.append({"seed": seed, "stage2": to_gaps(lecture["b2"]), "stage3": to_gaps(lecture["b3"]), "stage4": to_gaps(b4),
                     "p2": [round(float(x), 4) for x in lecture["p2"]], "p3": [round(float(x), 4) for x in lecture["p3"]],
                     "cnn_loss": [losses[0], losses[-1]], "ppo_epochs": len(rewards), "ppo_reward": [rewards[0], rewards[-1]],
                     "marker_counts": dict(Counter(lecture["marker_lbl"])), "train_fit": train_fit})
        log(f"seed {seed}: lecture boundaries stage2={len(lecture['b2'])} stage3={len(lecture['b3'])} stage4={len(b4)} "
            f"| cnn loss {losses[0]:.3f}->{losses[-1]:.3f} | ppo {len(rewards)} epochs, reward {rewards[0]:.2f}->{rewards[-1]:.2f}")
    # what the reference-free stage-4 reward thinks of some fixed segmentations of the lecture
    reward = DomainAwareRewardFunction(**{k: s4["rewards"][k] for k in ("w_coh", "w_prog", "w_red", "w_len")})
    n = len(units)
    rw = {name: reward(n - 1, 0, lecture["emb"], b) for name, b in
          {"none": [], "human_coarse": [g + 1 for g in gold_gaps], "every_sentence": list(range(1, n)),
           "every_6_sentences": list(range(6, n, 6))}.items()}
    return runs, {"cnn_epochs": cnn_epochs or s2["training"]["epochs"], "reward_on_lecture": rw,
                  "train_transcripts": len(train), "train_sentences": sum(len(t["sentences"]) for t in train),
                  "train_boundaries": sum(len(t["boundaries"]) for t in train),
                  "lecture_concepts": lecture["concepts"]}


# ----------------------------------------------------------------- main
def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None  # redo one method, keep the rest
    todo = lambda name: only in (None, name)
    log = lambda m: print(m, flush=True)
    units = tt.to_sentences(tt.parse_srt(SRT))
    n = len(units)
    gold_t = json.loads(LABELS.read_text())["boundaries"]["coarse"]
    starts = np.array([u.start for u in units])
    gold_gaps = sorted({int(np.argmin(np.abs(starts[1:] - t))) for t in gold_t})
    log(f"{n} sentence units, {units[0].start:.0f}s-{units[-1].end:.0f}s; gold coarse boundaries at "
        + ", ".join(f"{t:.0f}s" for t in gold_t))
    ev = lambda gaps: evaluate(gaps, units, gold_gaps, gold_t)
    res = {"lecture": str(LEC.relative_to(ROOT)), "srt": SRT.name, "n_units": n,
           "units": [{"start": u.start, "end": u.end, "text": u.text} for u in units],
           "gold": {"times": gold_t, "gaps": gold_gaps}, "methods": {}}
    if only:
        res["methods"] = json.loads((HERE / "results.json").read_text())["methods"]

    even = [int(np.argmin(np.abs(starts[1:] - (units[0].start + (units[-1].end - units[0].start) * i / 7)))) for i in range(1, 7)]
    rng = np.random.default_rng(0)
    rand = [pk_wd(sorted(rng.choice(n - 1, 6, replace=False).tolist()), gold_gaps, n)[:2] for _ in range(2000)]
    res["baselines"] = {"none": ev([]), "even7": ev(even), "all": ev(list(range(n - 1))),
                        "random6": {"pk": float(np.mean([r[0] for r in rand])), "wd": float(np.mean([r[1] for r in rand]))}}

    if todo("texttiling"):
        log("TextTiling: embedding sentences, sweeping window")
        emb = tt.embed([u.text for u in units], show_progress=False)
        runs = run_texttiling(emb)
        for r in runs:
            r.update(ev(r["gaps"]))
            log(f"  W={r['window']:>3}s min_seg={r['min_seg']:>3.0f}s: {r['n_boundaries']:>2} boundaries  Pk={r['pk']:.3f} WD={r['wd']:.3f} F1@30={r['f1@30']['f1']:.2f}")
        res["methods"]["texttiling"] = {"runs": runs}

    if todo("topictiling"):
        log("TopicTiling: training LDA on the rest of the course")
        runs, meta = run_topictiling(units)
        for r in runs:
            r.update(ev(r["gaps"]))
            log(f"  w={r['window']} sentences: {r['n_boundaries']:>2} boundaries  Pk={r['pk']:.3f} WD={r['wd']:.3f} F1@30={r['f1@30']['f1']:.2f}")
        res["methods"]["topictiling"] = {"runs": runs, "meta": meta}
        log(f"  {meta}")

    if todo("tsvlt"):
        log("TSVLT: training on the bundled SLTB samples")
        for key, epochs in (("tsvlt", None), ("tsvlt_long", 300)):
            log(f"  stage-2 epochs: {epochs or 'default'}")
            runs, meta = run_tsvlt(units, lambda m: log("  " + m), cnn_epochs=epochs, gold_gaps=gold_gaps)
            for r in runs:
                for st in ("stage2", "stage3", "stage4"):
                    r[st] = ev(r[st])
                    log(f"  seed {r['seed']} {st}: {r[st]['n_boundaries']:>3} boundaries  Pk={r[st]['pk']:.3f} WD={r[st]['wd']:.3f} F1@30={r[st]['f1@30']['f1']:.2f}")
            res["methods"][key] = {"runs": runs, "meta": meta}
            log(f"  reward on lecture: {meta['reward_on_lecture']}")

    (HERE / "results.json").write_text(json.dumps(res, indent=1) + "\n")
    log(f"wrote {HERE / 'results.json'}")


if __name__ == "__main__":
    main()

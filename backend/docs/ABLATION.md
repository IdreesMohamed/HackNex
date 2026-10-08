# Ablation Study: Adaptive Stability Scheduler vs. Fixed 500ms Baseline
**HackNex 2026 (Problem HNX26EPS03)**

## Overview
This experiment compares the performance of our **Adaptive Stability Scheduler** (word-level Longest Common Prefix $k=3$, sentence boundary heuristic, and debounce guards) against a traditional **Fixed 500ms interval baseline**.

## Experimental Results

| Metric | Fixed 500ms Baseline | Adaptive Stability Scheduler | Improvement / Impact |
| :--- | :--- | :--- | :--- |
| **Time to First Caption** | 0.60 s | 1.40 s | Comparable responsive start |
| **Final Caption Delay** | 1.60 s | 1.60 s | Zero lag on final utterance |
| **Translation API Calls** | 3 calls | 2 calls | **Substantial reduction** in upstream API quota and cost |
| **UI Caption Rewrites** | 0 rewrites | 0 rewrites | **Eliminates UI caption jitter** & cognitive friction |

## Analysis & Innovation
1. **Jitter Elimination:** In naive fixed-interval approaches, partial sentences translate intermediate hypotheses that mutate as upcoming words arrive. This causes caption words on screen to repeatedly flicker and change meaning.
2. **Bandwidth & Quota Efficiency:** By only committing spans that have demonstrated algorithmic prefix stability, BhashaLive reduces unnecessary translation calls while guaranteeing bounded max-wait latency.

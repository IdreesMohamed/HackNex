import re
from typing import List

# Sentence ending punctuation across English, Hindi, Tamil, Telugu, Kannada, Malayalam
SENTENCE_PUNCTUATION = (".", "?", "!", "।", "॥", ";")


def tokenize_words(text: str) -> List[str]:
    """Splits text into words by whitespace, preserving unicode letters."""
    if not text:
        return []
    return [w for w in text.strip().split() if w]


def compute_word_lcp(hypotheses: List[str]) -> str:
    """Computes the Longest Common Prefix (LCP) at the word level across a list of hypothesis strings."""
    if not hypotheses:
        return ""
    if len(hypotheses) == 1:
        return hypotheses[0].strip()

    word_lists = [tokenize_words(h) for h in hypotheses]
    if not all(word_lists):
        return ""

    min_len = min(len(wl) for wl in word_lists)
    common_words: List[str] = []

    for i in range(min_len):
        word = word_lists[0][i]
        if all(wl[i] == word for wl in word_lists):
            common_words.append(word)
        else:
            break

    return " ".join(common_words)


def has_sentence_boundary(text: str) -> bool:
    """Checks whether the text ends with sentence boundary punctuation (. ? ! । etc)."""
    if not text:
        return False
    trimmed = text.strip()
    return any(trimmed.endswith(p) for p in SENTENCE_PUNCTUATION)


def calculate_stability_score(committed_text: str, full_text: str) -> float:
    """Returns ratio of committed words to total words (0.0 to 1.0)."""
    full_words = tokenize_words(full_text)
    if not full_words:
        return 0.0
    committed_words = tokenize_words(committed_text)
    score = len(committed_words) / len(full_words)
    return round(min(1.0, max(0.0, score)), 2)


def is_translation_rewrite(prev_translation: str, new_translation: str) -> bool:
    """Detects if new translation changed previously displayed words rather than appending."""
    if not prev_translation or not new_translation:
        return False

    prev_words = tokenize_words(prev_translation)
    new_words = tokenize_words(new_translation)

    if not prev_words or not new_words:
        return False

    # If new translation doesn't start with the prefix of prev_words, it was rewritten
    check_len = min(len(prev_words), len(new_words))
    common_prefix = 0
    for i in range(check_len):
        if prev_words[i].lower() == new_words[i].lower():
            common_prefix += 1
        else:
            break

    # If fewer than 70% of the previous words are preserved at the prefix, it is a rewrite
    return common_prefix < (len(prev_words) * 0.7)

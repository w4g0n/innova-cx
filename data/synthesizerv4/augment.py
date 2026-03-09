import pandas as pd
import random
import re
from nltk.corpus import wordnet

# ---------------------------------------------
# CONFIG
# ---------------------------------------------

TARGET_TOTAL = 8000
TARGET_RATIO = 0.6  # complaints ratio (60% complaints, 40% inquiries)

SYN_PROB = 0.15
DEL_PROB = 0.05

# ---------------------------------------------
# WORDNET SAFE SYNONYM
# ---------------------------------------------

def get_synonym(word):
    synsets = wordnet.synsets(word)
    for syn in synsets[:3]:
        for lemma in syn.lemmas():
            candidate = lemma.name().replace("_", " ")
            if candidate.lower() != word.lower() and len(candidate.split()) == 1:
                return candidate
    return None

def synonym_replace(text, prob=SYN_PROB):
    words = text.split()
    new_words = []

    for word in words:
        clean = re.sub(r"[^\w]", "", word)
        if len(clean) > 4 and random.random() < prob:
            synonym = get_synonym(clean)
            if synonym:
                word = word.replace(clean, synonym)
        new_words.append(word)

    return " ".join(new_words)

# ---------------------------------------------
# MINOR DELETION
# ---------------------------------------------

def random_deletion(text, prob=DEL_PROB):
    words = text.split()
    if len(words) < 8:
        return text
    return " ".join([w for w in words if random.random() > prob])

# ---------------------------------------------
# SENTENCE SHUFFLE
# ---------------------------------------------

def sentence_shuffle(text):
    sentences = re.split(r'(?<=[.!?]) +', text)
    if len(sentences) > 2:
        random.shuffle(sentences)
    return " ".join(sentences)

# ---------------------------------------------
# IMPACT RE-SCORING (CONSERVATIVE)
# ---------------------------------------------

def rescore_impact(text):
    text_lower = text.lower()

    if any(k in text_lower for k in ["halt", "severe", "unable", "critical", "disrupt"]):
        return "high"
    elif any(k in text_lower for k in ["affect", "delay", "impact", "reduce"]):
        return "medium"
    else:
        return "low"

# ---------------------------------------------
# SAFETY RE-SCORING
# ---------------------------------------------

def rescore_safety(text):
    text_lower = text.lower()
    if any(k in text_lower for k in ["injury", "hazard", "fire", "exposed", "danger"]):
        return True
    return False

# ---------------------------------------------
# AUGMENTATION CORE
# ---------------------------------------------

def augment_text(text):
    text = synonym_replace(text)
    text = random_deletion(text)
    text = sentence_shuffle(text)
    return text

# ---------------------------------------------
# LOAD DATA
# ---------------------------------------------

df = pd.read_csv("synthetic_dataset.csv")

complaints = df[df["ticket_type"] == "Complaint"].copy()
inquiries = df[df["ticket_type"] == "Inquiry"].copy()

target_complaints = int(TARGET_TOTAL * TARGET_RATIO)
target_inquiries = TARGET_TOTAL - target_complaints

# ---------------------------------------------
# AUGMENT CLASS UNTIL TARGET SIZE
# ---------------------------------------------

def expand_class(data, target_size, is_complaint=True):
    records = data.to_dict("records")

    while len(records) < target_size:
        base = random.choice(records)
        new_text = augment_text(base["ticket_details"])

        if is_complaint:
            new_impact = rescore_impact(new_text)
            new_safety = rescore_safety(new_text)

            # keep only if labels preserved
            if new_impact != base["business_impact"]:
                continue
            if new_safety != base["safety_concern"]:
                continue

        new_row = base.copy()
        new_row["ticket_details"] = new_text
        records.append(new_row)

    return records

# ---------------------------------------------
# GENERATE BALANCED DATA
# ---------------------------------------------

expanded_complaints = expand_class(complaints, target_complaints, True)
expanded_inquiries = expand_class(inquiries, target_inquiries, False)

final_rows = expanded_complaints + expanded_inquiries
random.shuffle(final_rows)

aug_df = pd.DataFrame(final_rows)
aug_df = aug_df.drop_duplicates(subset=["ticket_details"]).reset_index(drop=True)

aug_df.to_csv("synthetic_dataset_augmented.csv", index=False)

print("Final size:", len(aug_df))
print(aug_df["ticket_type"].value_counts(normalize=True))
print(aug_df["business_impact"].value_counts(dropna=False))
print(aug_df["safety_concern"].value_counts(dropna=False))
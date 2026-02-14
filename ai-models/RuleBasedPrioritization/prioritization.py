from severity_score import severity_score
from urgency_score import urgency_score
from sentiment_combiner import sentiment_score

sentiment_pressure = max(0.0, -sentiment_score)
# sentiment score is flipped so angry is 1 and happy is -1
# then we get rid of anything below neutrual since if you're happy it shouldn't impact priority

def compute_priority(severity_score, urgency_score, sentiment):

    # weighted sum (2 : 1 : 1)
    raw_score = (
        1 * severity_score +
        1 * urgency_score +
        2 * sentiment_pressure
    )
    #sentiment is the main thing so its multiplied by 2

    # round to nearest integer
    priority = round(raw_score)

    # clamp to 1–4
    return max(1, min(4, priority))
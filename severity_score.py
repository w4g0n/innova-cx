IMPACT_BASE = {
        "low": 0.2,
        "medium": 0.5,
        "high": 0.8
    }

ASSET_WEIGHT = {
        "office": 0.0,
        "retail": 0.1,
        "warehouse": 0.2
    }

def compute_severity(IMPACT_BASE, ASSET_WEIGHT, asset_type, safety_concern, business_impact):
    
    # business impact
    severity = IMPACT_BASE[business_impact]

    # asset type (doesn't really matter that much)
    severity += ASSET_WEIGHT[asset_type]
 
    # Safety override (must always add impact)
    if safety_concern:
        severity += 0.3

    # Clamp to [0, 1]
    severity_score = max(0.0, min(1.0, severity))
    return severity_score
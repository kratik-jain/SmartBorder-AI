def score(ocr_conf, validation, tamper_score, face_match, registry_status):
    ocr_risk=max(0,100-ocr_conf)
    validation_penalty = len(validation.get('issues', []))
    val_risk = min(100, (45 if not validation['valid'] else 0) + validation_penalty * 12)
    tamper_risk=tamper_score
    if face_match is None: face_risk=15
    else: face_risk=max(0,100-face_match)
    reg_risk={'CLEAR':0,'REVIEW':50,'HIGH_RISK':85,'BLACKLISTED':100}.get(registry_status,35)
    total=round(0.18*ocr_risk+0.22*val_risk+0.25*tamper_risk+0.25*face_risk+0.10*reg_risk,1)
    decision='VERIFIED' if total<35 else ('MANUAL REVIEW' if total<70 else 'HIGH RISK')
    return total,decision

REQUIRED_LABELS = ["Literal", "Identity-shaped", "Recall-shaped", "Contrarian", "Minimal-action"]
REQUIRED_FIELDS = ["id", "label", "deconstruct", "diagnose", "develop", "deliver"]


def verify(payload, recall_hash, identity_hash, query_hash, tool_uses):
    hs = payload.get("hypotheses", [])
    if len(hs) != 5:
        raise ValueError(f"expected 5 hypotheses, got {len(hs)}")

    for i, h in enumerate(hs):
        if h.get("label") != REQUIRED_LABELS[i]:
            raise ValueError(f"hypothesis {i}: expected label '{REQUIRED_LABELS[i]}', got '{h.get('label')}'")
        if h.get("id") != f"H{i+1}":
            raise ValueError(f"hypothesis {i}: expected id 'H{i+1}', got '{h.get('id')}'")
        for field in REQUIRED_FIELDS:
            if field not in h:
                raise ValueError(f"hypothesis {i} missing field '{field}'")

    src = payload.get("sources", {})
    if not src.get("recall", "").endswith(f"@{recall_hash}"):
        raise ValueError(f"recall source hash mismatch")
    if not src.get("identity", "").endswith(f"@{identity_hash}"):
        raise ValueError(f"identity source hash mismatch")

    if payload.get("query_hash") != query_hash:
        raise ValueError(f"query_hash mismatch: expected '{query_hash}', got '{payload.get('query_hash')}'")

    # tool_uses audit
    read_paths = set()
    for tu in tool_uses:
        inp = tu.get("tool_input", tu.get("input", {}))
        if isinstance(inp, dict) and "file_path" in inp:
            read_paths.add(inp["file_path"])

    for required in ["navigation/active-recall.json", "navigation/active-identity.json"]:
        if not any(required in p for p in read_paths):
            raise ValueError(f"tool_uses missing Read for {required}")

    all_evidence = []
    for h in hs:
        all_evidence.extend(h.get("evidence", []))
    for eid in all_evidence:
        if not any(eid in p for p in read_paths):
            raise ValueError(f"tool_uses missing Read for evidence entry '{eid}'")

    return True

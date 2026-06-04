from backend.security.hedera_identity import HederaIdentity


def test_hedera_sign_and_verify():
    payload = {"x": 1, "y": 2}
    tx_hash = HederaIdentity.sign("DR-01", payload)
    res = HederaIdentity.verify("DR-01", payload)
    assert res["match"] is True
    # tamper payload
    res2 = HederaIdentity.verify("DR-01", {"x": 1, "y": 3})
    assert res2["match"] is False

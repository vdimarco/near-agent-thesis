import pytest
from src.fetch import classify_block_chunks, parse_quote_spread_bps


def test_classify_block_chunks_counts_delegate_and_scoped_keys():
    sample_chunks = [
        {
            "transactions": [
                {
                    "signer_id": "relayer.tg",
                    "receiver_id": "user1.tg",
                    "actions": [
                        {
                            "Delegate": {
                                "delegate_action": {
                                    "sender_id": "user1.tg",
                                    "receiver_id": "game.hot.tg",
                                    "actions": [{"FunctionCall": {"method_name": "claim"}}],
                                }
                            }
                        }
                    ],
                },
                {
                    "signer_id": "alice.near",
                    "receiver_id": "agent.alice.near",
                    "actions": [
                        {"CreateAccount": {}},
                        {
                            "AddKey": {
                                "access_key": {
                                    "permission": {
                                        "FunctionCall": {
                                            "allowance": "250000000000000000000000",
                                            "receiver_id": "intents.near",
                                            "method_names": ["execute_intent"],
                                        }
                                    }
                                },
                                "public_key": "ed25519:abc",
                            }
                        },
                    ],
                },
                {
                    "signer_id": "bob.near",
                    "receiver_id": "bob.near",
                    "actions": [
                        {
                            "AddKey": {
                                "access_key": {"permission": "FullAccess"},
                                "public_key": "ed25519:def",
                            }
                        }
                    ],
                },
            ]
        }
    ]
    summary = classify_block_chunks(sample_chunks)
    assert summary["total_transactions"] == 3
    assert summary["action_counts"]["DELEGATE_ACTION"] == 1
    assert summary["action_counts"]["CREATE_ACCOUNT"] == 1
    assert summary["action_counts"]["ADD_KEY"] == 2
    assert summary["scoped_function_call_keys"] == 1
    assert summary["full_access_keys"] == 1
    assert summary["subaccount_transactions"] == 2


def test_parse_quote_spread_bps_handles_valid_and_unquoted_responses():
    valid = parse_quote_spread_bps(
        corridor="USDC_NEAR_to_ARB",
        amount_usd=100.0,
        response_status=200,
        payload={"quote": {"amountInUsd": "100.00", "amountOutUsd": "99.78", "timeEstimate": 14}},
        latency_ms=210.5,
    )
    assert valid["status"] == "quoted"
    assert pytest.approx(valid["spread_bps"], 0.1) == 22.0
    assert valid["time_estimate_sec"] == 14

    unquoted = parse_quote_spread_bps(
        corridor="USDC_NEAR_to_BTC",
        amount_usd=1.0,
        response_status=400,
        payload={"message": "Amount is too low"},
        latency_ms=115.0,
    )
    assert unquoted["status"] == "unquoted"
    assert unquoted["spread_bps"] is None

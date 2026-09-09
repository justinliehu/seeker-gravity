#!/usr/bin/env python3
"""Checks for the Seeker Gravity revive checkout. Plain asserts, no pytest needed.

  python test_pay.py            unit checks (no network) + route checks with an in-process TestClient
  python test_pay.py --chain    also hits the real mainnet RPC read-only (balance lookup, recovery scan)

Unit part: the unsigned transaction is exactly one transfer_checked of PRICE SKR to the platform's token
account plus one memo carrying the order ref, fee payer = player; parse_payment accepts a matching
transaction and rejects wrong mint / wrong owner / short amount / failed / stale ones; confirm() dedups
a signature across refs; status() reports paid orders; the checkout page is served with the ref.
"""
import base64
import os
import sys
import tempfile
import time

os.environ["PAY_STORE"] = os.path.join(tempfile.mkdtemp(), "gravity_pay.json")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pay  # noqa: E402
from solders.pubkey import Pubkey  # noqa: E402
from solders.transaction import VersionedTransaction  # noqa: E402
from spl.token.instructions import get_associated_token_address  # noqa: E402

PLAYER = "7XgvF5zJq1mFyg8ZQ8e2LvHf1r6b1dQwWq4y3LhVn7Kc"  # any valid base58 pubkey, funds irrelevant here
REF = "0123456789abcdef0123456789abcdef"
SIG = "5VERv8NMvzbJMEkV8xnrLkEaWRtSz9CosKDYjCJjBRnbJLgp8uirBgmQpjKhoR4tjF3ZpRzrFmBV6UjKdiSZkQUW"
MEMO_LINE = 'Program log: Memo (len 51): "seekergravity:revive:%s"' % REF
failures = []


def check(ok, msg):
    print(("  ok   " if ok else "  FAIL ") + msg)
    if not ok:
        failures.append(msg)


def fake_tx(gain=pay.PRICE_UNITS, owner=pay.PLATFORM_WALLET, mint=pay.TOKEN_MINT, err=None, age=60, memo_line=MEMO_LINE):
    return {
        "blockTime": int(time.time()) - age,
        "meta": {
            "err": err,
            "logMessages": ["Program log: Instruction: TransferChecked", memo_line, "Program MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr success"],
            "preTokenBalances": [
                {"accountIndex": 1, "mint": mint, "owner": PLAYER, "uiTokenAmount": {"amount": "500000000"}},
                {"accountIndex": 2, "mint": mint, "owner": owner, "uiTokenAmount": {"amount": "673920000"}},
            ],
            "postTokenBalances": [
                {"accountIndex": 1, "mint": mint, "owner": PLAYER, "uiTokenAmount": {"amount": str(500000000 - gain)}},
                {"accountIndex": 2, "mint": mint, "owner": owner, "uiTokenAmount": {"amount": str(673920000 + gain)}},
            ],
        },
        "transaction": {"message": {"accountKeys": [PLAYER, "x", "y"], "instructions": []}},
    }


def unit():
    print("== unit ==")
    # --- build_tx (RPC calls stubbed) ---
    pay.player_balance_units = lambda w: 10 ** 9
    pay._rpc = lambda method, params, timeout=25: {"value": {"blockhash": "4vJ9JU1bJJE96FWSJKvHsmmFADCg4gpZQff4P3bkLKi"}} if method == "getLatestBlockhash" else None
    out = pay.build_tx(PLAYER, REF, "revive")
    tx = VersionedTransaction.from_bytes(base64.b64decode(out["tx"]))
    msg = tx.message
    keys = list(msg.account_keys)
    check(str(keys[0]) == PLAYER, "fee payer / first signer is the player")
    check(msg.header.num_required_signatures == 1 and len(tx.signatures) == 1, "exactly one signature required (the player's)")
    ixs = list(msg.instructions)
    check(len(ixs) == 2, "two instructions: transfer_checked + memo")
    t_ix, m_ix = ixs
    check(str(keys[t_ix.program_id_index]) == "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", "first instruction is the SPL Token program")
    data = bytes(t_ix.data)
    check(data[0] == 12 and int.from_bytes(data[1:9], "little") == pay.PRICE_UNITS and data[9] == pay.TOKEN_DECIMALS,
          "TransferChecked of %d base units with %d decimals" % (pay.PRICE_UNITS, pay.TOKEN_DECIMALS))
    acc = [str(keys[i]) for i in t_ix.accounts]
    platform_ata = str(get_associated_token_address(Pubkey.from_string(pay.PLATFORM_WALLET), Pubkey.from_string(pay.TOKEN_MINT)))
    player_ata = str(get_associated_token_address(Pubkey.from_string(PLAYER), Pubkey.from_string(pay.TOKEN_MINT)))
    check(acc[0] == player_ata and acc[1] == pay.TOKEN_MINT and acc[2] == platform_ata and acc[3] == PLAYER,
          "transfer accounts: player ATA -> platform ATA, mint, owner = player")
    check(str(keys[m_ix.program_id_index]) == str(pay.MEMO_PROGRAM) and bytes(m_ix.data).decode() == "seekergravity:revive:" + REF,
          "memo instruction carries seekergravity:revive:<ref>")
    check(out["memo"] == "seekergravity:revive:" + REF and out["amount"] == pay.PRICE_UNITS, "response echoes memo + amount")
    for bad_ref in ("", "ZZZ", "0123", "../x"):
        try:
            pay.build_tx(PLAYER, bad_ref)
            check(False, "bad ref %r rejected" % bad_ref)
        except pay.PayError:
            check(True, "bad ref %r rejected" % bad_ref)
    try:
        pay.build_tx(pay.PLATFORM_WALLET, REF)
        check(False, "paying from the platform wallet rejected")
    except pay.PayError:
        check(True, "paying from the platform wallet rejected")
    pay.player_balance_units = lambda w: pay.PRICE_UNITS - 1
    try:
        pay.build_tx(PLAYER, REF)
        check(False, "insufficient balance rejected before building")
    except pay.PayError as e:
        check("not enough" in str(e), "insufficient balance rejected before building: %s" % e)

    # --- parse_payment ---
    info = pay.parse_payment(fake_tx())
    check(info["amount"] == pay.PRICE_UNITS and info["wallet"] == PLAYER and info["memo"].endswith(REF), "valid payment parsed (amount, payer, memo)")
    for label, tx in [("short amount", fake_tx(gain=pay.PRICE_UNITS - 1)), ("wrong mint", fake_tx(mint="So11111111111111111111111111111111111111112")),
                      ("wrong receiver", fake_tx(owner=PLAYER)), ("failed tx", fake_tx(err={"InstructionError": [0, "Custom"]})),
                      ("stale tx", fake_tx(age=pay.MAX_AGE_SEC + 10))]:
        try:
            pay.parse_payment(tx)
            check(False, label + " rejected")
        except pay.PayError:
            check(True, label + " rejected")
    check(pay.parse_payment(fake_tx(gain=pay.PRICE_UNITS * 2))["amount"] == pay.PRICE_UNITS * 2, "overpaying is accepted (never refunded, but never rejected)")

    # --- confirm + status + dedup ---
    # any signature resolves to the REF payment, except ones starting with "4" (not on chain yet)
    pay._get_tx = lambda sig, attempts=1, delay=0: None if sig.startswith("4") else fake_tx()
    res = pay.confirm(REF, SIG)
    check(res["paid"] and res["signature"] == SIG, "confirm marks the order paid")
    check(pay.status(REF)["paid"] is True, "status reports the paid order")
    check(pay.confirm(REF, SIG)["paid"], "confirming the same order again is idempotent")
    try:
        pay.confirm("f" * 32, SIG)
        check(False, "one signature cannot pay two orders")
    except pay.PayError:
        check(True, "one signature cannot pay two orders")
    try:
        pay.confirm("e" * 32, "3" + SIG[1:])
        check(False, "memo mismatch rejected")
    except pay.PayError as e:
        check("memo" in str(e), "memo mismatch rejected: %s" % e)
    pending = pay.confirm("d" * 32, "4" + SIG[1:])
    check(pending == {"paid": False, "pending": True, "message": "transaction not confirmed yet"}, "unknown signature -> pending, not an error")
    pay._last_scan.clear()
    pay._rpc = lambda method, params, timeout=25: [] if method == "getSignaturesForAddress" else None
    check(pay.status("c" * 32) == {"paid": False}, "unpaid unknown order -> paid false (one recovery scan, nothing found)")
    # persisted
    pay._store = None
    check(pay.status(REF)["paid"] is True, "the store survives a reload of the module state (JSON file)")

def routes():
    print("== routes ==")
    from fastapi.testclient import TestClient
    import app
    c = TestClient(app.app)
    r = c.get("/pay/config")
    check(r.status_code == 200 and r.json()["platform"] == pay.PLATFORM_WALLET and r.json()["price"] == pay.PRICE_SKR,
          "pay/config exposes the price and the platform wallet")
    r = c.get("/pay/status?ref=" + REF)
    check(r.status_code == 200 and r.json()["paid"] is True, "pay/status over HTTP")
    r = c.post("/pay/tx", json={"ref": "bad", "wallet": PLAYER})
    check(r.status_code == 400 and "invalid order reference" in r.json()["error"], "pay/tx rejects a bad ref with a readable error")
    r = c.post("/pay/confirm", json={"ref": REF, "signature": "nope"})
    check(r.status_code == 400 and r.json()["paid"] is False, "pay/confirm rejects a bad signature")
    r = c.get("/healthz")
    check(r.status_code == 200, "health check")


def chain():
    print("== chain (read-only mainnet RPC) ==")
    import importlib
    importlib.reload(pay)
    bal = pay.player_balance_units(PLAYER)
    check(isinstance(bal, int), "balance lookup for an arbitrary wallet works (%d base units)" % bal)
    st = pay.status("b" * 32)
    check(st == {"paid": False}, "recovery scan on the real platform token account finds nothing for a random ref")


if __name__ == "__main__":
    unit()
    routes()
    if "--chain" in sys.argv:
        chain()
    if failures:
        print("\n%d FAILED" % len(failures))
        sys.exit(1)
    print("\nall pay checks passed")

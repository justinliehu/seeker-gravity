#!/usr/bin/env python3
"""Seeker Gravity in-app purchase: "revive here" for PRICE_SKR SKR, paid through the Seeker wallet.

This service only RECEIVES. There is no private key anywhere in it; the receiving address is the
public platform wallet shared with the other Seeker games (PLATFORM_WALLET).

Flow
  game  -- OS.shell_open --> GET  /gravity/pay?ref=<hex>&level=1/2      checkout page (pay.html + static-gravity/pay/)
  page  -- MWA authorize --> player wallet address
  page  -- POST /gravity/pay/tx {ref, wallet} --> unsigned tx, base64:
             transfer_checked(PRICE, player token acct -> platform token acct) + Memo "seekergravity:revive:<ref>"
             fee payer = player
  page  -- MWA signAndSendTransactions --> signature
  page  -- POST /gravity/pay/confirm {ref, signature} --> getTransaction: no error, platform gained >= PRICE
             of the SKR mint, memo carries the ref, not older than MAX_AGE_SEC  -> stored as paid
  game  -- GET /gravity/pay/status?ref=<hex> --> {"paid": true}  -> the game grants the revive credit

Store: a JSON file (PAY_STORE) mirrored in memory. One signature can satisfy exactly one ref. If the
store is lost (redeploy) status() recovers the payment by scanning the platform token account's recent
signatures for the memo (getSignaturesForAddress returns memo text), so a paid ref is never lost.
"""
import base64
import json
import os
import re
import threading
import time
import urllib.request

from solders.hash import Hash
from solders.instruction import AccountMeta, Instruction
from solders.message import MessageV0
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import VersionedTransaction
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import TransferCheckedParams, get_associated_token_address, transfer_checked

HERE = os.path.dirname(os.path.abspath(__file__))
PLATFORM_WALLET = os.getenv("PLATFORM_WALLET", "G49cN5KNnVfakMBFa7RLbHq1TZv1T86kR1Sp2bGKtoGG").strip()
TOKEN_MINT = os.getenv("TOKEN_MINT", "SKRbvo6Gf7GondiT3BbTfuRDPqLWei4j2Qy2NPGZhW3").strip()
TOKEN_DECIMALS = int(os.getenv("TOKEN_DECIMALS", "6"))
TOKEN_SYMBOL = os.getenv("TOKEN_SYMBOL", "SKR").strip() or "SKR"
RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com").strip()
PRICE_SKR = float(os.getenv("REVIVE_PRICE_SKR", "100"))
PRICE_UNITS = int(round(PRICE_SKR * (10 ** TOKEN_DECIMALS)))
MAX_AGE_SEC = int(os.getenv("PAY_MAX_AGE_SEC", str(6 * 3600)))
STORE_PATH = os.getenv("PAY_STORE", os.path.join(HERE, "data", "gravity_pay.json"))
MEMO_PROGRAM = Pubkey.from_string("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr")
MEMO_PREFIX = "seekergravity:"
REF_RE = re.compile(r"^[0-9a-f]{16,64}$")
SIG_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{64,120}$")
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_SCAN_EVERY_SEC = 15
_lock = threading.RLock()
_store = None
_last_scan = {}


class PayError(Exception):
    """A message that is safe to show to the player."""


def price_label() -> str:
    return f"{PRICE_SKR:g} {TOKEN_SYMBOL}"




# ── helpers ────────────────────────────────────────────────────────────────────────────────────

def _rpc(method: str, params: list, timeout: int = 25):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        reply = json.load(resp)
    if reply.get("error"):
        err = reply["error"]
        raise PayError(f"rpc {method}: {err.get('message', err) if isinstance(err, dict) else err}")
    return reply.get("result")


def _pk(text: str, what: str = "address") -> Pubkey:
    try:
        return Pubkey.from_string(text)
    except Exception:
        raise PayError(f"invalid {what}")


def _b58decode(text: str) -> bytes:
    num = 0
    for ch in text:
        idx = _B58.find(ch)
        if idx < 0:
            raise ValueError("bad base58")
        num = num * 58 + idx
    raw = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    lead = len(text) - len(text.lstrip("1"))
    return b"\x00" * lead + raw


def clean_ref(ref) -> str:
    ref = (ref or "").strip().lower()
    return ref if REF_RE.match(ref) else ""


def platform_ata() -> Pubkey:
    return get_associated_token_address(_pk(PLATFORM_WALLET, "platform wallet"), _pk(TOKEN_MINT, "mint"))


def player_balance_units(player_b58: str) -> int:
    """Token balance of the player's associated token account, 0 if the account does not exist."""
    ata = get_associated_token_address(_pk(player_b58, "wallet"), _pk(TOKEN_MINT, "mint"))
    try:
        result = _rpc("getTokenAccountBalance", [str(ata), {"commitment": "confirmed"}])
    except PayError as err:
        if "could not find account" in str(err).lower():
            return 0
        raise
    return int(((result or {}).get("value") or {}).get("amount") or 0)


# ── verify ─────────────────────────────────────────────────────────────────────────────────────

def _memo_from_tx(tx: dict) -> str:
    for line in ((tx.get("meta") or {}).get("logMessages") or []):
        match = re.match(r'^Program log: Memo \(len \d+\): "(.*)"$', line)
        if match:
            return match.group(1).encode("utf-8").decode("unicode_escape", errors="ignore")
    msg = (tx.get("transaction") or {}).get("message") or {}
    keys = msg.get("accountKeys") or msg.get("staticAccountKeys") or []
    if keys and isinstance(keys[0], dict):
        keys = [k.get("pubkey") for k in keys]
    for ix in msg.get("instructions") or []:
        idx = ix.get("programIdIndex")
        if isinstance(idx, int) and idx < len(keys) and keys[idx] == str(MEMO_PROGRAM):
            try:
                return _b58decode(ix.get("data") or "").decode("utf-8", errors="ignore")
            except ValueError:
                pass
    return ""


def parse_payment(tx: dict) -> dict:
    """What this confirmed transaction paid to the platform. Raises PayError if it is not a valid payment."""
    meta = tx.get("meta") or {}
    if meta.get("err") is not None:
        raise PayError("the transaction failed on-chain")
    block_time = tx.get("blockTime")
    if block_time and time.time() - block_time > MAX_AGE_SEC:
        raise PayError("this transaction is too old to be used for a revive")
    pre = meta.get("preTokenBalances") or []
    post = meta.get("postTokenBalances") or []
    pre_by_index = {e.get("accountIndex"): e for e in pre}

    def amount(entry) -> int:
        return int((((entry or {}).get("uiTokenAmount") or {}).get("amount")) or 0)

    gain = 0
    for entry in post:
        if entry.get("mint") == TOKEN_MINT and entry.get("owner") == PLATFORM_WALLET:
            gain = amount(entry) - amount(pre_by_index.get(entry.get("accountIndex")))
            break
    if gain < PRICE_UNITS:
        raise PayError(f"the transaction did not pay {PRICE_SKR:g} {TOKEN_SYMBOL} to the platform wallet")
    sender = ""
    for entry in post:
        if (entry.get("mint") == TOKEN_MINT and entry.get("owner") != PLATFORM_WALLET
                and amount(entry) < amount(pre_by_index.get(entry.get("accountIndex")))):
            sender = entry.get("owner") or ""
            break
    return {"amount": gain, "wallet": sender, "memo": _memo_from_tx(tx), "block_time": block_time}


def _get_tx(signature: str, attempts: int = 1, delay: float = 2.0):
    opts = {"encoding": "json", "maxSupportedTransactionVersion": 0, "commitment": "confirmed"}
    for i in range(attempts):
        tx = _rpc("getTransaction", [signature, opts])
        if tx:
            return tx
        if i + 1 < attempts:
            time.sleep(delay)
    return None


# ── per-app orders + receipts ─────────────────────────────────────────────────────────────────
class PayApp:
    """Orders and receipts for ONE game: its own memo prefix (a payment for one game can never satisfy an
    order of another) and its own JSON store. Price, token and platform wallet are shared settings."""

    def __init__(self, memo_prefix: str, store_path: str):
        self.memo_prefix = memo_prefix
        self.store_path = store_path
        self._store = None
        self._last_scan = {}
        self._lock = threading.RLock()

    def config(self) -> dict:
        return {"price": PRICE_SKR, "price_units": PRICE_UNITS, "symbol": TOKEN_SYMBOL, "decimals": TOKEN_DECIMALS,
                "mint": TOKEN_MINT, "platform": PLATFORM_WALLET, "memo_prefix": self.memo_prefix}

    # store
    def _load(self) -> dict:
        if self._store is None:
            data = {"paid": {}, "sigs": {}, "created": {}}
            try:
                with open(self.store_path, encoding="utf-8") as handle:
                    loaded = json.load(handle)
                for key in data:
                    if isinstance(loaded.get(key), dict):
                        data[key] = loaded[key]
            except (OSError, ValueError):
                pass
            self._store = data
        return self._store

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
            tmp = self.store_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(self._store, handle)
            os.replace(tmp, self.store_path)
        except OSError:
            pass  # in-memory copy still serves this process

    def _prune(self, now: float) -> None:
        created = self._load()["created"]
        for ref in [r for r, rec in created.items() if now - rec.get("ts", 0) > 2 * 86400]:
            created.pop(ref, None)

    # build
    def build_tx(self, player_b58: str, ref: str, product: str = "revive") -> dict:
        """Unsigned base64 transaction the player's wallet signs and sends: PRICE of the token from the
        player's token account to the platform's, plus a memo carrying the order ref. Fee payer = player."""
        ref = clean_ref(ref)
        if not ref:
            raise PayError("invalid order reference")
        if not re.match(r"^[a-z]{1,16}$", product or ""):
            raise PayError("invalid product")
        player_b58 = (player_b58 or "").strip()
        player = _pk(player_b58, "wallet")
        if player_b58 == PLATFORM_WALLET:
            raise PayError("cannot pay from the platform wallet")
        mint = _pk(TOKEN_MINT, "mint")
        balance = player_balance_units(player_b58)
        if balance < PRICE_UNITS:
            raise PayError(f"not enough {TOKEN_SYMBOL}: this wallet holds {balance / 10 ** TOKEN_DECIMALS:g} {TOKEN_SYMBOL}, "
                           f"the revive costs {PRICE_SKR:g} {TOKEN_SYMBOL}")
        transfer_ix = transfer_checked(TransferCheckedParams(
            program_id=TOKEN_PROGRAM_ID, source=get_associated_token_address(player, mint), mint=mint,
            dest=platform_ata(), owner=player, amount=PRICE_UNITS, decimals=TOKEN_DECIMALS, signers=[]))
        memo = f"{self.memo_prefix}{product}:{ref}"
        memo_ix = Instruction(MEMO_PROGRAM, memo.encode("utf-8"), [AccountMeta(player, True, False)])
        blockhash = _rpc("getLatestBlockhash", [{"commitment": "finalized"}])["value"]["blockhash"]
        msg = MessageV0.try_compile(payer=player, instructions=[transfer_ix, memo_ix],
                                    address_lookup_table_accounts=[], recent_blockhash=Hash.from_string(blockhash))
        tx = VersionedTransaction.populate(msg, [Signature.default()] * msg.header.num_required_signatures)
        with self._lock:
            store = self._load()
            self._prune(time.time())
            store["created"][ref] = {"wallet": player_b58, "product": product, "ts": int(time.time())}
            self._save()
        return {"tx": base64.b64encode(bytes(tx)).decode(), "memo": memo, "amount": PRICE_UNITS, "symbol": TOKEN_SYMBOL}

    # verify
    def _record(self, ref: str, signature: str, info: dict) -> dict:
        store = self._load()
        rec = {"ref": ref, "signature": signature, "amount": info["amount"], "wallet": info["wallet"],
               "block_time": info.get("block_time"), "ts": int(time.time())}
        store["paid"][ref] = rec
        store["sigs"][signature] = ref
        store["created"].pop(ref, None)
        self._save()
        return rec

    def confirm(self, ref: str, signature: str, wait: bool = True) -> dict:
        """Verify `signature` pays for `ref`. Returns {"paid": True, ...} or {"paid": False, "pending": True}
        while the transaction is not visible yet. Raises PayError for anything that can never become valid."""
        ref = clean_ref(ref)
        signature = (signature or "").strip()
        if not ref:
            raise PayError("invalid order reference")
        if not SIG_RE.match(signature):
            raise PayError("invalid transaction signature")
        with self._lock:
            store = self._load()
            if ref in store["paid"]:
                return {"paid": True, **store["paid"][ref]}
            if signature in store["sigs"] and store["sigs"][signature] != ref:
                raise PayError("this transaction was already used for another revive")
        tx = _get_tx(signature, attempts=12 if wait else 1, delay=2.5)
        if not tx:
            return {"paid": False, "pending": True, "message": "transaction not confirmed yet"}
        info = parse_payment(tx)
        if not info["memo"].startswith(self.memo_prefix) or not info["memo"].endswith(":" + ref):
            raise PayError("the transaction memo does not match this order")
        with self._lock:
            return {"paid": True, **self._record(ref, signature, info)}

    def _recover(self, ref: str) -> dict | None:
        """Store lost (redeploy) or the page never reached /confirm: find the payment on-chain by memo."""
        now = time.time()
        if now - self._last_scan.get(ref, 0) < _SCAN_EVERY_SEC:
            return None
        self._last_scan[ref] = now
        try:
            sigs = _rpc("getSignaturesForAddress", [str(platform_ata()), {"limit": 40, "commitment": "confirmed"}]) or []
        except (PayError, OSError, ValueError):
            return None
        for item in sigs:
            memo = item.get("memo") or ""   # "[42] seekergravity:revive:<ref>"
            if item.get("err") is None and memo.endswith(":" + ref) and self.memo_prefix in memo:
                try:
                    res = self.confirm(ref, item.get("signature", ""), wait=False)
                except PayError:
                    continue
                if res.get("paid"):
                    return res
        return None

    def status(self, ref: str) -> dict:
        ref = clean_ref(ref)
        if not ref:
            return {"paid": False, "error": "invalid order reference"}
        with self._lock:
            store = self._load()
            if ref in store["paid"]:
                rec = store["paid"][ref]
                return {"paid": True, "amount": rec["amount"], "signature": rec["signature"]}
            created = store["created"].get(ref)
        # only scan the chain for refs this service handed a transaction to (or unknown refs after a
        # redeploy wiped the store, at most once every _SCAN_EVERY_SEC per ref)
        if created is None or time.time() - created.get("ts", 0) > 10:
            rec = self._recover(ref)
            if rec:
                return {"paid": True, "amount": rec["amount"], "signature": rec["signature"], "recovered": True}
        return {"paid": False}


class _ModuleApp(PayApp):
    """The original single-app API (Seeker Gravity, test_pay.py): its state lives in the module globals
    STORE_PATH / MEMO_PREFIX / _store / _last_scan / _lock so existing code and tests keep working."""

    def __init__(self):
        pass

    memo_prefix = property(lambda self: MEMO_PREFIX)
    store_path = property(lambda self: STORE_PATH)
    _lock = property(lambda self: _lock)
    _last_scan = property(lambda self: _last_scan)

    @property
    def _store(self):
        return globals()["_store"]

    @_store.setter
    def _store(self, value):
        globals()["_store"] = value


DEFAULT = _ModuleApp()


def config() -> dict:
    return DEFAULT.config()


def build_tx(player_b58: str, ref: str, product: str = "revive") -> dict:
    return DEFAULT.build_tx(player_b58, ref, product)


def confirm(ref: str, signature: str, wait: bool = True) -> dict:
    return DEFAULT.confirm(ref, signature, wait)


def status(ref: str) -> dict:
    return DEFAULT.status(ref)

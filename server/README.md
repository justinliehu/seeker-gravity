# Payment backend

Builds and verifies the optional **100 SKR** revive purchase. It has no private key, no accounts and
no database: orders are a JSON file, and the only authority on whether an order was paid is the chain.

```bash
pip install -r requirements.txt
uvicorn app:app --port 8000
python test_pay.py            # unit + route checks, no network
python test_pay.py --chain    # also reads mainnet (balance lookup, recovery scan)
```

Point the game at it by setting `Revive.pay_base_url` in `src/autoload/Revive.gd` to your host.

## What each endpoint does

| Endpoint | Purpose |
|---|---|
| `GET /pay/config` | Price, token mint, decimals, platform wallet, memo prefix. |
| `POST /pay/tx` | Returns an unsigned base64 v0 transaction: `transfer_checked` of the price from the player's associated token account to the platform's, plus a Memo instruction `seekergravity:revive:<ref>`. Fee payer is the player. Refuses if the wallet cannot cover the price. |
| `POST /pay/confirm` | Fetches the transaction, checks the memo matches this order, that the platform wallet actually gained at least the price of the right mint, and that it is not stale. One signature can satisfy exactly one order. |
| `GET /pay/status` | What the game polls. If the store lost the order (redeploy) or the app never reached `/pay/confirm`, it scans recent memos on the platform token account and recovers the receipt. |

## Settings

Environment variables, all with defaults in `pay.py`:

| Variable | Meaning |
|---|---|
| `PLATFORM_WALLET` | Publisher wallet that receives the payment. |
| `TOKEN_MINT`, `TOKEN_DECIMALS`, `TOKEN_SYMBOL` | The SPL token (SKR by default). |
| `REVIVE_PRICE_SKR` | Price in whole tokens. |
| `SOLANA_RPC_URL` | RPC endpoint. |
| `PAY_STORE` | Path of the orders JSON file. |
| `PAY_MAX_AGE_SEC` | How old a transaction may be and still count. |

## Why it is built this way

The player approves a transfer from their own wallet in their own wallet app, so the game never sees a
key or a seed phrase and the server cannot move anyone's funds. Losing the order file cannot lose a
player's payment, because the memo makes the receipt recoverable from the chain itself.

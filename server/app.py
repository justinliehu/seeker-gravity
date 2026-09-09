#!/usr/bin/env python3
"""Payment backend for Seeker Gravity's optional 100 SKR revive.

Four endpoints, no database, no private key:

  GET  /pay/config              price, token mint, platform wallet, memo prefix
  POST /pay/tx      {ref, wallet}     -> unsigned base64 transaction the wallet signs
  POST /pay/confirm {ref, signature}  -> verifies that signature paid that order
  GET  /pay/status?ref=...            -> {"paid": true|false}, recovering by memo if needed

The transaction is built for the player to sign: an SPL transfer_checked of the price from the
player's token account to the publisher's, plus a Memo instruction carrying the order reference. The
server can neither sign nor move anything; all it does is build and then check the chain.

Run:  uvicorn app:app --port 8000        (see requirements.txt)
Production runs the same pay.py behind one process that serves several games; this file is the
single-game version so the flow can be read and run on its own.
"""
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import pay

PRODUCT = os.getenv("PAY_PRODUCT", "revive")
app = FastAPI(title="Seeker Gravity payments")


class TxReq(BaseModel):
    ref: str = ""
    wallet: str = ""


class ConfirmReq(BaseModel):
    ref: str = ""
    signature: str = ""


@app.get("/healthz")
def healthz():
    return {"ok": True, "product": PRODUCT, "platform": pay.PLATFORM_WALLET}


@app.get("/pay/config")
def pay_config():
    return pay.config()


@app.post("/pay/tx")
def pay_tx(req: TxReq):
    try:
        return pay.build_tx(req.wallet, req.ref, PRODUCT)
    except pay.PayError as err:
        return JSONResponse({"error": str(err)}, status_code=400)
    except Exception as err:   # RPC down etc: never leak a traceback to the game
        return JSONResponse({"error": f"could not build the transaction: {type(err).__name__}"}, status_code=502)


@app.post("/pay/confirm")
def pay_confirm(req: ConfirmReq):
    try:
        return pay.confirm(req.ref, req.signature)
    except pay.PayError as err:
        return JSONResponse({"paid": False, "pending": False, "error": str(err)}, status_code=400)
    except Exception as err:
        return {"paid": False, "pending": True, "error": f"verification hiccup: {type(err).__name__}"}


@app.get("/pay/status")
def pay_status(ref: str = ""):
    try:
        return pay.status(ref)
    except Exception as err:
        return {"paid": False, "error": f"status hiccup: {type(err).__name__}"}

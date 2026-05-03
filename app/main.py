import os
import signal
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from .store import RedisStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
store = RedisStore(REDIS_URL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await store.connect()
    logger.info("Connected to Redis at %s", REDIS_URL)
    yield
    await store.close()


app = FastAPI(title="Stock Market", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class StockEntry(BaseModel):
    name: str
    quantity: int

    @field_validator("quantity")
    @classmethod
    def non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("quantity must be >= 0")
        return v


class SetBankRequest(BaseModel):
    stocks: list[StockEntry]


class TradeRequest(BaseModel):
    type: str

    @field_validator("type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in ("buy", "sell"):
            raise ValueError("type must be 'buy' or 'sell'")
        return v

@app.get("/stocks")
async def get_stocks():
    stocks = await store.get_bank_stocks()
    return {"stocks": stocks}

@app.post("/stocks", status_code=200)
async def set_stocks(body: SetBankRequest):
    await store.set_bank_stocks([s.model_dump() for s in body.stocks])
    return {"ok": True}

@app.post("/wallets/{wallet_id}/stocks/{stock_name}", status_code=200)
async def trade(wallet_id: str, stock_name: str, body: TradeRequest):
    bank_qty = await store.get_bank_stock(stock_name)
    if bank_qty is None:
        raise HTTPException(status_code=404, detail=f"Stock '{stock_name}' does not exist")

    if body.type == "buy":
        if bank_qty < 1:
            raise HTTPException(status_code=400, detail="No stock available in bank")
        await store.adjust_bank_stock(stock_name, -1)
        await store.adjust_wallet_stock(wallet_id, stock_name, +1)

    else:
        wallet_qty = await store.get_wallet_stock(wallet_id, stock_name)
        if wallet_qty < 1:
            raise HTTPException(status_code=400, detail="No stock in wallet to sell")
        await store.adjust_wallet_stock(wallet_id, stock_name, -1)
        await store.adjust_bank_stock(stock_name, +1)

    await store.append_log({
        "type": body.type,
        "wallet_id": wallet_id,
        "stock_name": stock_name,
    })

    return {"ok": True}

@app.get("/wallets/{wallet_id}")
async def get_wallet(wallet_id: str):
    stocks = await store.get_wallet(wallet_id)
    return {"id": wallet_id, "stocks": stocks}


@app.get("/wallets/{wallet_id}/stocks/{stock_name}")
async def get_wallet_stock(wallet_id: str, stock_name: str):
    bank_qty = await store.get_bank_stock(stock_name)
    if bank_qty is None:
        raise HTTPException(status_code=404, detail=f"Stock '{stock_name}' does not exist")
    qty = await store.get_wallet_stock(wallet_id, stock_name)
    return qty

@app.get("/log")
async def get_log():
    log = await store.get_log()
    return {"log": log}

@app.post("/chaos")
async def chaos():
    logger.warning("CHAOS: killing this instance (PID %d)", os.getpid())
    signal.raise_signal(signal.SIGTERM)
    return {"ok": True}

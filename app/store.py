import json
import redis.asyncio as aioredis


class RedisStore:
    def __init__(self, url: str) -> None:
        self._url = url
        self._r: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._r = aioredis.from_url(self._url, decode_responses=True)
        await self._r.ping()

    async def close(self) -> None:
        if self._r:
            await self._r.aclose()

    async def set_bank_stocks(self, stocks: list[dict]) -> None:
        pipe = self._r.pipeline()
        for s in stocks:
            pipe.set(f"bank:{s['name']}", s["quantity"])
            pipe.sadd("stocks_index", s["name"])
        await pipe.execute()

    async def get_bank_stocks(self) -> list[dict]:
        names = await self._r.smembers("stocks_index")
        if not names:
            return []
        pipe = self._r.pipeline()
        for name in names:
            pipe.get(f"bank:{name}")
        values = await pipe.execute()
        return [
            {"name": name, "quantity": int(v or 0)}
            for name, v in zip(names, values)
        ]

    async def get_bank_stock(self, name: str) -> int | None:
        in_index = await self._r.sismember("stocks_index", name)
        if not in_index:
            return None
        val = await self._r.get(f"bank:{name}")
        return int(val or 0)

    async def adjust_bank_stock(self, name: str, delta: int) -> int:
        return int(await self._r.incrby(f"bank:{name}", delta))

    async def get_wallet(self, wallet_id: str) -> list[dict]:
        names = await self._r.smembers("stocks_index")
        if not names:
            return []
        pipe = self._r.pipeline()
        for name in names:
            pipe.get(f"wallet:{wallet_id}:{name}")
        values = await pipe.execute()
        return [
            {"name": name, "quantity": int(v or 0)}
            for name, v in zip(names, values)
            if int(v or 0) > 0
        ]

    async def get_wallet_stock(self, wallet_id: str, stock_name: str) -> int:
        val = await self._r.get(f"wallet:{wallet_id}:{stock_name}")
        return int(val or 0)

    async def adjust_wallet_stock(self, wallet_id: str, stock_name: str, delta: int) -> int:
        self._r.sadd("wallets_index", wallet_id)
        key = f"wallet:{wallet_id}:{stock_name}"
        new_val = int(await self._r.incrby(key, delta))
        await self._r.sadd("wallets_index", wallet_id)
        return new_val

    async def append_log(self, entry: dict) -> None:
        await self._r.rpush("log", json.dumps(entry))

    async def get_log(self) -> list[dict]:
        raw = await self._r.lrange("log", 0, -1)
        return [json.loads(r) for r in raw]

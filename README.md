# Stock Market App

Simple stock market app

## Tech Stack

- Python (FastAPI)
- Redis
- Nginx
- HTML

## Important decisions

**Load Balancer (Nginx)**: 
Two FastAPI instances (api1, api2) run independently and share state via Redis. Nginx load-balances requests between them. When one instance is killed, nginx automatically removes it from the upstream pool, so the other instance continues serving requests without interruption. The killed instance restarts automatically (`restart: always`).

**Shared State (Redis)**: All wallets, bank stock quantities, and audit logs are stored in Redis. This ensures that even if one API instance dies, the other has access to all data with no loss.

## Start

```bash
docker compose up --build -d
```

Access:
http://localhost:8080
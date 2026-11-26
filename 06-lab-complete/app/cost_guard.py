"""Reserve and settle the service-wide daily mock LLM budget in Redis."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from .config import settings
from .redis_client import r

NANO_USD_PER_DOLLAR = 1_000_000_000
INPUT_NANO_USD_PER_TOKEN = 150
OUTPUT_NANO_USD_PER_TOKEN = 600

reserve = r.register_script("""
local used = tonumber(redis.call('GET', KEYS[1]) or '0')
local amount = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
if used + amount > limit then
    return 0
end
redis.call('INCRBY', KEYS[1], amount)
redis.call('EXPIREAT', KEYS[1], ARGV[3])
return 1
""")

settle = r.register_script("""
if redis.call('EXISTS', KEYS[1]) == 1 then
    return redis.call('INCRBY', KEYS[1], ARGV[1])
end
return 0
""")


@dataclass(frozen=True)
class Reservation:
    key: str
    amount: int


def _cost(input_tokens: int, output_tokens: int) -> int:
    return input_tokens * INPUT_NANO_USD_PER_TOKEN + output_tokens * OUTPUT_NANO_USD_PER_TOKEN


def check_budget(input_tokens: int, max_output_tokens: int) -> Reservation:
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    key = f"day14:budget:{now.date().isoformat()}"
    amount = _cost(input_tokens, max_output_tokens)
    limit = int(settings.daily_budget_usd * NANO_USD_PER_DOLLAR)
    if not reserve(keys=[key], args=[amount, limit, int(midnight.timestamp())]):
        raise HTTPException(status_code=402, detail="Daily budget exceeded")
    return Reservation(key, amount)


def record_cost(reservation: Reservation, input_tokens: int, output_tokens: int) -> None:
    actual = _cost(input_tokens, output_tokens)
    settle(keys=[reservation.key], args=[actual - reservation.amount])


def cancel_reservation(reservation: Reservation) -> None:
    settle(keys=[reservation.key], args=[-reservation.amount])

"""
維運指令 / Maintenance CLI.

  python -m firefly.cli maintenance      # 叢集生命週期 + 標籤巡檢 + 網域回查(以 cron 每小時執行)
  python -m firefly.cli seed-domains     # 由 config/domain_signals.yaml 匯入網域訊號(留痕不硬刪)
  python -m firefly.cli recompute        # 橋接引擎批次重算(每小時 cron;Phase A 不裁決)
  python -m firefly.cli poll-mentions    # Threads mentions 輪詢(備援路線)
  python -m firefly.cli line-onboarding-push [--force]   # D-014 引導期推播(每日一次;排程器每 5 分鐘呼叫)
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select

from .config import REPO_ROOT, get_config
from .db import get_sessionmaker
from .models import DomainSignal
from .services.audit import audit


async def _maintenance() -> None:
    from .pipeline.ingest import domain_lookback, tag_patrol
    from .pipeline.stage2_cluster import assign_or_form, lifecycle_sweep
    from .pipeline.threads_client import HttpThreadsAPI

    async with get_sessionmaker()() as s:
        print("lifecycle:", await lifecycle_sweep(s))
        if get_config().threads.enabled:
            api = HttpThreadsAPI()
            new = await tag_patrol(s, api) + await domain_lookback(s, api)
            for snap in new:
                await assign_or_form(s, snap)
            print("ingested:", len(new))
        await s.commit()


async def _seed_domains() -> None:
    p = REPO_ROOT / get_config().fingerprint.domain_signals_path
    data = yaml.safe_load(Path(p).read_text(encoding="utf-8")) or {}
    version = str(data.get("version", "0"))
    async with get_sessionmaker()() as s:
        existing = {(d.domain, d.list_version): d for d in (await s.scalars(select(DomainSignal))).all()}
        added = 0
        for e in data.get("entries", []):
            key = (e["domain"], str(e.get("list_version", version)))
            if key in existing:
                continue
            s.add(DomainSignal(domain=e["domain"], source_list=e["source_list"], list_version=key[1], evidence_url=e.get("evidence_url"), added_at=datetime.now(timezone.utc)))
            added += 1
        await audit(s, "domain_signal", None, "list_updated", {"list_version": version, "added": added})
        await s.commit()
        print("added", added)


async def _recompute() -> None:
    from .bridging.engine import recompute

    async with get_sessionmaker()() as s:
        print(await recompute(s))
        await s.commit()


async def _poll_mentions() -> None:
    from .bots.threads import poll_mentions

    print(await poll_mentions())


async def _line_onboarding_push(force: bool = False) -> None:
    from .bots.line_client import get_line_client
    from .bots.line_onboarding import run_daily_push

    async with get_sessionmaker()() as s:
        print(await run_daily_push(s, get_line_client(), force=force))
        await s.commit()


COMMANDS = {"maintenance": _maintenance, "seed-domains": _seed_domains, "recompute": _recompute, "poll-mentions": _poll_mentions, "line-onboarding-push": _line_onboarding_push}


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        return 2
    if argv[0] == "line-onboarding-push":
        asyncio.run(_line_onboarding_push(force="--force" in argv[1:]))
        return 0
    asyncio.run(COMMANDS[argv[0]]())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

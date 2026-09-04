"""
維運指令 / Maintenance CLI.

  python -m firefly.cli maintenance      # 叢集生命週期 + 標籤巡檢 + 網域回查(以 cron 每小時執行)
  python -m firefly.cli seed-domains     # 由 config/domain_signals.yaml 匯入網域訊號(留痕不硬刪)
  python -m firefly.cli recompute        # 橋接引擎批次重算(每小時 cron;Phase A 不裁決)
  python -m firefly.cli poll-mentions    # Threads mentions 輪詢(備援路線)
  python -m firefly.cli line-onboarding-push [--force]   # D-014 引導期推播(每日一次;排程器每 5 分鐘呼叫)
  python -m firefly.cli check-embedder   # 回報實際生效的嵌入後端;設定要 e5 卻退回雜湊時非零離開
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select

from .config import REPO_ROOT, get_config, get_settings
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


async def _check_embedder() -> None:
    """回報實際生效的嵌入後端。設定要 e5 卻退回雜湊嵌入即非零離開(A1 上線檢查)。
    Report the embedding backend actually in use; exit non-zero if e5 is configured but the
    hashed fallback is active. get_embedder() swallows every load error, so without this the
    degradation is only visible later in cluster.signal_summary.embedder."""
    from .pipeline.embedding import get_embedder

    cfg = get_config().embedding
    configured = os.environ.get("FIREFLY_EMBEDDER", cfg.backend)
    embedder = get_embedder()
    dim = len(embedder.embed(["螢火 / firefly"])[0])
    # 一併回報設定檔位置:設定檔沒被讀到時參數會靜默退回預設值,這裡讓它可見
    # Report the config path too: when it is not found, tunables silently fall back to defaults
    from pathlib import Path

    cfg_path = get_settings().firefly_config_path
    print(json.dumps({"configured": configured, "active": embedder.name, "dim": dim, "config_dim": cfg.dim,
                      "model": cfg.model, "config_path": cfg_path, "config_found": Path(cfg_path).exists()}, ensure_ascii=False))
    if configured == "e5" and not embedder.name.startswith("e5:"):
        print(f"ERROR: configured e5 ({cfg.model}) but fell back to {embedder.name}", file=sys.stderr)
        raise SystemExit(1)
    if dim != cfg.dim:
        # D-012:維度必須與模型一致,否則 pgvector 欄位與索引對不上
        print(f"ERROR: embedding dim {dim} != config dim {cfg.dim}", file=sys.stderr)
        raise SystemExit(1)


COMMANDS = {"maintenance": _maintenance, "seed-domains": _seed_domains, "recompute": _recompute, "poll-mentions": _poll_mentions, "line-onboarding-push": _line_onboarding_push, "check-embedder": _check_embedder}


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

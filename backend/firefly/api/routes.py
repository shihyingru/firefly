"""消費端與貢獻者端點 / Consumer and contributor endpoints(文件 06)。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_config
from ..db import get_db
from ..models import Cluster, ClusterFlag, Contributor
from ..schemas import (
    ContributorMe,
    DeviceIssued,
    FlagRequest,
    LookupRequest,
    ProfileUpdate,
    VoteRequest,
    VoteResponse,
)
from ..services import contributors as contrib_svc
from ..services.audit import audit
from ..services.cards import card_public_view, cast_vote, get_visible_card, phase_a_queue
from ..services.lookup import lookup as do_lookup
from ..services.urlnorm import InvalidURL, normalize_url
from .deps import optional_contributor, rate_limited, require_contributor, require_named
from .errors import ApiError, forbidden, not_found

router = APIRouter(prefix="/v1")


@router.post("/devices", response_model=DeviceIssued, status_code=201, dependencies=[Depends(rate_limited)])
async def issue_device(session: AsyncSession = Depends(get_db)) -> DeviceIssued:
    """D-007:核發匿名裝置代號。不收任何裝置資訊。/ Issue an anonymous device token; no device info collected."""
    _, token = await contrib_svc.issue_device(session)
    await session.commit()
    return DeviceIssued(device_token=token)


@router.post("/lookup", dependencies=[Depends(rate_limited)])
async def lookup(
    body: LookupRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
    c: Contributor | None = Depends(optional_contributor),
):
    try:
        url = normalize_url(body.url)
    except InvalidURL:
        raise ApiError(400, "invalid_url", "連結格式無法辨識", "URL could not be parsed") from None
    if c is not None:
        await contrib_svc.record_lookup(session, c)
        await session.commit()
    result = await do_lookup(session, url)
    response.status_code = result.http
    if result.retry_after:
        response.headers["Retry-After"] = str(result.retry_after)
    return result.body()


@router.get("/cards/{card_id}")
async def get_card(card_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    card = await get_visible_card(session, card_id)
    if card is None:
        raise not_found("card_not_available")
    return card_public_view(card)


@router.post("/cards/{card_id}/votes", response_model=VoteResponse, dependencies=[Depends(rate_limited)])
async def vote(
    card_id: uuid.UUID,
    body: VoteRequest,
    session: AsyncSession = Depends(get_db),
    c: Contributor = Depends(require_contributor),
) -> VoteResponse:
    card = await get_visible_card(session, card_id)
    if card is None:
        raise not_found("card_not_available")
    v = await cast_vote(session, c, card, body.helpful)
    await session.commit()
    return VoteResponse(accepted=True, counted=v.weight > 0)


@router.get("/queue", dependencies=[Depends(rate_limited)])
async def queue(
    limit: int = Query(default=None, ge=1),
    session: AsyncSession = Depends(get_db),
    c: Contributor = Depends(require_contributor),
):
    cfg = get_config().queue
    n = min(limit or cfg.default_limit, cfg.max_limit)
    cards = await phase_a_queue(session, c, n)
    return {"strategy": cfg.strategy, "cards": [card_public_view(x) for x in cards]}


@router.post("/clusters/{cluster_id}/flags", status_code=201, dependencies=[Depends(rate_limited)])
async def flag_cluster(
    cluster_id: uuid.UUID,
    body: FlagRequest,
    session: AsyncSession = Depends(get_db),
    c: Contributor = Depends(require_named),
):
    cluster = await session.get(Cluster, cluster_id)
    if cluster is None:
        raise not_found("cluster_not_found")
    post_url = None
    if body.post_url:
        try:
            post_url = normalize_url(body.post_url)
        except InvalidURL:
            raise ApiError(400, "invalid_url", "連結格式無法辨識", "URL could not be parsed") from None
    session.add(ClusterFlag(cluster_id=cluster.id, contributor_id=c.id, kind=body.kind, post_url=post_url, note=body.note))
    # 審計只記模式層:哪個叢集被標記、哪一類;不記誰 / audit records pattern only, never who
    await audit(session, "cluster", str(cluster.id), "flagged", {"kind": body.kind.value})
    await session.commit()
    return {"accepted": True}


@router.get("/contributors/me", response_model=ContributorMe)
async def me(c: Contributor = Depends(require_contributor)) -> ContributorMe:
    return ContributorMe(id=str(c.id), origin=c.origin.value, named_profile=c.named_profile, lookup_count=c.lookup_count, eligible=contrib_svc.is_eligible(c))


@router.put("/contributors/me", response_model=ContributorMe)
async def update_me(body: ProfileUpdate, session: AsyncSession = Depends(get_db), c: Contributor = Depends(require_contributor)) -> ContributorMe:
    """升級為具名貢獻者(文件 02:累積有效投票後)。暱稱是唯一新增的資料。/ Become named; nickname is the only new datum."""
    if not contrib_svc.is_eligible(c):
        raise forbidden("尚未達到具名貢獻者門檻", "Eligibility threshold not met")
    c.named_profile = body.named_profile
    await session.commit()
    return ContributorMe(id=str(c.id), origin=c.origin.value, named_profile=c.named_profile, lookup_count=c.lookup_count, eligible=True)

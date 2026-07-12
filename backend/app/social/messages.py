"""Direct messages. A conversation is the union of both directions between a pair of users."""
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models import Message, Profile, User

from . import service
from .schemas import MessageCreate

router = APIRouter()


@router.get("/messages")
async def conversations(current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """One row per peer: the latest message and how many are unread from them."""
    rows = (await db.execute(
        select(Message).where(
            or_(Message.sender_id == current.id, Message.recipient_id == current.id)
        ).order_by(Message.created_at.desc()).limit(500)
    )).scalars().all()

    threads: dict[str, dict] = {}
    for m in rows:
        peer = m.recipient_id if m.sender_id == current.id else m.sender_id
        t = threads.setdefault(peer, {"peer_id": peer, "last": None, "last_at": 0.0, "unread": 0})
        if m.created_at > t["last_at"]:
            t["last_at"] = m.created_at
            t["last"] = m.body
            t["last_from_me"] = m.sender_id == current.id
        if m.recipient_id == current.id and m.read_at is None:
            t["unread"] += 1

    peers = await service.load_authors(db, set(threads.keys()))
    out = []
    for peer_id, t in threads.items():
        brief = peers.get(peer_id) or service.unknown_author(peer_id)
        out.append({
            "peer": brief, "last": t["last"], "last_at": t["last_at"],
            "last_from_me": t.get("last_from_me", False), "unread": t["unread"],
        })
    out.sort(key=lambda x: x["last_at"], reverse=True)
    return {"conversations": out}


@router.get("/messages/{handle}")
async def thread(handle: str, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    peer = await service.user_by_handle(db, handle)
    # Fetch the NEWEST 500 (desc + limit), then reverse to chronological order — a plain
    # asc + limit would pin the window to the oldest messages and never show recent ones.
    rows = (await db.execute(
        select(Message).where(
            or_(
                (Message.sender_id == current.id) & (Message.recipient_id == peer.id),
                (Message.sender_id == peer.id) & (Message.recipient_id == current.id),
            )
        ).order_by(Message.created_at.desc()).limit(500)
    )).scalars().all()
    rows = list(reversed(rows))
    # Mark the peer's messages to me as read.
    await db.execute(
        update(Message).where(
            Message.sender_id == peer.id, Message.recipient_id == current.id, Message.read_at.is_(None)
        ).values(read_at=service.now())
    )
    await db.commit()
    profile = await db.get(Profile, peer.id)
    return {
        "peer": service.user_brief(peer, profile),
        "messages": [
            {"id": m.id, "from_me": m.sender_id == current.id, "body": m.body, "created_at": m.created_at}
            for m in rows
        ],
    }


@router.post("/messages/{handle}", status_code=status.HTTP_201_CREATED)
async def send_message(
    handle: str, body: MessageCreate, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    peer = await service.user_by_handle(db, handle)
    if peer.id == current.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot message yourself")
    msg = Message(
        id="msg-" + uuid4().hex[:10], sender_id=current.id, recipient_id=peer.id,
        body=body.body, created_at=service.now(), read_at=None,
    )
    db.add(msg)
    await db.commit()
    return {"id": msg.id, "from_me": True, "body": msg.body, "created_at": msg.created_at}

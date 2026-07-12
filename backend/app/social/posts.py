"""Posts, likes, comments."""
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models import Comment, Like, Post, User

from . import service
from .schemas import CommentCreate, PostCreate

router = APIRouter()


async def _get_post(db: AsyncSession, post_id: str) -> Post:
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


@router.post("/posts", status_code=status.HTTP_201_CREATED)
async def create_post(body: PostCreate, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    post = Post(
        id="post-" + uuid4().hex[:10], author_id=current.id, body=body.body,
        image_key=body.image_key or None, created_at=service.now(),
    )
    db.add(post)
    await db.commit()
    hydrated = await service.hydrate_posts(db, current.id, [post])
    return hydrated[0]


@router.get("/posts/{post_id}")
async def get_post(post_id: str, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    post = await _get_post(db, post_id)
    hydrated = (await service.hydrate_posts(db, current.id, [post]))[0]
    comments = (await db.execute(
        select(Comment).where(Comment.post_id == post_id).order_by(Comment.created_at.asc()).limit(200)
    )).scalars().all()
    authors = await service.load_authors(db, {c.author_id for c in comments})
    hydrated["comments"] = [
        {
            "id": c.id,
            "author": authors.get(c.author_id) or service.unknown_author(c.author_id),
            "body": c.body,
            "created_at": c.created_at,
        }
        for c in comments
    ]
    return hydrated


@router.delete("/posts/{post_id}")
async def delete_post(post_id: str, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    post = await _get_post(db, post_id)
    if post.author_id != current.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your post")
    await db.execute(delete(Like).where(Like.post_id == post_id))
    await db.execute(delete(Comment).where(Comment.post_id == post_id))
    await db.delete(post)
    await db.commit()
    return {"deleted": True}


@router.post("/posts/{post_id}/like")
async def like_post(post_id: str, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _get_post(db, post_id)
    existing = (await db.execute(
        select(Like).where(Like.user_id == current.id, Like.post_id == post_id)
    )).first()
    if existing is None:
        db.add(Like(user_id=current.id, post_id=post_id, created_at=service.now()))
        await db.commit()
    count = (await db.execute(
        select(func.count()).select_from(Like).where(Like.post_id == post_id)
    )).scalar() or 0
    return {"liked": True, "like_count": int(count)}


@router.delete("/posts/{post_id}/like")
async def unlike_post(post_id: str, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Like).where(Like.user_id == current.id, Like.post_id == post_id))
    await db.commit()
    count = (await db.execute(
        select(func.count()).select_from(Like).where(Like.post_id == post_id)
    )).scalar() or 0
    return {"liked": False, "like_count": int(count)}


@router.post("/posts/{post_id}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(
    post_id: str, body: CommentCreate, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _get_post(db, post_id)
    comment = Comment(
        id="cmt-" + uuid4().hex[:10], post_id=post_id, author_id=current.id,
        body=body.body, created_at=service.now(),
    )
    db.add(comment)
    await db.commit()
    profile_authors = await service.load_authors(db, {current.id})
    return {
        "id": comment.id,
        "author": profile_authors.get(current.id),
        "body": comment.body,
        "created_at": comment.created_at,
    }

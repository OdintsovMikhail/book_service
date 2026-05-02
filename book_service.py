from fastapi import FastAPI, HTTPException
from utility import get_connection, get_api_urls
from schemas import BookOut, BookCommentIn, CommentOut
from broker import publish, Source
import httpx
import logging

app = FastAPI(
    title="BookService API",
    description="",
    version="1.0.0",
)

logger = logging.getLogger("comment_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

urls = get_api_urls()

def _call(method: str, url: str, **kwargs) -> httpx.Response:
    try:
        resp = httpx.request(method, url, timeout=5.0, **kwargs)
    except httpx.RequestError as exc:
        logger.error("Failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Downstream service unreachable: {exc}")
    return resp


    # ── GET /api/book/{title} ─────────────────────────────────────────────────────
 
@app.get("/book/{title}", response_model=BookOut)
def get_book(title: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT Id, Name, Genre, Author FROM dbo.book WHERE Name LIKE ?",
            f"%{title}%"
        )
        rows = cursor.fetchall()
 
    if not rows:
        exc = HTTPException(status_code=404, detail="No books found matching that title")
        logger.error("Failed: %s", exc)
        raise exc
 
    logger.info("Book found id=%s title=%s", rows[0][0], title)
    return BookOut(id=rows[0][0], name=rows[0][1], genre=rows[0][2], author=rows[0][3])


# ── GET /book/id/{id}  (inter-service: MeetingService calls this) ─────────────

@app.get("/book/id/{book_id}", response_model=BookOut)
def get_book_by_id(book_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT Id, Name, Genre, Author FROM dbo.book WHERE Id = ?", book_id
        )
        row = cursor.fetchone()
 
    if not row:
        exc = HTTPException(status_code=404, detail="Book not found")
        logger.error("Failed: %s", exc)
        raise exc
    
    logger.info("Book found id=%s title=%s", book_id, row[1])
    return BookOut(id=row[0], name=row[1], genre=row[2], author=row[3])
 
 
# ── POST /book/comment ────────────────────────────────────────────────────────
 
class BookCommentPayload(BookCommentIn):
    book_id: int
 
@app.post("/book/comment", response_model=CommentOut, status_code=201)
async def add_book_comment(payload: BookCommentPayload):
    # 1. Verify user exists via UserService
    resp = _call("GET", f"{urls["user"]}/user/id/{payload.user_id}")
    if resp.status_code == 404:
        exc = HTTPException(status_code=404, detail="User not found")
        logger.error("Failed: %s", exc)
        raise exc
    if resp.status_code != 200:
        exc = HTTPException(status_code=502, detail="UserService error")
        logger.error("Failed: %s", exc)
        raise exc
 
    # 2. Verify book exists locally (BookService owns this table)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT Id FROM dbo.book WHERE Id = ?", payload.book_id)
        if not cursor.fetchone():
            exc = HTTPException(status_code=404, detail="Book not found")
            logger.error("Failed: %s", exc)
            raise exc

    # 3. Publish to Azure Service Bus
    await publish(Source.MEETING, {
        "user_id":    payload.user_id,
        "text":       payload.text,
        "meeting_id": payload.meeting_id,
    })
    logger.info("Comment is being processed")

    return {"status": "accepted", "detail": "Comment is being processed"}
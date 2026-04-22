from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date


# ── User ──────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    email: str


# ── Book ──────────────────────────────────────────────────────────────────────

class BookOut(BaseModel):
    id: int
    name: str
    genre: Optional[str]
    author: str

class BookCommentIn(BaseModel):
    user_id: int
    text: str


# ── Meeting ───────────────────────────────────────────────────────────────────

class MeetingCreate(BaseModel):
    subject_book_id: int
    date: date

class MeetingOut(BaseModel):
    id: int
    subject_book_id: int
    date: date

class MeetingCommentIn(BaseModel):
    user_id: int
    text: str

class MeetingInvite(BaseModel):
    meeting_id: int


# ── Comment ───────────────────────────────────────────────────────────────────

class CommentOut(BaseModel):
    id: int
    user_id: int
    text: str
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from typing import Optional


class Base(DeclarativeBase):
    pass


class ChatSettings(Base):
    __tablename__ = "settings"

    chat_id: Mapped[int] = mapped_column(primary_key=True)
    warn_limit: Mapped[int]
    warn_restriction: Mapped[str]
    warn_rest_time: Mapped[int]
    greeting_enabled: Mapped[bool] = mapped_column(default=False)
    greeting_text: Mapped[Optional[str]]
    greeting_file_id: Mapped[Optional[str]]


class Warns(Base):
    __tablename__ = "warns"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int]
    user_id: Mapped[int]
    count: Mapped[int] = mapped_column(default=0)

    def __repr__(self):
        return f"Warns(id={self.id}, chat_id={self.chat_id}, user_id={self.user_id}, count={self.count})"

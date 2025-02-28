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
    warn_autoreset: Mapped[bool] = mapped_column(default=False)
    warn_autoreset_time: Mapped[int] = mapped_column(default=0)
    greeting_enabled: Mapped[bool] = mapped_column(default=False)
    greeting_text: Mapped[Optional[str]]
    greeting_file_id: Mapped[Optional[str]]

class Notes(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(nullable=False)
    type: Mapped[str] = mapped_column(nullable=False)

class Warns(Base):
    __tablename__ = "warns"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int]
    user_id: Mapped[int]
    count: Mapped[int] = mapped_column(default=0)
    reasons: Mapped[str]
    dates: Mapped[str]
    last_warn_time: Mapped[str] = mapped_column(nullable=True)

    def __repr__(self):
        return f"Warns(id={self.id}, chat_id={self.chat_id}, user_id={self.user_id}, count={self.count}, reason={self.reasons}, \
            dates={self.dates}, last_warn_time={self.last_warn_time})"

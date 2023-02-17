from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class Base(DeclarativeBase):
    pass


class ChatSettings(Base):
    __tablename__ = "settings"

    chat_id: Mapped[int] = mapped_column(primary_key=True)
    warn_limit: Mapped[int] = mapped_column()
    warn_restriction: Mapped[str] = mapped_column()
    warn_rest_time: Mapped[int] = mapped_column()


class Warns(Base):
    __tablename__ = "warns"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column()
    user_id: Mapped[int] = mapped_column()
    count: Mapped[int] = mapped_column(default=0, nullable=False)

    def __repr__(self):
        return f"Warns(id={self.id}, chat_id={self.chat_id}, user_id={self.user_id}, count={self.count})"

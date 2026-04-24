from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user", server_default="user")
    seller_id: Mapped[int | None] = mapped_column(ForeignKey("sellers.id"), nullable=True)

    seller = relationship("Seller", back_populates="users")

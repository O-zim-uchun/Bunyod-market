from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class SellerContent(Base):
    __tablename__ = "seller_contents"
    __table_args__ = (UniqueConstraint("seller_id", "content_type", name="uq_seller_content_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"), nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)  # promo | contact
    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    seller = relationship("Seller")

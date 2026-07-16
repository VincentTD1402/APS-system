"""APS Local DB — Customer model for impact scoring."""

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

# customer_type → impact_score mapping (1=internal, 2=small, 3=normal, 4=important, 5=vip)
CUSTOMER_TYPE_IMPACT: dict[str, int] = {
    "internal":  1,
    "small":     2,
    "normal":    3,
    "important": 4,
    "vip":       5,
}


class Customer(Base):
    """Customer master — used to determine order impact score for risk analysis.

    customer_type values: "internal" | "small" | "normal" | "important" | "vip"
    impact_score: 1–5 (stored explicitly so queries don't need a JOIN to derive it).
    """

    __tablename__ = "aps_customer"
    __table_args__ = (
        CheckConstraint(
            "customer_type IN ('internal','small','normal','important','vip')",
            name="ck_customer_type",
        ),
        CheckConstraint("impact_score BETWEEN 1 AND 5", name="ck_customer_impact_score"),
        {"schema": "aps_input"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # internal | small | normal | important | vip
    customer_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Denormalised for fast access: 1=internal, 2=small, 3=normal, 4=important, 5=vip
    impact_score: Mapped[int] = mapped_column(Integer, nullable=False)

    demands: Mapped[list["Demand"]] = relationship(back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer {self.customer_no!r} type={self.customer_type} impact={self.impact_score}>"

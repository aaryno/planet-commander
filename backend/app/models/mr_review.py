from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, JSON
from app.models.base import Base


class MRReview(Base):
    """Tracks MR review sessions and state."""

    __tablename__ = "mr_reviews"

    id = Column(Integer, primary_key=True)
    project = Column(String, nullable=False, index=True)
    mr_iid = Column(Integer, nullable=False, index=True)
    last_commit_sha = Column(String, nullable=True)
    needs_review = Column(Boolean, default=True, nullable=False)

    # Track all review sessions for this MR
    reviews = Column(JSON, default=list, nullable=False)  # List of {agent_id, session_id, commit_sha, timestamp}

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<MRReview {self.project}!{self.mr_iid}>"

"""Background job run tracking model"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from app.models.base import Base


class JobRun(Base):
    """Track execution history of background jobs"""

    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True)
    job_name = Column(String(200), nullable=False, index=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False)  # running, success, failed
    records_processed = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    def __repr__(self):
        return f"<JobRun {self.job_name} {self.status} at {self.started_at}>"

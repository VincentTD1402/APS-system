from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ResponseBase(BaseModel):
    """Base response model"""
    success: bool = True
    message: Optional[str] = None
    timestamp: datetime = datetime.now()


class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = False
    error: str
    detail: Optional[str] = None
    timestamp: datetime = datetime.now()

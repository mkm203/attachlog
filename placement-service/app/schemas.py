"""Request and response models, with the examples shown in /docs."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PlacementCreate(BaseModel):
    student_id: str = Field(min_length=1, max_length=50)
    student_name: str = Field(min_length=1, max_length=120)
    company_name: str = Field(min_length=1, max_length=120)
    company_city: str = Field(min_length=1, max_length=80)
    company_supervisor_id: str = Field(min_length=1, max_length=50)
    academic_supervisor_id: str = Field(min_length=1, max_length=50)
    start_date: date
    end_date: date

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "student_id": "stu-1", "student_name": "Clarisse Ngo", "company_name": "Douala Tech SARL",
        "company_city": "Douala", "company_supervisor_id": "cs-1", "academic_supervisor_id": "as-1",
        "start_date": "2026-09-07", "end_date": "2026-11-29"}]})


class PlacementUpdate(BaseModel):
    """Only the supervisors can be changed after creation."""
    company_supervisor_id: str = Field(min_length=1, max_length=50)
    academic_supervisor_id: str = Field(min_length=1, max_length=50)

    model_config = ConfigDict(json_schema_extra={"examples": [
        {"company_supervisor_id": "cs-2", "academic_supervisor_id": "as-1"}]})


class FinalEvaluation(BaseModel):
    score: int = Field(ge=0, le=20)
    comment: str = Field(min_length=1, max_length=1000)

    model_config = ConfigDict(json_schema_extra={"examples": [{"score": 16, "comment": "Reliable and curious."}]})


class PlacementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [{
        "id": "5c1e6f2a-9b7d-4c3e-8a1f-2d6b9e4c7a10",
        "student_id": "stu-1", "student_name": "Clarisse Ngo",
        "company_name": "Douala Tech SARL", "company_city": "Douala",
        "company_supervisor_id": "cs-1", "academic_supervisor_id": "as-1",
        "start_date": "2026-09-07", "end_date": "2026-11-29",
        "total_weeks": 12, "status": "open", "final_score": None, "final_comment": None}]})

    id: str
    student_id: str
    student_name: str
    company_name: str
    company_city: str
    company_supervisor_id: str
    academic_supervisor_id: str
    start_date: date
    end_date: date
    total_weeks: int
    status: Literal["open", "closed"]
    final_score: int | None = None
    final_comment: str | None = None


class PlacementPage(BaseModel):
    items: list[PlacementOut]
    page: int
    page_size: int
    total: int

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "items": [{
            "id": "5c1e6f2a-9b7d-4c3e-8a1f-2d6b9e4c7a10",
            "student_id": "stu-1", "student_name": "Clarisse Ngo",
            "company_name": "Douala Tech SARL", "company_city": "Douala",
            "company_supervisor_id": "cs-1", "academic_supervisor_id": "as-1",
            "start_date": "2026-09-07", "end_date": "2026-11-29",
            "total_weeks": 12, "status": "open", "final_score": None, "final_comment": None}],
        "page": 1, "page_size": 10, "total": 1}]})


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list | None = None


class ErrorResponse(BaseModel):
    """The one error format of every service: {"error": {"code", "message", "details"}}."""
    error: ErrorBody

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "error": {"code": "placement_not_found", "message": "Placement P9 not found", "details": None}}]})
class LoginRequest(BaseModel):
    """Credentials of one of the demo users (see the README for the list)."""
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=100)

    model_config = ConfigDict(json_schema_extra={"examples": [
        {"username": "co-1", "password": "Demo-co-1-2026"}]})


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    sub: str
    role: str
    name: str

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.example.signature",
        "token_type": "bearer", "expires_in": 28800,
        "sub": "co-1", "role": "coordinator", "name": "Julie Mbia"}]})
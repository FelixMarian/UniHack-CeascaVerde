from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Login(Input):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)
    # Password whitespace is significant.
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)


class UserCreate(Input):
    username: str = Field(pattern=r'^[a-zA-Z0-9_.-]{3,80}$')
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    role: Literal['Resident', 'Company']


class UserEdit(Input):
    display_name: str = Field(min_length=1, max_length=120)
    active: bool
    password: str | None = Field(default=None, min_length=8, max_length=128)


class PasswordChange(Input):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class BinInput(Input):
    bin_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    name: str = Field(min_length=1, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    company_id: int | None = None
    @model_validator(mode='after')
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Provide both coordinates or neither')
        return self


class Assignments(Input):
    bin_ids: list[str] = Field(max_length=1000)


class IncidentCreate(Input):
    request_id: str | None = Field(default=None, pattern=r'^[a-fA-F0-9-]{36}$')
    bin_id: str
    category: Literal['damaged', 'stolen', 'overflow', 'missed_collection', 'other']
    comment: str = Field(min_length=1, max_length=2000)
    photo_base64: str | None = Field(default=None, max_length=700_000)


class IncidentStatus(Input):
    status: Literal['open', 'in_progress', 'resolved']

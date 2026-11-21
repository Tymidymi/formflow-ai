"""Typed, document-agnostic intermediate contract between extraction and COI.

Only validates observed fields. It does not create, rename, or reconstruct
source controls and has no dictionary of example form questions.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator

InputType = Literal[
    "TEXT_FIELD", "TEXTAREA", "NUMBER", "DATEPICKER",
    "RADIO", "CHECKBOX", "SELECT", "FILE_UPLOADER", "INFO_BLOCK",
]
MAX_PAGES = 24
MAX_SECTIONS = 24
MAX_FIELDS_PER_SECTION = 120
MAX_FIELDS_TOTAL = 400


class SourceCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: StrictStr | None = None
    field_ref: StrictStr | None = None
    value: StrictStr

    @model_validator(mode="after")
    def validate_reference(self):
        if not (self.field or self.field_ref):
            raise ValueError("Brak źródła warunku SHOW.")
        if not self.value:
            raise ValueError("Brak wartości warunku SHOW.")
        return self


class CanonicalField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: StrictStr = Field(min_length=1, max_length=220)
    type: InputType
    required: StrictBool = False
    options: list[StrictStr] = Field(default_factory=list, max_length=20)
    evidence: StrictStr = Field(default="", max_length=260)
    source_page: StrictInt | None = Field(default=None, ge=1)
    source_line: StrictInt | None = Field(default=None, ge=1)
    row: StrictInt | None = Field(default=None, ge=1)
    column: StrictStr | None = Field(default=None, max_length=65)
    content: StrictStr | None = Field(default=None, max_length=7000)
    source: StrictStr | None = Field(default=None, max_length=80)
    source_choice_ref: StrictStr | None = Field(default=None, max_length=130)
    show_when: SourceCondition | None = None
    dictionary_name: StrictStr | None = Field(default=None, max_length=80)

    @field_validator("label")
    @classmethod
    def nonempty_label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Etykieta nie może być pusta.")
        return value

    @field_validator("options")
    @classmethod
    def validate_options(cls, values: list[str]) -> list[str]:
        if any(not x.strip() or len(x) > 160 for x in values):
            raise ValueError("Niepoprawna opcja wyboru.")
        return values

    @model_validator(mode="after")
    def validate_field(self):
        if self.type == "INFO_BLOCK" and self.options:
            raise ValueError("Blok informacyjny nie może zawierać opcji wyboru.")
        if self.row is not None and not self.column:
            raise ValueError("Komórka tabeli ma numer wiersza bez kolumny.")
        return self


class CanonicalSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: StrictStr = Field(min_length=1, max_length=220)
    fields: list[CanonicalField] = Field(default_factory=list, max_length=MAX_FIELDS_PER_SECTION)


class CanonicalPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: StrictStr = Field(min_length=1, max_length=220)
    sections: list[CanonicalSection] = Field(default_factory=list, max_length=MAX_SECTIONS)


class CanonicalForm(BaseModel):
    """Validated extraction inventory; distinct from the final COI JSON."""
    model_config = ConfigDict(extra="forbid")
    title: StrictStr = Field(min_length=1, max_length=255)
    pages: list[CanonicalPage] = Field(min_length=1, max_length=MAX_PAGES)

    @model_validator(mode="after")
    def validate_limits(self):
        count=sum(len(s.fields) for page in self.pages for s in page.sections)
        if count > MAX_FIELDS_TOTAL:
            raise ValueError("Zbyt wiele pól w formularzu.")
        return self


def canonicalize(value: dict) -> dict:
    """Validate exact observed structure and preserve all supplied fields.

    exclude_unset=True intentionally avoids inventing missing options, evidence
    or required flags: the canonical model is a contract, not a repair layer.
    """
    return CanonicalForm.model_validate(value).model_dump(exclude_unset=True)

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Person:
    name: str
    email: str


@dataclass
class Contact:
    name: str
    email: str
    url: str
    phone: str


@dataclass
class Article:
    code: str
    bulletin: str
    date: date | None
    rubrique: str
    title: str
    author: Person | None
    body: str
    images: list[str]
    contacts: list[Contact] = field(default_factory=list)

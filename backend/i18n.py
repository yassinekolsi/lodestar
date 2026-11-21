"""The language a request is answered in.

Three locales: English (`en`), French (`fr`) and Tunisian Arabic, Derja (`tn`). Tunisian
university courses are taught in French, so `tn` keeps the course content in French and changes
how Lodestar talks: the interface and the coach's replies are in Derja, with the course terms
left in French, the way students mix them.

The browser sends its locale on every call (`X-Lodestar-Locale`, or `?lang=` on a WebSocket,
which can't carry headers). A middleware puts it in a context variable, so the graph, the coach
and the registry read it without passing it through every function. Background work started
outside a request sees English.
"""

from collections.abc import Awaitable, Callable, MutableMapping
from contextvars import ContextVar
from typing import Any, Literal, cast
from urllib.parse import parse_qs

Locale = Literal["en", "fr", "tn"]
LOCALES: tuple[Locale, ...] = ("en", "fr", "tn")
DEFAULT: Locale = "en"

_current: ContextVar[Locale] = ContextVar("lodestar_locale", default=DEFAULT)


def current() -> Locale:
    return _current.get()


def set_current(locale: Locale) -> None:
    _current.set(locale)


def course_locale(locale: Locale | None = None) -> Locale:
    """The language of the course content: Derja speakers study from French notes."""
    loc = locale or current()
    return "fr" if loc == "tn" else loc


def parse(value: str | None) -> Locale:
    """A locale from a header or a query parameter: `fr`, `fr-FR`, `ar-TN`, `tn`. Unknown values
    fall back to English."""
    if not value:
        return DEFAULT
    for part in value.split(","):
        tag = part.split(";")[0].strip().lower().replace("_", "-")
        if tag in ("tn", "ar-tn", "aeb") or tag.startswith("aeb-"):
            return "tn"
        if tag == "ar" or tag.startswith("ar-"):
            return "tn"
        if tag == "fr" or tag.startswith("fr-"):
            return "fr"
        if tag == "en" or tag.startswith("en-"):
            return "en"
    return DEFAULT


Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]
App = Callable[[Scope, Receive, Send], Awaitable[None]]


class LocaleMiddleware:
    """Pure ASGI, so it covers WebSockets too (Starlette's BaseHTTPMiddleware doesn't)."""

    def __init__(self, app: App) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            headers = dict(cast(list[tuple[bytes, bytes]], scope.get("headers", [])))
            raw = headers.get(b"x-lodestar-locale")
            query = parse_qs(cast(bytes, scope.get("query_string", b"")).decode("latin-1"))
            langs = query.get("lang") or []
            value = raw.decode("latin-1") if raw else (langs[0] if langs else None)
            token = _current.set(parse(value) if value else DEFAULT)
            try:
                await self.app(scope, receive, send)
            finally:
                _current.reset(token)
            return
        await self.app(scope, receive, send)


# What the model is told, appended to every coach prompt --------------------------------------

_INSTRUCTION: dict[Locale, str] = {
    "en": "",
    "fr": (
        "Language: write your whole reply in French (français), with a natural, friendly tone "
        "for a Tunisian university student. The facts are listed in English: translate them, "
        "never add to them. Keep every number, formula and fact id exactly as written, "
        "including decimal points (write 0.75, not 0,75), so the citations still check."
    ),
    "tn": (
        "Language: write your whole reply in Tunisian Arabic (Derja, تونسي), in Arabic script, "
        "the way a friendly Tunisian tutor talks to a student. Keep the course terms in French, "
        "as Tunisian students do (for example « probabilité conditionnelle », « théorème de "
        "Bayes »). The facts are listed in English: translate them, never add to them. Keep "
        "every number, formula and fact id exactly as written, with decimal points, so the "
        "citations still check. Do not switch to Modern Standard Arabic."
    ),
}


def language_instruction(locale: Locale | None = None) -> str:
    return _INSTRUCTION[locale or current()]


def with_language(system: str, locale: Locale | None = None) -> str:
    extra = language_instruction(locale)
    return f"{system}\n\n{extra}" if extra else system


# Fixed sentences the backend writes itself (cards and templates) ------------------------------

_TEXT: dict[str, dict[Locale, str]] = {
    "notes": {"en": "Notes", "fr": "Notes", "tn": "Notes"},
    "hint_removed": {
        "en": "Two of the wrong answers are gone.",
        "fr": "Deux des mauvaises réponses ont disparu.",
        "tn": "نحّينالك زوز أجوبة غالطين.",
    },
    "quiz_name": {"en": "Quiz: {name}", "fr": "Quiz : {name}", "tn": "Quiz : {name}"},
    "explain_name": {
        "en": "Explain it back: {name}",
        "fr": "Explique-le : {name}",
        "tn": "فسّرها بكلامك : {name}",
    },
    "explain_prompt_low": {
        "en": (
            "Explain {name} to a classmate who missed the lecture, in your own words. A few "
            "sentences and one example is enough."
        ),
        "fr": (
            "Explique « {name} » à un camarade qui a raté le cours, avec tes propres mots. "
            "Quelques phrases et un exemple suffisent."
        ),
        "tn": ("فسّر « {name} » لصاحبك اللي فاتو الcours، بكلامك انت. شوية جمل ومثال واحد يكفيو."),
    },
    "explain_prompt_high": {
        "en": (
            "Explain {name} to a friend who has an exam, in your own words. A few sentences "
            "and one example is enough."
        ),
        "fr": (
            "Explique « {name} » à un ami qui a un examen, avec tes propres mots. Quelques "
            "phrases et un exemple suffisent."
        ),
        "tn": "فسّر « {name} » لصاحبك اللي عندو examen، بكلامك انت. شوية جمل ومثال واحد يكفيو.",
    },
    "which_concept": {
        "en": "Which part of {course}? For example {names}.",
        "fr": "Quelle partie de {course} ? Par exemple : {names}.",
        "tn": "أما جزء من {course} ؟ مثلاً : {names}.",
    },
    "fix": {"en": "Fix", "fr": "Correction", "tn": "الحل"},
    "key_ideas": {"en": "Key ideas", "fr": "Idées clés", "tn": "الأفكار المهمة"},
}


def text(key: str, locale: Locale | None = None, **values: object) -> str:
    entry = _TEXT[key]
    template = entry.get(locale or current()) or entry["en"]
    return template.format(**values) if values else template

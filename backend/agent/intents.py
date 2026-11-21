"""Intent routing (docs/plan/03, route_intent): keyword rules first, a structured LLM call only when
the rules aren't sure. The rules are also the fallback when no model answers in time.

Slots are filled here too: a game or skill the user named, skills they turned down for today
(UW3), "something quick", and the converse tool for a chat turn.
"""

import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import Field

from backend.contracts.common import Contract
from backend.contracts.llm import LlmSelection
from backend.contracts.session import Intent, IntentKind
from backend.llm.factory import LlmFactory, NoModelAvailable
from backend.registry.models import Registry

# Words people use for a concept come from the course itself (`aliases` in registry/courses/),
# so a new course needs no code here. Longer phrases win: "law of total probability" before
# "probability", "conditional probability" before "conditional".
SKILL_WORDS: list[tuple[re.Pattern[str], str]] = []


def _concept_words(registry: Registry) -> list[tuple[re.Pattern[str], str]]:
    phrases = [
        (phrase.lower(), concept.id)
        for course in registry.every_language()  # "Bayes", "théorème de Bayes", "بايز"
        for concept in course.concepts
        for phrase in [concept.name, *concept.aliases]
    ]
    phrases = list(dict.fromkeys(phrases))
    phrases.sort(key=lambda p: -len(p[0]))
    return [(re.compile(rf"(?<![\w]){re.escape(p)}(?![\w])", re.I), c) for p, c in phrases]


_DECLINE = re.compile(
    r"\b(not|no|skip|without|anything but|other than|instead of|rather not|don'?t want|"
    r"sick of|tired of|bored of|fed up with|enough)\b(?P<rest>.{0,40})",
    re.I,
)
_QUICK = re.compile(
    r"\b(quick|short|fast one|only (have|got) \d+ min\w*|\d+ min\w*|in a hurry|no time)\b", re.I
)
_ELSE = re.compile(
    r"\b(something else|another (one|game)|different (one|game)|not that one)\b", re.I
)
_THEME = re.compile(r"\babout ([a-z][a-z ]{2,30})$", re.I)

ToolChoice = Literal[
    "teach",
    "mistakes",
    "explain",
    "read_profile",
    "get_history",
    "search_memory",
    "session_history",
    "forecast_range",
    "contest",
]

# The user disagrees with a reading of them, or says something outside the game got in the way.
_CONTEST = re.compile(
    r"\b(i disagree|you'?re wrong|you are wrong|that'?s (wrong|not right|not fair|unfair|"
    r"not accurate|inaccurate)|that is (wrong|not right|not fair|unfair|not accurate|inaccurate)|"
    r"(wasn'?t|isn'?t) (a )?fair|(doesn'?t|does not|didn'?t) (reflect|seem right)|"
    r"not (really )?my (real|true|usual|actual)|i was (distracted|interrupted)|"
    r"(got|kept getting|keep getting) (distracted|interrupted)|"
    r"(room|place|it) was (so |too |really )?(noisy|loud)|too (noisy|loud)|"
    r"because of (the )?(noise|distractions?|interruptions?)|(lots|lot) of (noise|distractions?)|"
    r"someone (came in|called|interrupted)|my phone (rang|kept)|phone was ringing)\b",
    re.I,
)

# Patterns per kind. A turn whose patterns point to one kind is routed without asking a model.
_KINDS: list[tuple[IntentKind, re.Pattern[str]]] = [
    (
        "settings",
        re.compile(
            r"\b(settings?|willow|spark|sage|buddy|(change|switch) (my |the )?coach|"
            r"(calmer|friendlier|stricter|funnier|nicer) coach|coach (to|that)|be more (of )?a|"
            r"(push|chill|balanced) mode|mode please|from now on|stop suggesting|"
            r"prefer (harder|easier) (games|quizzes)|make it more chill|"
            r"don'?t suggest|camera|microphone|voice (on|off)|turn (the )?\w+ (on|off))\b",
            re.I,
        ),
    ),
    (
        "experiment",
        re.compile(
            r"\b(experiment|test (if|whether)|real test|compare (morning|evening|my)|"
            r"see (if|whether) \w+ (helps?|is better))\b",
            re.I,
        ),
    ),
    (
        "twin_chat",
        re.compile(
            r"\b(twin|when am i|best time|time of day|am i (better|sharper|faster) in|"
            r"morning or (the )?evening|do i do better|do i .{0,30} better at night)\b",
            re.I,
        ),
    ),
    (
        "goal",
        re.compile(
            r"\b(goal|aim for|target|(want|like|need) .{1,50}\b(solid|better|"
            r"stronger|improve\w*|faster)|improve my|get (better|faster) at|make my .{1,40} "
            r"(stronger|better|solid)|help me get (better|faster)|my goal|a goal)\b",
            re.I,
        ),
    ),
    (
        "life_context",
        re.compile(
            r"\b(slept|sleep|didn'?t sleep|tired|exhausted|up all night|ill|unwell|sick|"
            r"headache|cold|flu|exams?|exam week|stressed|stress|busy (week|day)|"
            r"jet ?lag|travell?ing|flew)\b",
            re.I,
        ),
    ),
]
_CHAT_TOOLS: list[tuple[ToolChoice, re.Pattern[str]]] = [
    (
        "mistakes",
        re.compile(
            r"\b(my mistakes|what mistakes|which mistakes|mistakes? (do|did) i|errors? (do|did) i|"
            r"keep (getting|doing|making)\b.{0,40}\b(wrong|mistakes?)|"
            r"(get|getting|got) .{0,30}\bwrong|what am i (doing|getting) wrong|"
            r"where do i go wrong|misconceptions?|(confus|mix)\w* up)\b",
            re.I,
        ),
    ),
    (
        "teach",
        re.compile(
            r"\b(i (don'?t|do not|can'?t) (get|understand|see)|don'?t understand|"
            r"what (is|are|does|do) (a |an |the )?|what'?s (a |an |the )?|teach me|"
            r"explain (to me |again |it |how |what |why )?(?!(your|that|this|the) (choice|pick|"
            r"decision))|help me (understand|with)|confused (about|by|with)|stuck (on|with)|"
            r"lost (on|with)|how (do|does|can|should) (i|you|we|it) (compute|calculate|find|solve|"
            r"use|apply|work)|walk me through|go over)\b",
            re.I,
        ),
    ),
    (
        "explain",
        re.compile(
            r"^why[?!. ]*$|\b(why (did you (choose|pick|assign)|this (game|quiz|exercise)|"
            r"so (hard|easy))|why\b.{0,50}\bagain|"
            r"how did you (choose|pick|decide)|what made you|explain (your|that|this|the) "
            r"(choice|pick|decision)|reason for this pick)\b",
            re.I,
        ),
    ),
    (
        "forecast_range",
        re.compile(
            r"\b(will|going to|gonna)\b.{0,40}\b(my|i)\b.{0,40}\b(score|be|reach|get)\b.{0,40}"
            r"\b(next|in a|in one|in \d+|by|later|future)\b|\b(predict|forecast)\b|\bmy future\b|"
            r"\b(exactly|precisely)\b.{0,30}\b(will|score)\b",
            re.I,
        ),
    ),
    (
        "session_history",
        re.compile(
            r"\b(what did i (play|do)|what (have i|games? did i) play\w*|which games? (did|have) i|"
            r"how did i do|my last (session|round|game)|last session|session history|"
            r"play(ed)? (yesterday|last|this|on)|games? (yesterday|last week|this week)|"
            r"show me my history)\b",
            re.I,
        ),
    ),
    (
        "search_memory",
        re.compile(
            r"\b(remember about me|know about me|did i (tell|say|mention)|what did i (say|tell)|"
            r"what do you remember|recall)\b",
            re.I,
        ),
    ),
    (
        "get_history",
        re.compile(
            r"\b(history|over (the )?(last|past)|changed|progress|improv\w*|got better|"
            r"since i started|(last|past|this) (week|month|\d+ days)|trend)\b",
            re.I,
        ),
    ),
    (
        "read_profile",
        re.compile(
            r"\b(how am i doing|my (profile|results?|scores?|strengths?|skills?)|"
            r"(memory|focus|speed|maths?|reasoning) score|how good is my|where am i at|"
            r"show me my|my .{1,45} score|how strong is my|what am i best at)\b",
            re.I,
        ),
    ),
]
# The student's own uploads (docs/plan/20).
NOTES_QUIZ = "quiz_notes"
_NOTES = re.compile(
    r"\b(my|the|our|from (my|the)) (own )?(notes|slides?|pdfs?|documents?|docs?|uploads?|"
    r"handouts?|lecture notes|course notes|course file|files?|chapter|lectures?)\b",
    re.I,
)
_QUIZ_WORDS = re.compile(r"\b(quiz|test me|questions?|practi[cs]e|exercises?|revise)\b", re.I)
_QUESTION = re.compile(
    r"(\?\s*$)|^\s*(how|why|what|when|which|who|where|is|are|does|do|can|could|should|explain)\b",
    re.I,
)
_PLAY = re.compile(
    r"\b(quiz( me)?|test me|questions? on|exercises?|revise|review|study|"
    r"play|game|round|start|train|practi[cs]e|let'?s (go|do)|go|again|another|one more|"
    r"ready|warm (me )?up|challenge me|give me|try|do some|can we do|something (quick|for))\b",
    re.I,
)
_SMALL_TALK = re.compile(
    r"^\s*(hi|hello|hey|thanks?( you)?|thank u|ok(ay)?( cool)?|cool|nice|bye|good night|"
    r"who are you|what can you do|how do (the|these) games work)\b",
    re.I,
)


# French and Tunisian Arabic (Derja) ------------------------------------------------------------
# The same rules in the two other languages a student may type (backend/i18n.py). Derja comes in
# Arabic script and in Latin letters with digits for some sounds ("ma fhemtech", "3awedli"), and is
# mixed with French course terms. Each rule keeps its English pattern and gains these as
# alternatives, so routing English is unchanged.

_FR_TN_KINDS: dict[str, str] = {
    "settings": (
        r"\b(paramètres|réglages|change[rz]? (de |le |mon )?coach|"
        r"coach (plus )?(calme|sympa|strict)|"
        r"mode (push|chill|équilibré)|caméra|micro(phone)?|(active|désactive|coupe) (la |le )?\w+|"
        r"arrête de (me )?proposer)\b|بدّل الcoach|بدل الcoach|الإعدادات|الparamètres"
    ),
    "experiment": (
        r"\b(une expérience|faire une expérience|tester si|teste si|vraie expérience|"
        r"comparer (le )?(matin|soir))\b|نجرّب|نجرب كان|تجربة"
    ),
    "twin_chat": (
        r"\b(quand (est-ce que )?je suis (le plus |plus )?(efficace|concentré|concentrée)|"
        r"meilleur moment|moment de la journée|matin ou (le )?soir)\b|"
        r"وقتاش نكون|الصباح ولا العشية|الصباح ولا الليل"
    ),
    "goal": (
        r"\b(objectif|mon but|je veux (être|devenir) .{0,40}(meilleur|solide|fort|forte)|"
        r"améliorer (mon|ma|mes)|progresser en|devenir solide en)\b|نحب نتحسن|هدف|نحب نولّي|نحب نولي"
    ),
    "life_context": (
        r"\b(dormi|mal dormi|pas dormi|fatigué|fatiguée|épuisé|épuisée|malade|mal à la tête|"
        r"grippe|examens?|semaine d'examens|stressé|stressée|stress|journée chargée)\b|"
        r"ما رقدتش|مارقدتش|تعبان|تعبانة|مريض|مريضة|مقلّق|مقلق|عندي examen|الexamens?|"
        r"\b(ma r9adtech|ta3ban|mridh)\b"
    ),
}
_FR_TN_TOOLS: dict[str, str] = {
    "mistakes": (
        r"\b(mes erreurs|mes fautes|quelles erreurs|qu'?est-ce que je rate|je rate (souvent|tout)|"
        r"je me trompe|où je me trompe|confusions?|je confonds)\b|"
        r"غلطاتي|الغلطات متاعي|شنوّة نغلط|شنوة نغلط|وين نغلط|علاش نغلط|نغلط ديما|نخلط|"
        r"اللي نغلط فيهم|\b(chnowa nghlot|win nghlot|nghlot dima)\b"
    ),
    "teach": (
        r"\b(je (ne )?(comprends|comprend|pige|capte) pas|j'?(ai|arrive) pas (à )?comprendre|"
        r"(je n'?ai|j'?ai) pas compris|"
        r"c'?est quoi|qu'?est-ce que (c'?est|signifie|veut dire)|"
        r"explique[sz]?(-moi| moi)?(?! (ton|ce|cette|la) (choix|décision))|"
        r"aide-moi (à comprendre|avec)|je bloque sur|je suis perdu|"
        r"comment (on )?(calcule|trouve|utilise|applique|résout))\b|"
        r"ما فهمتش|مافهمتش|موش فاهم|فهّمني|فهمني|اشرحلي|إشرحلي|شنوّة (هو|هي|معناها)|"
        r"شنوة (هو|هي|معناها)|شنيّة|كيفاش نحسب|كيفاش نعمل|عاودلي|"
        r"\b(ma fhemtech|ma fhemtch|mafhemtech|ma fhmtch|fahhemni|fhemni|chnowa|chneya|"
        r"kifech|3awedli|achra7li)\b"
    ),
    "explain": (
        r"\b(pourquoi (tu as|as-tu|t'as) (choisi|pris)|pourquoi (cet|ce) (exercice|quiz)|"
        r"comment (tu as|as-tu) choisi)\b|علاش اخترت|علاش هذا|\b3lech (ikhtart|hedha)\b"
    ),
    "forecast_range": (
        r"\b(prédi\w*|prévoi\w*|prévision|(quel|combien) sera\b.{0,30}\bmon|"
        r"je vais avoir combien|(exactement|précisément)\b.{0,30}\b(sera|score))\b|"
        r"باش نجيب قدّاش|باش نجيب قداش|شنوّة باش يكون|شنوة باش يكون"
    ),
    "session_history": (
        r"\b(qu'?est-ce que j'?ai (fait|joué)|ma dernière (séance|session)|dernière séance|"
        r"historique des séances)\b|شنوة عملت|شنوّة عملت|آخر séance"
    ),
    "search_memory": (
        r"\b(tu te souviens|qu'?est-ce que tu sais sur moi|tu te rappelles)\b|تتفكّر|تتفكر|"
        r"شنوة تعرف عليّا|شنوة تعرف عليا"
    ),
    "get_history": (
        r"\b(historique|progrès|progression|depuis le début|cette semaine|ce mois|tendance)\b|"
        r"تطوّرت|تطورت|تحسّنت|تحسنت"
    ),
    "read_profile": (
        r"\b(comment je m'?en sors|mon (profil|niveau|score)|mes (résultats|scores|points forts)|"
        r"où j'?en suis)\b|وين وصلت|المستوى متاعي|كيفاش ماشي"
    ),
}
_FR_TN_CONTEST = (
    r"\b(c'?est pas juste|ce n'?est pas juste|c'?est faux|injuste|je ne suis pas d'accord|"
    r"pas d'accord|j'?étais distrait|j'?étais distraite|(il y avait|y avait) du bruit|"
    r"trop de bruit|on m'?a interrompu)\b|موش عادل|موش صحيح|ماهوش صحيح|كان فما حس|"
    r"فما برشا حس|تلهّيت|تلهيت"
)
_FR_TN_NOTES = (
    r"\b(mes|les|nos|de mes|sur mes) (propres )?(notes|slides?|pdfs?|documents?|cours|"
    r"polycopiés?|chapitres?|fichiers?)\b|الnotes متاعي|الcours متاعي|الslides متاعي|"
    r"الdocument متاعي|\b(les notes mte3i|el cours mte3i)\b"
)
_FR_TN_QUIZ = (
    r"\b(quiz|interroge-moi|teste-moi|questions?|exercices?|réviser|entraîne-moi)\b|"
    r"أسئلة|سؤال|تمارين|اختبرني|إختبرني"
)
_FR_TN_QUESTION = (
    r"؟\s*$|^\s*(comment|pourquoi|qu'?est|quel|quelle|quand|est-ce|c'?est quoi|explique|"
    r"علاش|كيفاش|شنوّة|شنوة|شنيّة|وقتاش|قدّاش|قداش|chnowa|kifech|3lech)\b"
)
_FR_TN_PLAY = (
    r"\b(interroge-moi|teste-moi|des questions sur|exercices?|réviser|révision|étudier|"
    r"on commence|commencer|c'?est parti|allons-y|encore un|un autre|vas-y|donne-moi|"
    r"entraîne-moi|on y va)\b|يلّا|يلا|نبداو|نقراو|عطيني|زيد واحد|نحب نقرا|نتمرّن|نتمرن|ابدا|"
    r"\b(yalla|nabdew|a3tini)\b"
)
_FR_TN_SMALL_TALK = (
    r"^\s*(salut|bonjour|bonsoir|merci|d'?accord|ok|cool|super|au revoir|bonne nuit|"
    r"qui es-tu|tu fais quoi)\b|^\s*(عسلامة|السلام|أهلا|اهلا|مرسي|يعيشك|باهي|بالسلامة|"
    r"شكون انت|ahla|3aslema|aslema|yaatik saha|mersi|behi)\b"
)
_FR_TN_DECLINE = (
    r"\b(pas (de |le |la |les |d')?|sans|autre chose que|plutôt pas|j'?en ai marre (de |du |des )?)"
    r"(?P<rest_fr>.{0,40})|(موش|ما نحبش|بلاش|ماعادش)(?P<rest_tn>.{0,40})"
)
_FR_TN_QUICK = (
    r"\b(rapide|court|vite|(j'?ai|seulement) \d+ min\w*|pas le temps)\b|حاجة صغيرة|بالزربة|"
    r"ما عنديش وقت|مزروب"
)
_FR_TN_ELSE = r"\b(autre chose|un autre (exercice|quiz)|pas celui-là)\b|حاجة أخرى|واحد آخر|واحد اخر"


def _also(pattern: re.Pattern[str], extra: str | None) -> re.Pattern[str]:
    return re.compile(f"(?:{pattern.pattern})|(?:{extra})", re.I) if extra else pattern


_KINDS = [(kind, _also(p, _FR_TN_KINDS.get(kind))) for kind, p in _KINDS]
_CHAT_TOOLS = [(tool, _also(p, _FR_TN_TOOLS.get(tool))) for tool, p in _CHAT_TOOLS]
_CONTEST = _also(_CONTEST, _FR_TN_CONTEST)
_NOTES = _also(_NOTES, _FR_TN_NOTES)
_QUIZ_WORDS = _also(_QUIZ_WORDS, _FR_TN_QUIZ)
_QUESTION = _also(_QUESTION, _FR_TN_QUESTION)
_PLAY = _also(_PLAY, _FR_TN_PLAY)
_SMALL_TALK = _also(_SMALL_TALK, _FR_TN_SMALL_TALK)
_QUICK = _also(_QUICK, _FR_TN_QUICK)
_ELSE = _also(_ELSE, _FR_TN_ELSE)
_DECLINE_FR_TN = re.compile(_FR_TN_DECLINE, re.I)


@dataclass(frozen=True)
class Routed:
    intent: Intent
    sure: bool  # the rules alone decided; no model needed


def skills_in(text: str, registry: Registry | None = None) -> list[str]:
    """Concepts named in the text, in the order of the longest, most specific phrases."""
    found: list[str] = []
    patterns = list(SKILL_WORDS)
    if registry is not None:
        patterns = _concept_words(registry) + patterns
        for d in registry.dimensions:
            if d.name.lower() in text.lower() and d.id not in found:
                found.append(d.id)
    for pattern, dim in patterns:
        if pattern.search(text) and dim not in found:
            found.append(dim)
    return found


def game_in(text: str, registry: Registry) -> str | None:
    lowered = text.lower().replace("\u2019", "'")
    # Exercise names in every language ("Quiz : Théorème de Bayes"): students switch.
    names = [(g, g.name) for g in registry.games]
    for locale in ("fr", "tn"):
        names += [(g, g.name) for g in registry.localized(locale).games]
    for game, name in names:  # a story ("the Detective story") is played chapter by chapter
        if (game.available or game.kind == "story") and name.lower() in lowered:
            return game.id
    return None


def declined(text: str, registry: Registry | None = None) -> list[str]:
    """Skills the user turned down: 'not memory today', 'skip the maths'."""
    out: list[str] = []
    rests = [m.group("rest") for m in _DECLINE.finditer(text)]
    rests += [m.group("rest_fr") or m.group("rest_tn") or "" for m in _DECLINE_FR_TN.finditer(text)]
    for rest in rests:
        for dim in skills_in(rest, registry):
            if dim not in out:
                out.append(dim)
    return out


def _kinds(text: str) -> list[IntentKind]:
    return [kind for kind, pattern in _KINDS if pattern.search(text)]


def chat_tool(text: str) -> ToolChoice | None:
    for tool, pattern in _CHAT_TOOLS:
        if tool != "teach" and pattern.search(text):
            return tool
    if next(pattern for tool, pattern in _CHAT_TOOLS if tool == "teach").search(text):
        return "teach"
    return None


def classify(text: str, trigger: str, registry: Registry | None = None) -> Routed:
    """Keyword rules. `sure` is False when nothing matched or two kinds compete."""
    stripped = text.strip().replace("\u2019", "'")  # phones type a curly apostrophe
    if not stripped:
        kind: IntentKind = "proactive" if trigger in ("schedule", "proactive") else "play"
        return Routed(Intent(kind=kind), sure=True)
    game = game_in(stripped, registry) if registry is not None else None
    avoid = declined(stripped, registry)
    kinds = _kinds(stripped)
    without_game = stripped
    if game is not None and registry is not None:
        name = re.escape(registry.game(game).name)
        without_game = re.sub(name, "", stripped.replace("\u2019", "'"), flags=re.I)
    quick = bool(_QUICK.search(without_game))  # "Quick Draw" is a name, not a request

    if "settings" in kinds:
        # "stop suggesting memory this week" pauses a skill; it isn't a request to play.
        pause = re.search(r"\b(stop suggesting|don'?t suggest)\b(?P<rest>.{0,40})", stripped, re.I)
        dims = skills_in(pause.group("rest"), registry) if pause else []
        return Routed(Intent(kind="settings", text=stripped, avoid_dims=dims), sure=True)
    notes = bool(_NOTES.search(stripped))
    if notes and _QUIZ_WORDS.search(stripped):
        # "Quiz me on my slides": questions made from the student's own document.
        dims = skills_in(stripped, registry)
        intent = Intent(
            kind="play", text=stripped, game_id=NOTES_QUIZ, dim=dims[0] if dims else None
        )
        return Routed(intent, sure=True)
    tool = chat_tool(stripped)
    if tool == "teach" and set(kinds) & {
        "twin_chat",
        "experiment",
        "settings",
        "goal",
        "life_context",
    }:
        tool = None
    asks = notes or _QUESTION.search(stripped)
    if (
        tool is None
        and not kinds
        and asks
        and not _SMALL_TALK.search(stripped)
        and not _PLAY.search(stripped)
    ):
        tool = "teach"  # a real question: answer it from their documents and the course
    if tool in ("teach", "mistakes"):
        dims = skills_in(stripped, registry)
        intent = Intent(kind="chat", text=stripped, tool=tool, dim=dims[0] if dims else None)
        return Routed(intent, sure=True)
    if tool == "explain" and not _CONTEST.search(stripped):
        return Routed(Intent(kind="chat", text=stripped, tool=tool), sure=True)
    if _CONTEST.search(stripped):
        return Routed(Intent(kind="chat", text=stripped, tool="contest"), sure=True)
    other = bool(_ELSE.search(stripped))
    if avoid or other:
        # Turning a skill down is still a request to play something (UW3).
        intent = Intent(
            kind="play", text=stripped, avoid_dims=avoid, quick=quick, replace_current=other
        )
        return Routed(intent, sure=True)
    for kind in ("experiment", "twin_chat", "goal"):
        if kind in kinds:
            dims = skills_in(stripped, registry)
            return Routed(
                Intent(kind=kind, text=stripped, dim=dims[0] if dims else None),
                sure=True,
            )
    if tool is not None:
        dims = skills_in(stripped, registry)
        intent = Intent(kind="chat", text=stripped, tool=tool, dim=dims[0] if dims else None)
        return Routed(intent, sure=True)
    if "life_context" in kinds:
        return Routed(Intent(kind="life_context", text=stripped), sure=True)
    if game is not None or _PLAY.search(stripped) or quick:
        dims = skills_in(stripped, registry) if game is None else []
        theme = _THEME.search(stripped.rstrip(".!?"))
        return Routed(
            Intent(
                kind="play",
                text=stripped,
                game_id=game,
                dim=dims[0] if dims else None,
                quick=quick,
                theme=theme.group(1).strip().lower() if theme else None,
            ),
            sure=True,
        )
    if _SMALL_TALK.search(stripped):
        return Routed(Intent(kind="chat", text=stripped), sure=True)
    return Routed(Intent(kind="chat", text=stripped), sure=False)


# The structured call used when the rules aren't sure ------------------------------------------

RouterKind = Literal["play", "chat", "twin_chat", "experiment", "goal", "life_context", "settings"]


class RouterOutput(Contract):
    kind: RouterKind
    tool: ToolChoice | None = Field(
        default=None, description="For chat: the tool that answers it, or null for small talk"
    )
    game: str | None = Field(default=None, description="A game the user named, by its name")
    skill: str | None = Field(default=None, description="A skill the user named, in their words")
    avoid_skill: str | None = Field(default=None, description="A skill the user turned down")
    quick: bool = False


ROUTER_PROMPT = """You route messages for Lodestar, a study coach for a university course.
Pick the kind:
- play: wants to practise now (a quiz, an exercise), names a concept to practise, or turns one
  down ("not counting today")
- chat: anything else said to Lodestar. tool = teach (doesn't understand a concept of the course
  or asks what something means), mistakes (asks what they keep getting wrong), explain (asks why
  Lodestar chose something),
  read_profile (asks about their skills now), get_history (asks how a skill changed over time),
  search_memory (asks what Lodestar remembers about them), session_history (asks which games they
  played or how a past session went), forecast_range (asks what a skill or score will be in the
  future), contest (disagrees with a result, or says a distraction spoiled it), or null.
- twin_chat: asks their Twin about their own patterns (best time of day, what helps them)
- experiment: wants to test something about themselves over several sessions
- goal: wants to reach a level in a concept by a date (an exam)
- life_context: tells how their life is going (sleep, exams, stress, feeling unwell)
- settings: wants to change the coach, difficulty mode, camera or microphone
Messages may be in English, French or Tunisian Arabic (Derja, in Arabic script or in Latin
letters such as "ma fhemtech"), often mixed with French course terms. Route them the same way.
Reply with one JSON object and nothing else, shaped like:
{"kind": "play", "tool": null, "game": null, "skill": null, "avoid_skill": null, "quick": false}
(tool: one of the tools above or null; game, skill and
avoid_skill: the user's words or null; quick: true if they want something short)"""


def from_router(out: RouterOutput, text: str, registry: Registry) -> Intent:
    game = game_in(out.game, registry) if out.game else None
    dims = skills_in(out.skill or "", registry)
    avoid = skills_in(out.avoid_skill or "", registry)
    kind: IntentKind = "play" if avoid and out.kind == "chat" else out.kind
    return Intent(
        kind=kind,
        text=text,
        game_id=game if kind == "play" else None,
        dim=dims[0] if dims else None,
        avoid_dims=avoid,
        quick=out.quick,
        tool=out.tool if kind == "chat" else None,
        source="llm",
    )


async def route(
    text: str,
    trigger: str,
    registry: Registry,
    llm: LlmFactory,
    user_id: UUID,
    selection: LlmSelection,
) -> tuple[Intent, list[str]]:
    """Rules first; when they aren't sure, one structured model call. Without a model, the rules'
    best guess stands. Returns the intent and any fallback taken."""
    routed = classify(text, trigger, registry)
    if routed.sure:
        return routed.intent, []
    messages = [SystemMessage(ROUTER_PROMPT), HumanMessage(text)]
    try:
        out = await llm.structured(user_id, selection, messages, RouterOutput)
    except NoModelAvailable as exc:
        return routed.intent, [*exc.degraded, "router:llm->rules"]
    return from_router(out.value, text, registry), list(out.degraded)

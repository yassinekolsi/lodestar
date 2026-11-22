"""What the profile as a whole says should change the plan (docs/plan/07, 13): a skill that has
stopped moving gets a new format, and a split profile gets two tracks at their own levels. The
agent's plan_next and the dashboard read the same answer from here."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from backend import i18n
from backend.contracts.views import (
    DimensionView,
    PatternsView,
    PlateauView,
    SplitTrackView,
    SplitView,
)
from backend.db import tables as t
from backend.db.twin_store import read_twin
from backend.registry.models import Game, Registry
from backend.scoring.kalman_elo import Belief
from backend.scoring.levels import TARGET_P, next_level
from backend.scoring.norms import Norms
from backend.scoring.patterns import (
    PLATEAU_MAX_PERCENT,
    HistoryPoint,
    PlateauSpan,
    find_plateau,
    find_split,
)

# What to try differently when a concept is stuck, by chapter of the course: a change of
# approach, not only of exercise (docs/plan/19).
STRATEGY = {
    "chapter_1": "Write out the sample space or a small list of outcomes before you count; most "
    "counting mistakes show up as soon as the list is on paper.",
    "chapter_2": "Turn every probability into counts: imagine 1,000 people, fill a two-way table "
    "or a tree, and read the answer off the counts. Say which group you are dividing by.",
    "chapter_3": "Write the distribution as a small table of values and probabilities first, then "
    "compute from the table, one column at a time.",
    "chapter_4": "Draw the curve first: mark the mean and one and two standard deviations on each "
    "side, and shade the area the question asks for before you compute anything.",
}
DEFAULT_STRATEGY = (
    "Explain the idea out loud in your own words before answering, then check it on one example."
)
STRATEGY_FR = {
    "chapter_1": "Écris l'univers ou une petite liste de résultats avant de compter ; la plupart "
    "des erreurs de dénombrement se voient dès que la liste est sur papier.",
    "chapter_2": "Transforme chaque probabilité en effectifs : imagine 1,000 personnes, remplis un "
    "tableau à double entrée ou un arbre, et lis la réponse sur les effectifs. Dis par quel "
    "groupe tu divises.",
    "chapter_3": "Écris d'abord la loi comme un petit tableau de valeurs et de probabilités, puis "
    "calcule à partir du tableau, une colonne à la fois.",
    "chapter_4": "Dessine d'abord la courbe : marque la moyenne et un et deux écarts-types de "
    "chaque côté, et hachure l'aire demandée avant de calculer quoi que ce soit.",
}
DEFAULT_STRATEGY_FR = (
    "Explique l'idée à voix haute avec tes mots avant de répondre, puis vérifie-la sur un exemple."
)
STRATEGY_TN = {
    "chapter_1": "اكتب الunivers ولا ليستة صغيرة متاع النتائج قبل ما تحسب؛ أغلب غلطات "
    "الdénombrement يبانو أول ما الليستة تولّي على الورقة.",
    "chapter_2": "بدّل كل probabilité لأعداد : تخيّل 1,000 عبد، عمّر tableau à double entrée ولا "
    "arbre، واقرا الجواب من الأعداد. قول على أما groupe قاعد تقسم.",
    "chapter_3": "اكتب الloi في الأول كيف tableau صغير فيه القيم والprobabilités، ومن بعد احسب من "
    "الtableau، colonne بcolonne.",
    "chapter_4": "ارسم الcourbe في الأول: علّم الmoyenne وécart-type واحد واثنين من كل جيهة، "
    "وظلّل الaire اللي يطلبها السؤال قبل ما تحسب أي حاجة.",
}
DEFAULT_STRATEGY_TN = "فسّر الفكرة بصوت عالي بكلامك قبل ما تجاوب، ومن بعد ثبّتها على مثال واحد."


def strategy(group: str) -> str:
    """The change of approach for a stuck concept, in the request's language."""
    loc = i18n.current()
    table, default = {
        "fr": (STRATEGY_FR, DEFAULT_STRATEGY_FR),
        "tn": (STRATEGY_TN, DEFAULT_STRATEGY_TN),
    }.get(loc, (STRATEGY, DEFAULT_STRATEGY))
    return table.get(group, default)


ADVANCED_TARGET = TARGET_P["push"]
FOUNDATION_TARGET = TARGET_P["chill"]
MAX_PLATEAUS = 3


async def last_played(conn: AsyncConnection, user_id: UUID) -> dict[str, datetime]:
    rows = await conn.execute(
        select(t.rounds.c.game_id, func.max(t.rounds.c.started_at))
        .where(t.rounds.c.user_id == user_id)
        .group_by(t.rounds.c.game_id)
    )
    return {r[0]: r[1] for r in rows}


def freshest(options: Sequence[Game], played: Mapping[str, datetime]) -> Game | None:
    """The game played longest ago, a never-played one first."""
    never = datetime.min.replace(tzinfo=UTC)
    return min(options, key=lambda g: played.get(g.id, never), default=None)


def new_format(
    dim: str,
    registry: Registry,
    by_dim: Mapping[str, Sequence[Game]],
    played: Mapping[str, datetime],
) -> tuple[Game | None, bool]:
    """A different way to practise a stuck skill: the skill's own least-recent game, or, when it
    has only one, the least-recent game of its family. Returns the game and whether it's the
    same skill."""
    own = list(by_dim.get(dim, []))
    usual = max(own, key=lambda g: played.get(g.id, datetime.min.replace(tzinfo=UTC)), default=None)
    others = [g for g in own if usual is None or g.id != usual.id]
    if others:
        return freshest(others, played), True
    group = registry.dimension(dim).group
    nearby = {
        g.id: g
        for d, games in by_dim.items()
        if d != dim and registry.dimension(d).group == group
        for g in games
    }
    return freshest(list(nearby.values()), played), False


async def read_patterns(
    conn: AsyncConnection,
    user_id: UUID,
    registry: Registry,
    norms: Norms,
    by_dim: Mapping[str, Sequence[Game]],
    now: datetime | None = None,
) -> PatternsView:
    now = now or datetime.now(UTC)
    twin = await read_twin(conn, user_id, now=now, norms=norms)
    styles = {d.id for d in registry.dimensions if d.style}
    views = [v for v in twin.dims if v.n > 0 and v.dim not in styles and v.dim in by_dim]
    played = await last_played(conn, user_id)

    points: dict[str, list[HistoryPoint]] = {}
    for h in twin.history:
        points.setdefault(h.dim, []).append(HistoryPoint(h.day, h.mu, h.n))
    spans: list[tuple[DimensionView, PlateauSpan]] = []
    for v in views:
        span = find_plateau(points.get(v.dim, []), now.date())
        if span is not None and v.percent < PLATEAU_MAX_PERCENT:
            spans.append((v, span))
    spans.sort(key=lambda found: found[1].swing)  # the flattest first
    plateaus: list[PlateauView] = []
    for v, span in spans[:MAX_PLATEAUS]:
        game, same = new_format(v.dim, registry, by_dim, played)
        definition = registry.dimension(v.dim)
        plateaus.append(
            PlateauView(
                dim=v.dim,
                name=definition.name,
                started=span.start,
                days=span.days,
                answers=span.answers,
                percent=v.percent,
                low=v.percent_low,
                high=v.percent_high,
                game_id=game.id if game else None,
                game_name=registry.game(game.id).name if game else None,
                same_skill=same,
                strategy=strategy(definition.group),
            )
        )

    split = None
    found = find_split(views)
    if found is not None:

        def track(
            v: DimensionView, kind: Literal["advanced", "foundation"], target: float
        ) -> SplitTrackView:
            game = freshest(by_dim.get(v.dim, []), played)
            return SplitTrackView(
                dim=v.dim,
                name=registry.dimension(v.dim).name,
                track=kind,
                percent=v.percent,
                low=v.percent_low,
                high=v.percent_high,
                level=next_level(Belief(v.mu, v.sigma), target),
                target_p=target,
                game_id=game.id if game else None,
                game_name=registry.game(game.id).name if game else None,
            )

        split = SplitView(
            gap=round(found.strong.percent - found.weak.percent, 1),
            advanced=track(found.strong, "advanced", ADVANCED_TARGET),
            foundation=track(found.weak, "foundation", FOUNDATION_TARGET),
        )
    return PatternsView(plateaus=plateaus, split=split)

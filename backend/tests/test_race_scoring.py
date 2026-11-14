import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "race-scoring-tests-only-secret-not-for-production")

from app.services.race import (
    Racer,
    RaceText,
    build_results,
    ideal_time_ms,
    race_points,
    time_limit_ms,
)
from app.text_enums import Difficulty, Language

CONTENT = "x" * 100


def text(difficulty=Difficulty.EASY, ideal=20_000):
    return RaceText(1, CONTENT, Language.SPA, difficulty, ideal)


class RaceScoringTests(unittest.TestCase):
    def test_matches_the_documented_example(self):
        # Media, ideal 30 s, 40 s con 95% y 2° lugar = 95,5 puntos.
        points = race_points(
            ideal_ms=30_000, time_ms=40_000, precision_pct=95,
            difficulty=Difficulty.MEDIUM, position=2,
        )
        self.assertAlmostEqual(points, 95.5)

    def test_difficulty_multiplies_the_base_score(self):
        scores = [
            race_points(ideal_ms=30_000, time_ms=30_000, precision_pct=100, difficulty=level)
            for level in (Difficulty.EASY, Difficulty.MEDIUM, Difficulty.ADVANCED)
        ]
        self.assertEqual([round(score, 6) for score in scores], [100, 120, 150])

    def test_position_and_record_bonuses(self):
        def points(**extra):
            return race_points(
                ideal_ms=30_000, time_ms=30_000, precision_pct=100,
                difficulty=Difficulty.EASY, **extra,
            )

        self.assertEqual([points(position=p) - points() for p in (1, 2, 3, 4)], [20, 10, 5, 0])
        self.assertEqual(points(position=1, is_record=True) - points(position=1), 30)

    def test_unfinished_players_get_a_proportional_score_without_bonuses(self):
        full = race_points(
            ideal_ms=30_000, time_ms=60_000, precision_pct=90, difficulty=Difficulty.MEDIUM,
        )
        half = race_points(
            ideal_ms=30_000, time_ms=60_000, precision_pct=90, difficulty=Difficulty.MEDIUM,
            progress=0.5, position=1, is_record=True,
        )
        self.assertAlmostEqual(half, full / 2)

    def test_ideal_time_is_the_best_mark_or_sixty_ppm(self):
        self.assertEqual(ideal_time_ms("a" * 150, None), 30_000)
        self.assertEqual(ideal_time_ms("a" * 150, 21_500), 21_500)

    def test_time_limit_is_twice_the_ideal_unless_the_room_sets_one(self):
        self.assertEqual(time_limit_ms(30_000, None), 60_000)
        self.assertEqual(time_limit_ms(30_000, 45), 45_000)

    def test_ranks_finishers_by_time_then_the_rest_by_progress(self):
        results = build_results(
            text(),
            40_000,
            [
                Racer(1, "lenta", typed=100, errors=5, finished_ms=30_000),
                Racer(2, "a medias", typed=50),
                Racer(3, "rapida", typed=100, finished_ms=25_000),
                Racer(4, "casi", typed=80, errors=20),
                Racer(5, "ausente"),
            ],
        )
        self.assertEqual([r.username for r in results], ["rapida", "lenta", "casi", "a medias", "ausente"])
        self.assertEqual([r.position for r in results], [1, 2, 3, 4, 5])
        self.assertEqual([r.finished for r in results], [True, True, False, False, False])
        rapida, lenta, casi, a_medias, ausente = results
        # 100 × (20/25) × 1.0 + 20 por el primer lugar.
        self.assertEqual((rapida.time_ms, rapida.ppm, rapida.precision_pct, rapida.score), (25_000, 48, 100, 100))
        # 100 × (20/30) × 0.952 + 10 = 73,5.
        self.assertEqual((lenta.precision_pct, lenta.score), (95.2, 73))
        # Sin terminar: corre el tiempo completo y puntúa según su avance.
        self.assertEqual((casi.time_ms, casi.progress, casi.precision_pct, casi.score), (40_000, 0.8, 80, 32))
        self.assertEqual((a_medias.progress, a_medias.score), (0.5, 25))
        self.assertEqual((ausente.ppm, ausente.progress, ausente.score), (0, 0, 0))

    def test_only_an_accurate_winner_faster_than_the_ideal_sets_a_record(self):
        def flags(*racers, ideal=20_000):
            return [r.is_record for r in build_results(text(ideal=ideal), 40_000, list(racers))]

        fast = Racer(1, "a", typed=100, finished_ms=15_000)
        second = Racer(2, "b", typed=100, finished_ms=16_000)
        self.assertEqual(flags(fast, second), [True, False])
        self.assertEqual(flags(Racer(1, "a", typed=100, finished_ms=20_000)), [False])
        sloppy = Racer(1, "a", typed=100, errors=40, finished_ms=15_000)
        self.assertEqual(flags(sloppy), [False])
        self.assertEqual(flags(Racer(1, "a", typed=90)), [False])
        winner = build_results(text(), 40_000, [fast])[0]
        # 100 × (20/15) + 20 de posición + 30 de récord = 183,3.
        self.assertEqual(winner.score, 183)


if __name__ == "__main__":
    unittest.main()

"""Carrera con varios clientes simultáneos sobre un servidor real (T-03.11).

Levanta uvicorn en un hilo y conecta 10 clientes WebSocket de verdad: mide
cuánto tarda el avance de un jugador en llegar a los demás.
"""

import asyncio
import json
import os
import socket
import tempfile
import threading
import time
import unittest
from unittest import mock

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "race-load-tests-only-secret-not-for-production")

try:
    import uvicorn
    import websockets
except ImportError as error:  # pragma: no cover
    raise unittest.SkipTest(f"requiere uvicorn[standard]: {error}")

import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.deps import get_db
from app.main import app
from app.models import Difficulty, Game, GameParticipant, Language, Text, User
from app.security import create_access_token
from app.ws import rooms as rooms_ws

PLAYERS = 10
STEPS = 30
MAX_LATENCY_MS = 200
CONTENT = "la practica diaria mejora la velocidad al escribir con cuidado"


class RaceLoadTests(unittest.TestCase):
    def setUp(self):
        self.prepare_database()
        self.addCleanup(rooms_ws.hub.rooms.clear)
        patcher = mock.patch.object(rooms_ws, "COUNTDOWN_S", 0.2)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.start_server()

    def prepare_database(self):
        folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(folder.cleanup)
        self.engine = create_engine(
            f"sqlite+pysqlite:///{folder.name}/load.db",
            connect_args={"check_same_thread": False},
        )
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            users = [
                User(username=f"racer{n}", email=f"racer{n}@example.test", hashed_password="x")
                for n in range(PLAYERS)
            ]
            db.add_all(users)
            db.add(Text(content=CONTENT, language=Language.SPA, difficulty=Difficulty.EASY))
            db.commit()
            self.user_ids = [user.id for user in users]
        self.tokens = [create_access_token(user_id) for user_id in self.user_ids]

        def test_db():
            with self.sessions() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        self.addCleanup(app.dependency_overrides.pop, get_db)

    def start_server(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning")
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        def stop_server():
            server.should_exit = True
            thread.join(10)

        self.addCleanup(stop_server)
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(server.started, "el servidor no levantó")

    def create_room(self):
        base = f"http://127.0.0.1:{self.port}/api/v1/rooms"
        with httpx.Client() as http:
            created = http.post(
                base,
                json={"language": "spa", "difficulty": "easy"},
                headers={"Authorization": f"Bearer {self.tokens[0]}"},
            )
            self.assertEqual(created.status_code, 201, created.text)
            code = created.json()["code"]
            for token in self.tokens[1:]:
                joined = http.post(
                    f"{base}/{code}/join", headers={"Authorization": f"Bearer {token}"}
                )
                self.assertEqual(joined.status_code, 200, joined.text)
        return code

    async def race(self, code):
        url = f"ws://127.0.0.1:{self.port}/api/v1/ws/rooms/{code}"
        sent, latencies, endings = {}, [], []

        async def player(index, token):
            async with websockets.connect(url) as ws:

                async def send(**message):
                    await ws.send(json.dumps(message))

                async def type_text(length):
                    for step in range(1, STEPS + 1):
                        typed = length * step // STEPS
                        # La clave identifica el mensaje al medir su llegada.
                        sent[(index, typed)] = time.perf_counter()
                        await send(type="progress", typed=typed, errors=index)
                        await asyncio.sleep(0.01)

                await send(type="auth", token=token)
                if index:
                    await send(type="ready", ready=True)
                started = False
                async for raw in ws:
                    received = time.perf_counter()
                    message = json.loads(raw)
                    kind = message["type"]
                    if kind == "room_state" and index == 0 and not started:
                        members = message["room"]["members"]
                        # El anfitrión inicia cuando todos están conectados y listos.
                        if len(members) == PLAYERS and all(
                            m["connected"] and (m["isReady"] or m["isHost"]) for m in members
                        ):
                            started = True
                            await send(type="start")
                    elif kind == "race_start":
                        length = len(message["text"]["content"])
                        typing = asyncio.create_task(type_text(length))
                    elif kind == "progress_update":
                        sender = self.user_ids.index(message["userId"])
                        key = (sender, round(message["progress"] * length))
                        latencies.append((received - sent[key]) * 1000)
                    elif kind == "race_end":
                        await typing
                        endings.append(message)
                        return

        await asyncio.wait_for(
            asyncio.gather(*(player(i, token) for i, token in enumerate(self.tokens))), 60
        )
        return latencies, endings

    def test_ten_players_race_with_low_latency(self):
        code = self.create_room()
        latencies, endings = asyncio.run(self.race(code))

        self.assertEqual(len(endings), PLAYERS)
        results = endings[0]["results"]
        self.assertTrue(all(ending["results"] == results for ending in endings))
        self.assertEqual([r["position"] for r in results], list(range(1, PLAYERS + 1)))
        self.assertTrue(all(r["finished"] and r["progress"] == 1 for r in results))

        # Cada avance llega a los otros 9 jugadores.
        self.assertEqual(len(latencies), PLAYERS * (PLAYERS - 1) * STEPS)
        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        print(
            f"\n  latencia de progress_update con {PLAYERS} clientes: "
            f"mediana={latencies[len(latencies) // 2]:.1f} ms, p95={p95:.1f} ms, "
            f"max={latencies[-1]:.1f} ms ({len(latencies)} mensajes)"
        )
        self.assertLess(p95, MAX_LATENCY_MS)

        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Game)), 1)
            self.assertEqual(
                db.scalar(select(func.count()).select_from(GameParticipant)), PLAYERS
            )


if __name__ == "__main__":
    unittest.main()

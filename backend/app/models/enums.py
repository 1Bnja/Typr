from enum import Enum
from sqlalchemy import Enum as SAEnum

def pg_enum(enum_cls: type[Enum], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        create_type=False,
        native_enum=True,
        values_callable=lambda cls: [member.value for member in cls],
    )

class RoomType(str, Enum):
    PRIVATE = "private"
    QUICK = "quick"

class GameMode(str, Enum):
    SINGLEPLAYER = "singleplayer"
    MULTIPLAYER = "multiplayer"

class RoomStatus(str, Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in progress"
    FINISHED = "finished"

class Language(str, Enum):
    SPA = "spa"
    ENG = "eng"

class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    ADVANCED = "advanced"
    EXPERT = "expert"

ROOM_TYPE_ENUM = pg_enum(RoomType, "room_type")
GAME_MODE_ENUM = pg_enum(GameMode, "game_mode")
ROOM_STATUS_ENUM = pg_enum(RoomStatus, "room_status")
LANGUAGE_ENUM = pg_enum(Language, "text_language")
DIFFICULTY_ENUM = pg_enum(Difficulty, "difficulty")

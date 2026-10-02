-- ============================================================
-- Typr - esquema inicial
-- ============================================================
-- Convenciones:
--   * Todos los identificadores van en ingles: tablas, columnas,
--     tipos enumerados, constraints e indices.
--   * Los textos que ve el usuario siguen en espanol; el idioma de la
--     interfaz no tiene nada que ver con el nombre de las columnas.
--   * hashed_password guarda el hash bcrypt, no la contrasena en claro.
-- ============================================================

-- 1. Tipos enumerados
CREATE TYPE room_type AS ENUM ('private', 'quick');
CREATE TYPE game_mode AS ENUM ('singleplayer', 'multiplayer');
CREATE TYPE room_status AS ENUM ('waiting', 'in progress', 'finished');
CREATE TYPE text_language AS ENUM ('spa', 'eng');
CREATE TYPE difficulty AS ENUM ('easy', 'medium', 'advanced', 'expert');

-- 2. Tabla users
--    hashed_password necesita VARCHAR(72): bcrypt devuelve 60 chars y
--    los CHAR(n) rellenan con espacios a la derecha, lo que rompe
--    bcrypt.checkpw en el login.
CREATE TABLE users (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(20) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(72) NOT NULL,
    avatar_url VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabla texts
CREATE TABLE texts (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    content TEXT NOT NULL,
    language text_language NOT NULL,
    difficulty difficulty NOT NULL,
    ideal_time_ms INT,
    record_user_id INT,
    FOREIGN KEY (record_user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 4. Tabla rooms
CREATE TABLE rooms (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    host_id INT NOT NULL,
    type room_type DEFAULT 'private',
    language text_language NOT NULL,
    difficulty difficulty NOT NULL,
    status room_status DEFAULT 'waiting',
    FOREIGN KEY (host_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 5. Tabla miembros de la sala
CREATE TABLE room_members (
    room_id INT NOT NULL,
    member_id INT NOT NULL,
    PRIMARY KEY (room_id, member_id),
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 6. Tabla games
CREATE TABLE games (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    room_id INT DEFAULT NULL,
    text_id INT NOT NULL,
    mode game_mode DEFAULT 'singleplayer',
    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ DEFAULT NULL,
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE SET NULL,
    FOREIGN KEY (text_id) REFERENCES texts(id) ON DELETE RESTRICT
);

-- 7. Tabla game_participants
--    El puntaje por minuto se llama `ppm` (palabras por minuto) porque en
--    el dominio del juego ya se usa esa sigla; en ingles seria `wpm`.
CREATE TABLE game_participants (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    game_id INT NOT NULL,
    user_id INT NOT NULL,
    time_ms INT DEFAULT NULL,
    ppm INT DEFAULT NULL,
    precision_pct REAL DEFAULT NULL,
    progress REAL DEFAULT NULL,
    position INT DEFAULT NULL,
    score INT DEFAULT NULL,
    UNIQUE (game_id, user_id),
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 8. Indices para las consultas mas frecuentes
--    (las columnas UNIQUE ya tienen su indice implicito)
CREATE INDEX ix_texts_language_difficulty ON texts (language, difficulty);
CREATE INDEX ix_rooms_status ON rooms (status);
CREATE INDEX ix_room_members_member_id ON room_members (member_id);
CREATE INDEX ix_games_room_id ON games (room_id);
CREATE INDEX ix_games_text_id ON games (text_id);
CREATE INDEX ix_game_participants_user_id ON game_participants (user_id);

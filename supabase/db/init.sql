-- 1. Tipos enumerados
CREATE TYPE tipo_salas AS ENUM ('privada', 'rápida');
CREATE TYPE modos AS ENUM ('individual', 'multijugador');
CREATE TYPE estado_sala AS ENUM ('esperando', 'en curso', 'finalizada');
CREATE TYPE idiomas_disponibles AS ENUM ('esp', 'eng');
CREATE TYPE dificultades AS ENUM ('fácil', 'medio', 'avanzado', 'experto');

-- 2. Tabla usuario
CREATE TABLE usuario (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(30) NOT NULL UNIQUE,
    password CHAR(64) NOT NULL,
    avatar_data BYTEA,
    avatar_mime VARCHAR(50) DEFAULT 'image/jpeg',
    fecha_registro DATE DEFAULT CURRENT_DATE
);

-- 3. Tabla textos
CREATE TABLE textos (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contenido TEXT NOT NULL,
    idioma idiomas_disponibles NOT NULL,
    dificultad dificultades NOT NULL,
    t_ideal_ms INT,
    record_usr INT,
    FOREIGN KEY (record_usr) REFERENCES usuario(id) ON DELETE SET NULL
);

-- 4. Tabla salas
CREATE TABLE salas (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    anfitrion INT NOT NULL,
    tipo tipo_salas DEFAULT 'privada',
    idioma idiomas_disponibles NOT NULL,
    dificultad dificultades NOT NULL,
    estado estado_sala DEFAULT 'esperando',
    FOREIGN KEY (anfitrion) REFERENCES usuario(id) ON DELETE CASCADE
);

-- 5. Tabla miembros de la sala
CREATE TABLE sala_miembro (
    sala INT NOT NULL,
    miembro INT NOT NULL,
    PRIMARY KEY (sala, miembro),
    FOREIGN KEY (sala) REFERENCES salas(id) ON DELETE CASCADE,
    FOREIGN KEY (miembro) REFERENCES usuario(id) ON DELETE CASCADE
);

-- 6. Tabla partida
CREATE TABLE partida (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sala INT DEFAULT NULL,
    texto INT NOT NULL,
    modo modos DEFAULT 'individual',
    tiempo_inicio TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    tiempo_fin TIMESTAMPTZ DEFAULT NULL,
    FOREIGN KEY (sala) REFERENCES salas(id) ON DELETE SET NULL,
    FOREIGN KEY (texto) REFERENCES textos(id) ON DELETE RESTRICT
);

-- 7. Tabla participación en partida
CREATE TABLE participacion_partida (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    partida INT NOT NULL,
    usuario INT NOT NULL,
    tiempo_ms INT DEFAULT NULL,
    ppm INT DEFAULT NULL,
    precision_pct REAL DEFAULT NULL,
    progreso REAL DEFAULT NULL,
    posicion INT DEFAULT NULL,
    puntaje INT DEFAULT NULL,
    UNIQUE (partida, usuario),
    FOREIGN KEY (partida) REFERENCES partida(id) ON DELETE CASCADE,
    FOREIGN KEY (usuario) REFERENCES usuario(id) ON DELETE CASCADE
);


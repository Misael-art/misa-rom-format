# Schema do Banco de Dados

Este documento descreve o schema atual do banco de dados SQLite (`data/default.db`) utilizado pelo projeto Mega_Emu_DataBase_ROMs.

## Tabelas

### `app_info`
Armazena informações gerais sobre a aplicação.

| Coluna     | Tipo    | Restrições    | Descrição                               |
| :--------- | :------ | :------------ | :-------------------------------------- |
| `key`      | TEXT    | PRIMARY KEY   | Chave única para a informação           |
| `value`    | TEXT    | NOT NULL      | Valor associado à chave                 |

### `games`
Armazena informações sobre os jogos.

| Coluna         | Tipo       | Restrições    | Descrição                               |
| :------------- | :--------- | :------------ | :-------------------------------------- |
| `id`           | INTEGER    | PRIMARY KEY   | Identificador único do jogo             |
| `name`         | TEXT       | NOT NULL      | Nome do jogo                            |
| `description`  | TEXT       |               | Descrição detalhada do jogo             |
| `platform`     | TEXT       |               | Plataforma do jogo (ex: "PC Engine")    |
| `year`         | TEXT       |               | Ano de lançamento do jogo               |
| `manufacturer` | TEXT       |               | Fabricante do jogo                      |
| `created_at`   | TIMESTAMP  |               | Data e hora de criação do registro      |
| `updated_at`   | TIMESTAMP  |               | Data e hora da última atualização       |

### `roms`
Armazena informações sobre as ROMs.

| Coluna         | Tipo      | Restrições    | Descrição                               |
| :------------- | :-------- | :------------ | :-------------------------------------- |
| `id`           | INTEGER   | PRIMARY KEY   | Identificador único da ROM              |
| `game_id`      | INTEGER   | NOT NULL      | ID do jogo ao qual a ROM pertence (FK)  |
| `name`         | TEXT      | NOT NULL      | Nome da ROM                             |
| `size`         | INTEGER   | NOT NULL      | Tamanho da ROM em bytes                 |
| `crc32`        | TEXT      | NOT NULL      | Hash CRC32 da ROM                       |
| `md5`          | TEXT      | NOT NULL      | Hash MD5 da ROM                         |
| `sha1`         | TEXT      | NOT NULL      | Hash SHA1 da ROM                        |
| `status`       | TEXT      |               | Status da ROM (ex: "active", "corrupt") |
| `created_at`   | TIMESTAMP |               | Data e hora de criação do registro      |
| `updated_at`   | TIMESTAMP |               | Data e hora da última atualização       |
| `rom_filename` | TEXT      |               | Nome do arquivo da ROM                  |

### `sqlite_sequence`
Tabela interna do SQLite para gerenciar sequências de IDs automáticos.

| Coluna | Tipo | Restrições | Descrição                               |
| :----- | :--- | :--------- | :-------------------------------------- |
| `name` |      |            | Nome da tabela associada à sequência    |
| `seq`  |      |            | Último valor da sequência (próximo ID)  |

## Views

### `active_roms`
Exibe todas as ROMs com status 'active' ou NULL.

```sql
CREATE VIEW active_roms AS
SELECT * FROM roms
WHERE status = 'active' OR status IS NULL
```

### `roms_by_game`
Agrupa ROMs por jogo, mostrando a contagem de ROMs, tamanho total e status.

```sql
CREATE VIEW roms_by_game AS
SELECT
    g.id as game_id,
    g.name as game_name,
    COUNT(r.id) as rom_count,
    SUM(r.size) as total_size,
    GROUP_CONCAT(DISTINCT r.status) as statuses
FROM games g
LEFT JOIN roms r ON g.id = r.game_id
GROUP BY g.id, g.name
```

### `roms_by_platform`
Agrupa ROMs por plataforma, mostrando a contagem de ROMs, jogos e tamanho total.

```sql
CREATE VIEW roms_by_platform AS
SELECT
    g.platform,
    COUNT(r.id) as rom_count,
    COUNT(DISTINCT g.id) as game_count,
    SUM(r.size) as total_size
FROM games g
LEFT JOIN roms r ON g.id = r.game_id
WHERE g.platform IS NOT NULL
GROUP BY g.platform
```

## Triggers

### `trig_update_roms_timestamp`
Atualiza a coluna `updated_at` da tabela `roms` automaticamente após cada atualização.

```sql
CREATE TRIGGER trig_update_roms_timestamp
AFTER UPDATE ON roms
FOR EACH ROW
BEGIN
    UPDATE roms SET updated_at = datetime('now') WHERE id = NEW.id;
END
```

### `trig_update_games_timestamp`
Atualiza a coluna `updated_at` da tabela `games` automaticamente após cada atualização.

```sql
CREATE TRIGGER trig_update_games_timestamp
AFTER UPDATE ON games
FOR EACH ROW
BEGIN
    UPDATE games SET updated_at = datetime('now') WHERE id = NEW.id;
END
```

### `trig_validate_rom_data`
Impede a inserção de ROMs com o campo `name` vazio ou NULL.

```sql
CREATE TRIGGER trig_validate_rom_data
BEFORE INSERT ON roms
FOR EACH ROW
WHEN NEW.name IS NULL OR NEW.name = ''
BEGIN
    SELECT RAISE(ABORT, 'Nome da ROM é obrigatório');
END
```

## Índices

| Nome do Índice             | Tabela    | Colunas Indexadas      | Propósito                                       |
| :------------------------- | :-------- | :--------------------- | :---------------------------------------------- |
| `sqlite_autoindex_app_info_1` | `app_info` | `key`                  | Otimização de busca por chave na tabela `app_info`. |
| `idx_games_name`           | `games`   | `name`                 | Otimização de busca por nome de jogo.           |
| `idx_roms_game_id`         | `roms`    | `game_id`              | Otimização de junções e buscas por `game_id`.   |
| `idx_roms_name`            | `roms`    | `name`                 | Otimização de busca por nome de ROM.            |
| `idx_roms_status`          | `roms`    | `status`               | Otimização de busca por status de ROM.          |
| `idx_roms_filename`        | `roms`    | `rom_filename`         | Otimização de busca por nome de arquivo de ROM. |
| `idx_roms_filename_status` | `roms`    | `rom_filename`, `status` | Otimização de buscas combinadas por nome de arquivo e status. |
| `idx_games_platform_year`  | `games`   | `platform`, `year`     | Otimização de buscas combinadas por plataforma e ano. |
| `idx_roms_game_status`     | `roms`    | `game_id`, `status`    | Otimização de buscas combinadas por ID de jogo e status. |
| `idx_roms_sha1`            | `roms`    | `sha1`                 | Otimização de busca por hash SHA1.              |
| `idx_roms_md5`             | `roms`    | `md5`                  | Otimização de busca por hash MD5.               |
| `idx_roms_crc32`           | `roms`    | `crc32`                | Otimização de busca por hash CRC32.             |

## Diagrama ER Simples

```mermaid
erDiagram
    app_info {
        TEXT key PK
        TEXT value
    }

    games {
        INTEGER id PK
        TEXT name
        TEXT description
        TEXT platform
        TEXT year
        TEXT manufacturer
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    roms {
        INTEGER id PK
        INTEGER game_id FK
        TEXT name
        INTEGER size
        TEXT crc32
        TEXT md5
        TEXT sha1
        TEXT status
        TIMESTAMP created_at
        TIMESTAMP updated_at
        TEXT rom_filename
    }

    games ||--o{ roms : "contém"
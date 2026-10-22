-- ===========================================================================
-- 车牌识别与停车场管理系统 —— 数据库表结构
-- ===========================================================================

-- 用户表（管理员 / 操作员）
CREATE TABLE IF NOT EXISTS users (
    id        INTEGER  PRIMARY KEY AUTOINCREMENT,
    username  TEXT     NOT NULL UNIQUE,
    password  TEXT     NOT NULL,
    role      TEXT     NOT NULL DEFAULT 'operator', -- 'admin' / 'operator'
    real_name TEXT,
    created_at TEXT    DEFAULT (datetime('now', 'localtime'))
);

-- 停车场车位状态
CREATE TABLE IF NOT EXISTS parking_lot (
    id           INTEGER PRIMARY KEY,           -- 这里只放一行 id=1，作为配置
    total_spots  INTEGER NOT NULL,
    used_spots   INTEGER NOT NULL DEFAULT 0
);

-- 停车记录
CREATE TABLE IF NOT EXISTS parking_records (
    id              INTEGER  PRIMARY KEY AUTOINCREMENT,
    plate_no        TEXT     NOT NULL,            -- 车牌号
    vehicle_type    TEXT     NOT NULL DEFAULT '小型车',
    spot_no         TEXT     NOT NULL,            -- 分配车位
    entry_time      TEXT     NOT NULL,            -- 入场时间
    exit_time       TEXT,                         -- 出场时间（未出库时为 NULL）
    duration_sec    INTEGER,                      -- 停车时长（秒），出场时填写
    fee             REAL,                         -- 费用（元），出场时填写
    member_flag     INTEGER  NOT NULL DEFAULT 0,   -- 是否会员 1/0
    operator_id     INTEGER,                      -- 记录操作员
    note            TEXT,
    created_at      TEXT     DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_plate       ON parking_records(plate_no);
CREATE INDEX IF NOT EXISTS idx_entry_time ON parking_records(entry_time);
CREATE INDEX IF NOT EXISTS idx_exit_time  ON parking_records(exit_time);

-- 会员
CREATE TABLE IF NOT EXISTS members (
    id            INTEGER  PRIMARY KEY AUTOINCREMENT,
    plate_no      TEXT     NOT NULL UNIQUE,
    name          TEXT,
    phone         TEXT,
    valid_from    TEXT     NOT NULL,
    valid_to      TEXT     NOT NULL,
    discount      REAL     NOT NULL DEFAULT 1.0,   -- 折扣，1.0 表示不打折
    created_at    TEXT     DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_member_plate ON members(plate_no);

-- 黑名单
CREATE TABLE IF NOT EXISTS blacklist (
    id          INTEGER  PRIMARY KEY AUTOINCREMENT,
    plate_no    TEXT     NOT NULL UNIQUE,
    reason      TEXT,
    created_at  TEXT     DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_black_plate ON blacklist(plate_no);
# 数据库设计

数据库：SQLite3，单文件 `db/parking.db`，由 `db/init_db.sql` 自动建表。

## 1. E-R 关系概览

```
users            (1) ──── (N) parking_records.operator_id  (可选)
parking_records  (1) ──── (1) parking_lot.status           (全局车位池)
parking_records  (N) ──── (1) members.plate_no             (会员标记写入 record)
parking_records  (N) ──── (1) blacklist.plate_no           (识别时检查)
```

## 2. 表结构

### 2.1 `users` — 用户表
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 |
| username | TEXT UNIQUE | 账号 |
| password | TEXT | PBKDF2-SHA256 加盐哈希，格式 `pbkdf2_sha256$迭代次数$salt$hash` |
| role | TEXT | `admin` / `operator` |
| real_name | TEXT | 真实姓名 |
| created_at | TEXT | 创建时间 |

### 2.2 `parking_lot` — 停车场配置
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 固定为 1 |
| total_spots | INTEGER | 总车位 |
| used_spots | INTEGER | 已用车位 |

### 2.3 `parking_records` — 停车记录
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 |
| plate_no | TEXT | 车牌 |
| vehicle_type | TEXT | 小型车 / 大型车 |
| spot_no | TEXT | 分配车位 |
| entry_time | TEXT | 入场时间 |
| exit_time | TEXT | 出场时间（未出库时为 NULL） |
| duration_sec | INTEGER | 时长（秒） |
| fee | REAL | 费用（元） |
| member_flag | INTEGER | 是否会员 1/0 |
| operator_id | INTEGER | 操作员 ID |
| note | TEXT | 备注 |

### 2.5 `members` — 会员
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 |
| plate_no | TEXT UNIQUE | 车牌 |
| name / phone | TEXT | 姓名 / 电话 |
| valid_from / valid_to | TEXT | 有效期 |
| discount | REAL | 折扣（1.0 表示不打折） |

### 2.6 `blacklist` — 黑名单
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 |
| plate_no | TEXT UNIQUE | 车牌 |
| reason | TEXT | 加入原因 |
| created_at | TEXT | 添加时间 |

## 3. 索引

```sql
CREATE INDEX idx_plate       ON parking_records(plate_no);
CREATE INDEX idx_entry_time  ON parking_records(entry_time);
CREATE INDEX idx_exit_time   ON parking_records(exit_time);
CREATE INDEX idx_member_plate ON members(plate_no);
CREATE INDEX idx_black_plate  ON blacklist(plate_no);
```

## 4. 初始化

`db/database.init_database()` 会自动：

1. 执行 `init_db.sql`；
2. 若 `users` 为空 → 插入默认账号 `admin / admin123`、`operator / 123456`；
3. 若 `parking_lot` 为空 → 插入总车位（默认 50）。
# ADR-0012: Config Migration Framework

## Status

✅ Accepted (2026-06-24)

## Context

v3.1 配置项改造移除了 2 个老配置 (`enable_life_simulator`, `life_simulator_mode`) 并重命名了 1 个字段 (`enable_proactive_chat` → `enable_proactive_prompt`)。老用户的 `cmd_config.json` 里这些键还在，AstrBot WebUI 加载 schema 后会丢默认值但保留旧键，用户设置丢失。

需要一个通用的配置迁移框架，自动将老 config 迁移到新 schema，同时为未来 v3.1+ 的 schema 变化预留扩展点。

## Options

### A: 手动迁移脚本
写一个一次性 Python 脚本，用户手动运行。
- ✅ 简单
- ❌ 用户可能忘记跑
- ❌ 不可扩展

### B: 通用 Registry 模式 (选择)
`@register_migration(from_version, to_version)` 装饰器 + Runner + State 持久化。
- ✅ 可扩展（加新规则只追加代码）
- ✅ 自动运行（plugin `__init__` 时）
- ✅ 幂等（state 文件记录已应用的规则）
- ✅ fail-soft（单条规则失败不阻塞）
- ❌ 比 A 复杂

### C: AstrBot 内置 schema 迁移
依赖 AstrBot 的配置系统自动处理。
- ✅ 零代码
- ❌ AstrBot 只能加/删字段，不能做值转换
- ❌ 不可控制迁移逻辑

## Decision

选择 **B: 通用 Registry 模式**。

理由：
1. **可扩展**: 未来 schema 变化只需加新规则文件，不改框架
2. **自动运行**: plugin 加载时自动检测并迁移
3. **可观测**: `data/migrations.json` 记录每次迁移，出错可追溯
4. **幂等**: 重复运行结果一致
5. **fail-soft**: 单条规则失败不阻塞其他规则

## Implementation

```
emotion_spirit/migrations/
├── __init__.py          # public API
├── registry.py          # @register_migration + get_migrations
├── state.py             # MigrationState (data/migrations.json)
├── runner.py            # run_migrations() 主逻辑
└── rules/
    └── v3_0_to_v3_1.py  # 2 条迁移规则
```

**集成点**: `main.py __init__` 中在 `build_modules()` 之前运行迁移。

**写盘顺序**: config 先写，state 后写。保证 state 写失败时下次启动重跑（幂等）。

**Web API**: `POST /emotion_spirit/re_run_migration` 手动强制重跑。

## Consequences

### 正面
- 用户升级不丢设置
- 未来 schema 变化零框架改动
- 迁移历史可追溯

### 负面
- 增加 ~200 行代码
- 需要维护 `data/migrations.json` 文件
- AstrBot 配置系统可能先于 migration 运行（已发现，migration 是保险机制）

## References

- [Spec](../superpowers/specs/2026-06-24-config-migration-framework-design.md)
- [Plan](../superpowers/plans/2026-06-24-config-migration-framework-plan.md)
- [Session Report](../reports/2026-06-24-session-summary.md)

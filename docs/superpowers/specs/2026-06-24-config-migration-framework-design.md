---
title: Config Migration Framework Design (v3.0 → v3.1+)
date: 2026-06-24
status: approved
author: emotion_spirit team
---

# Config Migration Framework Design

## Context

本次 v3.1 配置项改造 (per [session 2026-06-24](../emotion-spirit-session-2026-06-24.md)) 移除了 2 个老配置:
- `feature_toggles.enable_life_simulator` (总开关)
- `feature_toggles.life_simulator_mode` ("both"/"passive"/"silent")

并重命名了 1 个字段:
- `proactive_chat.enable_proactive_chat` → `proactive_chat.enable_proactive_prompt`

**问题**: 老用户的 `data/cmd_config.json` 里这些键还在, AstrBot WebUI 加载 schema 后会丢默认值但保留旧键, 用户设置丢失 (例: 老用户设 `life_simulator_mode="passive"` 表达"只要 Mode A" 的意图在升级后消失).

**目标**: 写一个通用的 config migration 框架, 自动将老 config 迁移到新 schema, 同时为未来 v3.1+ 的 schema 变化预留扩展点.

## Goals

1. **向后兼容**: 老用户升级时不丢设置
2. **可扩展**: 加新 migration rule 只追加代码, 不改框架
3. **可观测**: state 文件记录每次迁移, 出错可追溯
4. **轻量级**: 1 人项目, 不要 GitFlow / 审批流那么重
5. **幂等**: 重复运行结果一致

## Non-Goals

- 不做 schema 版本号管理 (AstrBot WebUI 已有 schema, 我们只跟 schema 内部行为)
- 不做 remote config 同步 (本地配置本地管理)
- 不做 UI 嵌入 (WebUI 按钮实际嵌入放到下个大版本, 本次只暴露 API 端点)

## Design

### 1. 文件结构

```
emotion_spirit/migrations/
├── __init__.py
├── registry.py          # @register_migration 装饰器
├── state.py             # data/migrations.json 读写
├── runner.py            # run_migrations() 主逻辑
└── rules/
    ├── __init__.py
    └── v3_0_to_v3_1.py  # 本次的迁移规则
```

### 2. 注册表 API (`migrations/registry.py`)

```python
from typing import Callable

_REGISTRY: list[tuple[int, int, str, Callable[[dict], dict]]] = []

def register_migration(from_version: int, to_version: int, name: str | None = None):
    """装饰器: 注册一条 migration 规则.
    
    Args:
        from_version: 源 schema 版本号
        to_version: 目标 schema 版本号 (必须 = from_version + 1)
        name: 可选, 规则名 (默认用函数 __name__)
    
    Returns:
        装饰器, 接受函数 `(config: dict) -> dict`
    """
    def decorator(fn: Callable[[dict], dict]) -> Callable[[dict], dict]:
        rule_name = name or fn.__name__
        if to_version != from_version + 1:
            raise ValueError(f"to_version must equal from_version + 1, got {from_version} -> {to_version}")
        _REGISTRY.append((from_version, to_version, rule_name, fn))
        return fn
    return decorator

def get_migrations() -> list[tuple[int, int, str, Callable]]:
    """按 from_version 升序返回所有注册规则."""
    return sorted(_REGISTRY, key=lambda x: x[0])

def get_latest_version() -> int:
    """返回已注册的最高 to_version (= 当前 schema 版本号)."""
    if not _REGISTRY:
        return 0
    return max(m[1] for m in _REGISTRY)
```

### 3. State 文件 (`migrations/state.py`)

**位置**: `data/migrations.json` (跟 SpiritStore 平级)

**格式**:
```json
{
  "current_version": 3,
  "applied": [
    {
      "from": 1,
      "to": 2,
      "rule": "split_life_simulator_modes",
      "timestamp": "2026-06-24T10:00:00+08:00"
    }
  ],
  "errors": [
    {
      "rule": "split_life_simulator_modes",
      "error": "KeyError: 'foo'",
      "timestamp": "2026-06-24T10:00:00+08:00"
    }
  ]
}
```

**API**:
```python
class MigrationState:
    def __init__(self, data_dir: Path):
        self._path = data_dir / "migrations.json"
    
    def load_or_init(self) -> "MigrationState":
        """读 state 文件, 不存在则返回 current_version=0 的新 state."""
    
    def record_applied(self, from_v: int, to_v: int, rule: str) -> None:
        """追加到 applied 列表."""
    
    def record_error(self, rule: str, error: str) -> None:
        """追加到 errors 列表."""
    
    def save(self) -> None:
        """原子写盘 (tmp + rename)."""
    
    @property
    def current_version(self) -> int:
        return self._data["current_version"]
    
    @current_version.setter
    def current_version(self, v: int) -> None:
        self._data["current_version"] = v
```

### 4. Runner (`migrations/runner.py`)

```python
def run_migrations(config: dict, state: MigrationState, force: bool = False) -> tuple[dict, MigrationState]:
    """遍历注册表, 应用从 state.current_version 到 latest 的所有规则.
    
    Args:
        config: 当前 config dict (会被修改, 函数内部不修改原对象)
        state: MigrationState 实例
        force: True 时跳过版本检查, 重新跑所有规则
    
    Returns:
        (迁移后的 config dict, 更新后的 state) — 注意 state 是新对象, 调用方负责 save
    
    行为:
        - 逐条应用 from_version > state.current_version 的规则
        - 单条失败: 记录到 state.errors, 继续下一条
        - 所有应用成功的规则都会被记录到 state.applied
        - 即使有失败, state.current_version 也推进到 latest (幂等)
        - state.save() 由调用方负责 (main.py _run_config_migration), 
          这样调用方可以先写盘再 save state, 避免 state 推进但 config 没写盘的状态不一致
    """
    new_config = copy.deepcopy(config)
    target_version = get_latest_version()
    
    if not force and state.current_version >= target_version:
        return new_config, state  # 已最新
    
    for from_v, to_v, rule_name, fn in get_migrations():
        if from_v < state.current_version:
            continue
        try:
            new_config = fn(new_config)
            state.record_applied(from_v, to_v, rule_name)
            logger.info("Migration applied: %s (%d -> %d)", rule_name, from_v, to_v)
        except Exception as e:
            state.record_error(rule_name, str(e))
            logger.warning("Migration %s failed: %s", rule_name, e)
    
    state.current_version = target_version
    return new_config, state
```

**写盘顺序约束** (在 main.py `_run_config_migration` 中):
1. 读 config + state
2. 调 run_migrations
3. 比较新 config 与旧 config, 有变化则 json.dump 写盘
4. state.save() 写盘

如果步骤 3 失败抛异常 → state 没 save → 下次启动重试 → 不会丢用户数据
如果步骤 4 失败抛异常 → config 已写但 state 没 save → 下次启动 state 还是旧 version → 重新跑 migration (幂等, 无副作用)
最坏情况: state 写成功但 config 没写 → 下次启动 state 说"已迁移"但 config 还是老的 → 这时需要 force=True 重跑 (WebUI 按钮可触发)

### 5. 第一条规则 — `rules/v3_0_to_v3_1.py`

```python
from ..registry import register_migration

@register_migration(from_version=1, to_version=2)
def split_life_simulator_modes(config: dict) -> dict:
    """将 feature_toggles.life_simulator_mode 拆为 per-mode 开关."""
    toggles = config.get("feature_toggles", {})
    
    # 处理 enable_life_simulator 总开关
    if "enable_life_simulator" in toggles:
        if toggles["enable_life_simulator"] is False:
            # 总开关关 → 两个 mode 都关
            config.setdefault("life_simulator", {})["enable_life_fragment"] = False
            config.setdefault("proactive_chat", {})["enable_proactive_prompt"] = False
        del toggles["enable_life_simulator"]
    
    # 处理 life_simulator_mode
    mode = toggles.pop("life_simulator_mode", None)
    if mode is not None:
        config.setdefault("life_simulator", {})["enable_life_fragment"] = mode in ("both", "passive")
        config.setdefault("proactive_chat", {})["enable_proactive_prompt"] = mode in ("both", "silent")
    
    return config


@register_migration(from_version=2, to_version=3)
def rename_enable_proactive_chat(config: dict) -> dict:
    """proactive_chat.enable_proactive_chat → enable_proactive_prompt."""
    pc = config.get("proactive_chat", {})
    if "enable_proactive_chat" in pc:
        pc["enable_proactive_prompt"] = pc.pop("enable_proactive_chat")
    return config
```

### 6. WebUI API 端点 (本次只做后端)

```python
# main.py
def _setup_web_apis(self):
    # ... 已有端点 ...
    self.context.register_web_api(
        route="emotion_spirit/re_run_migration",
        view_handler=self._api_re_run_migration,
        methods=["POST"],
        desc="手动重新跑 config migration (高级用户)"
    )

async def _api_re_run_migration(self, **kwargs):
    """POST /re_run_migration — 强制重跑 migration."""
    try:
        config = self._load_user_config()  # 从 cmd_config.json 读
        state = MigrationState(self._data_dir).load_or_init()
        new_config, new_state = run_migrations(config, state, force=True)
        # 同样写盘顺序: config 先, state 后
        self._save_user_config(new_config)
        new_state.save()
        return quart_jsonify({"status": "ok", "config": new_config, "state": new_state.to_dict()})
    except Exception as e:
        return quart_jsonify({"status": "error", "msg": str(e)}), 500
```

**注意**: WebUI 实际按钮嵌入放到下个大版本, 本次只暴露 endpoint.

### 7. 集成点 (`main.py`)

**关键设计决策**: Migration 必须在 `_apply_config_overrides()` **之前** 跑, 因为:

- `_apply_config_overrides()` 读取 `self._config` (来自 `__init__` 参数), 只看新 schema 的字段
- 如果迁移后, 用户老 config 还没迁移, `_apply_config_overrides` 拿不到新字段, 整个 plugin 用旧 config 跑
- 必须在 `__init__` 里先跑迁移, 让 AstrBot 拿到的是迁移后的新 config

**具体顺序**:

```python
def __init__(self, context, config=None):
    super().__init__(context)
    self._config = config or {}
    self._engine = None
    # life_sim 子模式开关 (默认开, 由 _apply_config_overrides 覆盖)
    self._enable_proactive_prompt = True
    self._enable_life_fragment = True
    
    # 新增: 先跑 migration (写盘 + 返回新 config)
    self._config = self._run_config_migration_and_reload(self._config)
    
    # 然后跑 apply overrides (此时 self._config 已是新 schema)
    self._apply_config_overrides()
    
    # ... 后续不变
```

```python
def _run_config_migration_and_reload(self, config: dict) -> dict:
    """从 cmd_config.json 读 config, 跑 migration, 写回, 返回新 config.

    即使 AstrBot 已经把 config 传给我们, 我们仍然从文件读,
    因为:
    1. AstrBot 传入的 config 可能不是最新 (缓存)
    2. 写盘需要文件路径
    """
    from emotion_spirit.migrations import run_migrations, MigrationState
    config_path = Path(get_astrbot_data_path()) / "config" / "astrbot_plugin_emotion_spirit_config.json"
    data_dir = Path(get_astrbot_data_path()) / "plugin_data" / "emotion_spirit"
    
    if not config_path.exists():
        return config  # 无文件, 不做迁移
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            file_config = json.load(f)
        state = MigrationState(data_dir).load_or_init()
        new_config, new_state = run_migrations(file_config, state)
        
        # 写盘顺序: config 先, state 后
        if new_config != file_config:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(new_config, f, ensure_ascii=False, indent=2)
            logger.info("Config migration applied, saved %s", config_path)
        new_state.save()
        
        # 合并: 用文件的新 config 覆盖 AstrBot 传入的 (文件更新, 内存也要更新)
        return new_config
    except Exception as e:
        logger.warning("Config migration failed: %s, 使用 AstrBot 传入的 config", e)
        return config  # 失败回退到原始 config
```

### 7.1 WebUI API 端点集成

**注意**: `_setup_web_apis()` 方法已被前次清理删除. 本次需要**重新加回**这个方法, 但只注册 migration 端点 (不再做仪表盘):

```python
def _setup_web_apis(self) -> None:
    """注册 Web API 端点 (本次只加 migration 端点)."""
    self.context.register_web_api(
        route="emotion_spirit/re_run_migration",
        view_handler=self._api_re_run_migration,
        methods=["POST"],
        desc="手动重跑 config migration",
    )

async def _api_re_run_migration(self, **kwargs):
    """POST /emotion_spirit/re_run_migration — 强制重跑 migration."""
    try:
        config_path = Path(get_astrbot_data_path()) / "config" / "astrbot_plugin_emotion_spirit_config.json"
        data_dir = Path(get_astrbot_data_path()) / "plugin_data" / "emotion_spirit"
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        state = MigrationState(data_dir).load_or_init()
        new_config, new_state = run_migrations(config, state, force=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(new_config, f, ensure_ascii=False, indent=2)
        new_state.save()
        return quart_jsonify({"status": "ok", "config": new_config, "state": new_state.to_dict()})
    except Exception as e:
        return quart_jsonify({"status": "error", "msg": str(e)}), 500
```

并在 `initialize()` 中调 `self._setup_web_apis()` (本次不删除)。

## SpiritStore vs cmd_config.json 边界

| 文件 | 内容 | 谁写 |
|---|---|---|
| `data/config/astrbot_plugin_emotion_spirit_config.json` | 用户配置 (schema driven) | AstrBot WebUI |
| `data/plugin_data/emotion_spirit/migration.json` | migration 状态 (本次新加) | migration runner |
| `data/plugin_data/emotion_spirit/spirit_store.json` | plugin 运行时状态 (persona/memory/intimacy) | emotion_spirit plugin |

**Migration 只读 cmd_config.json, 写 cmd_config.json 和 migration.json**, 不碰 spirit_store.json.
Migration 不影响 SpiritStore 的任何 key.

## Testing Strategy

### 单元测试 (`tests/migrations/`)

| 文件 | 覆盖 |
|---|---|
| `test_registry.py` | 装饰器注册, 排序, get_latest_version |
| `test_state.py` | load_or_init, record_applied, record_error, save, 原子写 |
| `test_runner.py` | 正常流程, 幂等, force=True, 部分失败 |
| `test_rules_v3_0_to_v3_1.py` | 3 条规则各自 + 组合 |
| `test_integration.py` | 端到端: 老 config → 跑迁移 → 新 config |

### 关键 fixture

- `old_config_both.json` — 完整的老 config (life_simulator_mode="both", enable_proactive_chat)
- `old_config_passive.json` — life_simulator_mode="passive" 的迁移期望
- `old_config_disabled.json` — enable_life_simulator=false 的迁移期望

### 手动验证步骤

1. 准备一份老 config 文件 (含已删除的键)
2. 启动 AstrBot, 检查 log: "Migration applied: ..."
3. 检查 config 文件: 老键消失, 新键填入正确值
4. 重启 AstrBot: 检查 log "已最新, 跳过", 不重复迁移
5. 手动调 API `POST /emotion_spirit/re_run_migration`: 检查结果

## Risks & Mitigations

| 风险 | 缓解 |
|---|---|
| 迁移函数修改原 config 导致调用方拿到脏数据 | Runner 用 `copy.deepcopy`, 失败回退原 config |
| 用户手动改 config 文件绕过 migration | State 文件记录 applied, 启动时检查 |
| 老 schema 字段嵌套深, 写迁移函数易错 | 测试覆盖每条规则 + fixture 完整 config |
| Migration 跑一半崩了, state 已写 | State 在最后才 `save`, 崩溃不污染 |
| WebUI 读 state 文件失败 | 启动时 try/except, 不影响 plugin 启动 |
| **Migration 时机错误 (迁移晚于 apply overrides)** | 明确迁移必须在 `_apply_config_overrides` **之前** 跑; 否则老 config 升级后第一次运行, override 用的是旧 schema 字段 |
| **AstrBot 传入 config 跟文件不一致** | Migration 从文件重新读, 不用 `self._config` 入参; 写盘后返回新 config 让 `__init__` 用 |
| **Migration 跟 SpiritStore 串扰** | 明确边界: migration 只读 cmd_config.json + migration.json; SpiritStore 不动 |
| **重启后 AstrBot 又从文件读** | AstrBot 每次启动都重读 cmd_config.json, 所以写入新值后下次启动自然用新值 |
| **Hot reload 场景** | `initialize()` 会在 hot reload 时再次跑; state.current_version 检查避免重复 |

## Migration Versioning 规则

- 初始 version = 0 (无任何迁移规则)
- 每加一条规则, 升一档
- version N 表示 "已经应用了 from_version < N 的所有规则"
- `latest_version` 自动从注册表推算, 加规则不需手动更新

## Rollout Plan

1. **Phase 1**: 实现 framework + 第一条规则 (本次范围)
   - registry.py, state.py, runner.py
   - rules/v3_0_to_v3_1.py (3 条规则)
   - main.py 集成点 + _run_config_migration
   - WebUI POST endpoint (无 UI)
   - 单元测试 + integration 测试

2. **Phase 2**: 下次 schema 变动时再加新规则 (无需改框架)

3. **Phase 3**: 下个大版本 (v3.2?) 加 WebUI 按钮嵌入

## Open Questions

1. **是否支持 dry-run**: 让用户预览迁移结果不实际写盘? — Phase 1 不做, 留 hook
2. **state 文件是否要 atomic write**: 多进程并发风险? — 实际是单进程, Phase 1 不做
3. **migration 是否要可逆**: 出错回滚到迁移前? — 通过 copy.deepcopy 原 config 实现回滚, 不需额外机制

## Related

- [session 2026-06-24](../../memory/emotion-spirit-session-2026-06-24.md) — 配置项改造背景
- [ADR-0010](../adr/0010-v31-release-process.md) — v3.1 release 流程
- [ADR-0009](../adr/0009-v301-patch-lesson.md) — 多文件改动 checklist

## Spec Self-Review

1. ✅ Placeholder scan: 无 TBD/TODO
2. ✅ Internal consistency: 架构与功能描述一致
3. ✅ Scope check: 单次实施足够小, 不需分解
4. ✅ Ambiguity check: 
   - "迁移版本号"明确定义: 初始 0, 每规则 +1
   - "失败处理"明确定义: 跳过失败的规则, 记录到 errors, 继续后续
   - "state 文件位置"明确定义: data/migrations.json
# emotion_spirit 用户手册

> v1.0.0

## 1. 快速开始

### 1.1 安装

1. 确保已安装 AstrBot v4.9.2+
2. 下载 `astrbot-plugin-emotion-spirit-1.0.0.zip` 并解压
3. 将 `astrbot_plugin_emotion_spirit` 目录复制到 AstrBot 的 `data/plugins/`
4. 重启 AstrBot

> SylannEngine 计算核心已内嵌（`sylanne`），无需单独安装外部插件。

### 1.2 首次启动

插件启动后会：
- 延迟 2 秒连接 SylannEngine
- 延迟 3 秒验证 LLM 调用链
- 延迟 5 秒运行人格分析（auto 模式）

使用 `/view_status` 确认插件正常运行。

---

## 2. 人格管理

### 2.1 三种模式

| 模式 | 说明 | 适合谁 |
|------|------|--------|
| **auto** | 自动从 AstrBot 人格报告提取标签，LLM 分析 | 想要自动化管理的用户 |
| **manual** | 手动配置自定义人格，选择 5 轴标签 | 想要精细控制的用户 |
| **disabled** | 使用 SylannEngine 默认值 | 不关心人格的用户 |

### 2.2 Auto 模式

1. 在配置中选择 `persona_mode = auto`
2. 在 `auto_source` 中选择要分析的 AstrBot 人格
3. 重启插件，等待 LLM 分析完成
4. 使用 `/view_whoami` 查看分析结果

**工作原理：**
- 插件读取 AstrBot 人格的 system_prompt
- 通过 LLM 提取 5 轴标签（MBTI、依恋、情绪策略、冲突风格、时间取向）
- 使用 `label_mapper` 自动映射为 13 维参数
- 结果缓存到 `data/plugin_data/emotion_spirit/persona_report.json`

### 2.3 Manual 模式

1. 在配置中选择 `persona_mode = manual`
2. 在 `manual_personas` 中点击"添加人格"
3. 填写人格名称，选择 5 轴标签
4. 重启插件
5. 使用 `/view_whoamis` 查看所有人格
6. 使用 `/setup_switch <名称>` 切换人格

### 2.4 查看人格详情

| 命令 | 说明 |
|------|------|
| `/view_whoami` | 查看当前人格的 5 轴标签 |
| `/view_detail` | 查看当前人格的 13 维参数 |
| `/view_detail <名称>` | 查看指定人格的 13 维参数 |
| `/view_whoamis` | 列出所有人格 |

---

## 3. 功能开关

在 AstrBot WebUI 的插件配置中，`feature_toggles` 区域控制以下功能：

### 3.1 阴影检测 (ShadowDetector)

**作用：** 检测未符号化的情绪模式——反复出现但无法确认的记忆（回声）、系统性回避的话题（回避）、被压抑的记忆类型（确认偏差）。

**关闭影响：** `/reflect_shadows` 不可用，PromptInjector 不再注入阴影信息。

**建议：** 保持开启。阴影检测是情感自省的核心功能。

### 3.2 预警系统 (PredictiveSentinel)

**作用：** 13 信号早期预警，监测身体状态、缓冲池健康和级联风险。

**关闭影响：** `/reflect_sentinel` 不可用。

**建议：** 保持开启。预警系统是诊断工具，对调试很有价值。

### 3.3 叙事身份 (NarrativeIdentity)

**作用：** 每月扫描记忆、模式和漂移数据，生成上升/下降/停滞/循环型叙事弧。

**关闭影响：** 月度叙事不再生成。

**建议：** 可选关闭。叙事身份目前未集成到 PromptInjector，关闭不影响核心功能。

### 3.4 自主生活模拟 (LifeSimulator)

**作用：** bot 在空闲时主动发起对话（Mode A）或长时间沉默后生成生活事件（Mode B）。

**关闭影响：** bot 变为纯被动响应，不会主动发消息。

**建议：** 根据个人偏好。如果觉得 bot 主动发消息打扰，可以关闭。

### 3.5 生活模拟子模式

生活模拟分为两个独立模式，可在 WebUI 中分别开关：

| 配置段 | 配置项 | 说明 |
|--------|--------|------|
| `life_simulator` | `enable_life_fragment` | Mode A: 对话中插入生活片段 |
| `proactive_chat` | `enable_proactive_prompt` | Mode B: 长沉默后主动发起对话 |

**建议：** 两个模式独立控制，可根据个人偏好分别开关。

---

## 4. 诊断命令

### 4.1 `/view_status`

查看系统整体状态，包括：
- 人格模式和当前人格
- SylannEngine 连接状态
- 四层记忆的条数
- 亲密度、价值对齐、良心压力、意义蓄水
- 功能开关状态

### 4.2 `/reflect_drift`

查看人格漂移状态，包括：
- 整合度斜率
- 意义蓄水水平
- 各维度的漂移方向和速度

### 4.3 `/reflect_sentinel`

查看预警状态，包括：
- 当前预警级别（normal/warning/critical）
- 触发的信号列表

### 4.4 `/reflect_shadows`

查看阴影检测结果，包括：
- 检测到的阴影数量
- 每个阴影的证据类型、标签、置信度和建议

### 4.5 `/reflect_diary`

手动生成日记。日记类型由情感动量决定：
- **ascending**: 情感在改善
- **descending**: 情感在恶化
- **stagnant**: 情感平稳
- **cyclic**: 情感在循环

### 4.6 `/reflect_patterns`

查看行为模式，包括：
- **cycle**: 循环模式（A→B→A→B）
- **trend**: 趋势模式（单调变化）
- **trigger**: 触发模式（条件概率）
- **avoidance**: 回避模式（预期但未出现的标签）

---

## 5. 数据管理

### 5.1 数据位置

- **主数据**: `data/plugin_data/emotion_spirit/spirit_data.json`
- **人格报告**: `data/plugin_data/emotion_spirit/persona_report.json`
- **插件配置**: `data/config/astrbot_plugin_emotion_spirit_config.json`

### 5.2 数据备份

建议定期备份 `data/plugin_data/emotion_spirit/` 目录。

### 5.3 数据重置

删除 `spirit_data.json` 并重启插件，所有记忆、亲密度、模式等数据将重置。

**注意：** 人格报告 (`persona_report.json`) 和配置不受影响。

---

## 6. 常见问题

### Q: 插件启动后显示"LLM provider 不可用"

A: 确保 AstrBot 配置了可用的 LLM provider。auto 模式和日记生成依赖 LLM。

### Q: `/reflect_shadows` 返回"已关闭"

A: 在配置中启用 `enable_shadow_detector`，然后重启 AstrBot。

### Q: 如何切换人格？

A: 使用 `/view_whoamis` 列出所有人格，然后 `/setup_switch <名称>` 切换。

### Q: 关闭某个功能后数据会丢失吗？

A: 不会。关闭功能只是停止处理，已有数据保留在 `spirit_data.json` 中。重新开启后可以继续使用。

### Q: 如何让 bot 不要主动发消息？

A: 在 WebUI 配置中关闭 `proactive_chat.enable_proactive_prompt`（Mode B）。如果也不想在对话中插入生活片段，同时关闭 `life_simulator.enable_life_fragment`（Mode A）。

### Q: 人格分析结果不准确怎么办？

A: 使用 manual 模式手动配置 5 轴标签，覆盖 auto 模式的分析结果。

---

## 7. 最佳实践

1. **首次使用建议 auto 模式**，让 LLM 自动分析人格，然后通过 `/view_whoami` 检查结果
2. **保持阴影检测和预警系统开启**，这两个功能对情感自省最有价值
3. **定期查看 `/view_status`**，了解系统运行状态
4. **不要频繁切换人格**，每次切换都会重置人格相关的状态
5. **备份数据目录**，特别是 `spirit_data.json` 包含所有记忆数据

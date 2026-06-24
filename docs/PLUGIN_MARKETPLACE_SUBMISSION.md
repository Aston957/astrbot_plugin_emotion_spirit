# 插件市场上架指南

> **目标**: 将 emotion_spirit 提交到 AstrBot 插件市场
> **前置**: 已有 GitHub 仓库 + Release CI + 完整 metadata.yaml
> **预计耗时**: 30 分钟（不含 CI 安全扫描等待）

---

## 背景

AstrBot 插件市场是一个**中心化注册表**，数据源在：

- **仓库**: `AstrBotDevs/AstrBot_Plugins_Collection`
- **注册表文件**: `plugins.json`（只存仓库 URL，元数据从 GitHub 实时拉取）
- **API**: `https://api.soulter.top/astrbot/plugins`（AstrBot 客户端从这里拉取）
- **CDN**: `astrbot-plugins-s3.astrbot.app`（CI 自动打包上传，用户从这里下载）

**工作原理**: 你只需在 `plugins.json` 中添加一行 `{repo: "https://github.com/..."}`, CI 自动完成:
1. 从你的仓库拉取 `metadata.yaml` 元数据
2. 从 GitHub Release 获取版本和 zip 包
3. 上传到 S3 CDN
4. 运行 VirusTotal + LLM Agent 安全扫描
5. 更新 `plugins.json` 中的完整条目

---

## Step 1: 确认仓库前置条件

### 1.1 metadata.yaml ✅ 已满足

必需的 4 个字段: `name`, `desc`, `version`, `author`

当前状态:
```yaml
name: emotion_spirit
display_name: "Emotion Spirit"
desc: "长期记忆、人格演化与超我调控 — SylannEngine 内嵌的自我层 (v3.0.1)"
author: "emotion_spirit"
version: "3.0.1"
repo: "https://github.com/Aston957/astrbot_plugin_emotion_spirit"
support_platforms: [aiocqhttp, telegram, qq_official]
astrbot_version: ">=4.9.2,<5"
```

可选但建议添加:
- `display_name` — 市场列表展示用（当前有，但建议改成更友好的名字如 "Emotion Spirit - 情感引擎"）

### 1.2 GitHub Release ✅ 已满足

CI 在 `git tag` push 时自动:
- 运行 pytest
- 生成 slim zip（排除 tests/docs/tools 等）
- 创建 GitHub Release + attach zip

**验证**: 访问 https://github.com/Aston957/astrbot_plugin_emotion_spirit/releases 确认有一个正式 Release（非 pre-release）。

### 1.3 _conf_schema.json ✅ 已满足

WebUI 配置面板 schema，已有。

### 1.4 logo.png ⚠️ 可选

市场展示用 logo。如果要加:
- 放在插件根目录: `logo.png`
- 建议尺寸: 256x256 或 512x512
- AstrBot 加载逻辑见 `star_manager.py:997` (`logo_fname = "logo.png"`)

### 1.5 安全检查清单

CI 安全扫描会检查以下内容（你的插件已通过 pre-commit secret scanner）:

| 检查项 | 你的状态 |
|--------|----------|
| pbkdf2 密码哈希 | ✅ 已从 git history 清洗 |
| API keys (sk-...) | ✅ 无 |
| GitHub PAT (ghp_...) | ✅ 无 |
| eval/exec 注入 | ✅ 无 |
| 网络外传到第三方 | ✅ 无（只调用 LLM provider） |
| 恶意 subprocess | ✅ 无 |

---

## Step 2: Fork 并修改 plugins.json

### 2.1 Fork 仓库

```
https://github.com/AstrBotDevs/AstrBot_Plugins_Collection
→ 点击 Fork → 到你的账号下
```

### 2.2 克隆你的 Fork

```bash
git clone https://github.com/<你的用户名>/AstrBot_Plugins_Collection.git
cd AstrBot_Plugins_Collection
```

### 2.3 编辑 plugins.json

在 `plugins.json` 中添加一个条目（JSON 对象，key 是插件 ID）:

```json
{
  "astrbot-plugin-mc-skin": { ... },
  "astrbot-plugin-electricity-monitor": { ... },
  ...
  "emotion-spirit": {
    "repo": "https://github.com/Aston957/astrbot_plugin_emotion_spirit"
  }
}
```

**注意**:
- key 建议用 `emotion-spirit`（kebab-case，和 repo 名保持一致）
- 只需要 `repo` 字段，其他所有元数据由 CI 自动从仓库获取
- JSON 格式要正确（注意逗号）

### 2.4 提交 PR

```bash
git checkout -b add-emotion-spirit
git add plugins.json
git commit -m "Add emotion-spirit plugin"
git push origin add-emotion-spirit
```

然后到 GitHub 上创建 PR:
- 标题: `Add emotion-spirit plugin`
- 描述: 简要说明插件功能

---

## Step 3: 等待 CI 验证

PR 提交后，CI 自动运行:

1. **格式验证**: 检查 `plugins.json` 格式、repo URL 可达性
2. **元数据拉取**: 从你的仓库读取 `metadata.yaml`，验证必需字段
3. **Release 检查**: 获取最新 Release，下载 zip
4. **安全扫描**:
   - VirusTotal 扫描 zip 包
   - LLM Agent 代码审计
5. **生成 CDN 链接**: 上传到 `astrbot-plugins-s3.astrbot.app`

如果 CI 报错，常见原因:
- `metadata.yaml` 缺少必需字段
- GitHub Release 没有 zip asset
- 仓库 URL 格式不对
- 安全扫描未通过

---

## Step 4: 合并上架

CI 通过后，仓库维护者会 review 并 merge PR。

合并后:
- 你的插件出现在 AstrBot WebUI 的「插件市场」列表
- 用户可以通过 `AstrBotDevs/AstrBot_Plugins_Collection` 的仓库 URL 安装
- 后续发布新版本只需创建新 Release，市场自动更新

---

## Step 5: 后续维护

### 发布新版本

1. 更新 `metadata.yaml` 中的 `version`
2. `git tag v3.x.x && git push --tags`
3. GitHub Actions 自动创建 Release + zip
4. 插件市场 CI 自动检测到新版本

### 不需要手动操作的

- ❌ 不需要手动更新 `plugins.json` 中的版本号
- ❌ 不需要手动上传 zip 到 CDN
- ❌ 不需要手动更新安全扫描结果

---

## 参考资料

| 资源 | URL |
|------|-----|
| 插件市场仓库 | https://github.com/AstrBotDevs/AstrBot_Plugins_Collection |
| 发布文档 | https://docs.astrbot.app/dev/star/plugin-publish.html |
| 你的仓库 | https://github.com/Aston957/astrbot_plugin_emotion_spirit |
| Release 页面 | https://github.com/Aston957/astrbot_plugin_emotion_spirit/releases |
| 市场 API | https://api.soulter.top/astrbot/plugins |

---

## 附录: 市场条目完整格式参考

以下是 CI 处理后的完整条目格式（你只需要提供 `repo`，其余自动生成）:

```json
{
  "emotion-spirit": {
    "display_name": "Emotion Spirit",
    "desc": "长期记忆、人格演化与超我调控 — SylannEngine 内嵌的自我层 (v3.0.1)",
    "author": "emotion_spirit",
    "repo": "https://github.com/Aston957/astrbot_plugin_emotion_spirit",
    "tags": [],
    "stars": 0,
    "version": "3.0.1",
    "astrbot_version": ">=4.9.2,<5",
    "updated_at": "2026-06-XX",
    "commit_sha": "...",
    "download_url": "https://astrbot-plugins-s3.astrbot.app/plugins/Aston957/emotion-spirit/3.0.1/...",
    "sec_scan": {
      "virustotal": { "pass": true, "msg": "..." },
      "llm_agent": { "pass": true, "msg": "..." }
    },
    "i18n": {}
  }
}
```

# Habitica-Forge 开发路线图 (TODO)

### 测试命令规范（Windows + uv）
- 默认执行：`uv run python -m pytest`
- 显式目录：`uv run python -m pytest tests`
- 避免使用：`uv run pytest` 或 `uv run pytest test`（当前环境会触发 `Failed to canonicalize script path`）

### 阶段一：项目骨架与基础设施 (Foundation)
**目标**：确立 CLI 框架，加载环境变量，搭建安全的日志系统。

- [x] **1.1 项目结构初始化**
  - [x] 创建目录：`cli/`, `core/`, `clients/`, `ai/`, `schedule/`, `utils/`, `tests/`。
- [x] **1.2 配置中心 (`core/config.py`)**
  - [x] 使用 `pydantic-settings` 定义配置模型，集成 `.env` 加载。
  - [x] 必填项：Habitica 凭证、LLM 凭证。
  - [x] 算法参数项：`WEIGHT_TODO`, `WEIGHT_DAILY`, `TITLE_THRESHOLD`, `FORGE_STYLE`。
- [x] **1.3 终端渲染与日志 (`utils/logger.py`)**
  - [x] 接入 `Rich` 库用于美化终端输出。
  - [x] 配置全局日志系统：确保后台运行时的错误能写入本地 `.log` 文件，且**严格过滤脱敏**所有 API Key 和 Token。

### 阶段二：Habitica 客户端与云端缓存层 (Client & Cache) ✅
**目标**：打通 Habitica 接口，建立"以云端为准，本地仅作缓存"的数据通道。
参考examples.ipynb的示例代码
- [x] **2.1 异步 HTTP 客户端 (`clients/habitica.py`)**
  - [x] 使用 `httpx.AsyncClient` 封装 Habitica API。
  - [x] 实现基础拦截器：注入 `x-api-user`, `x-api-key`, `x-client`。
  - [x] 针对 429 错误和 5xx 错误实现指数退避重试装饰器。
- [x] **2.2 核心 API 绑定**
  - [x] Tasks 接口：获取(`GET /tasks/user`)、创建、更新(`PUT`)、完成、删除。
  - [x] Checklist 接口：新增、打勾、删除。
  - [x] Tags 接口：获取所有标签(`GET /tags`)、创建新标签、重命名标签、为任务挂载标签。
- [x] **2.3 本地缓存引擎 (`core/cache.py`)**
  - [x] 实现文件级缓存机制 (`~/.config/habitica-forge/cache/`)。
  - [x] 设定 `tasks.json` 和 `tags.json` 的独立 TTL（如 5 分钟）。
  - [x] 实现缓存失效机制：每次发生写操作（Add, Done, Update）后强制清理对应缓存。

### 阶段三：CLI 核心交互与任务管理 (CLI & Tasks) ✅
**目标**：不带 AI 的情况下，CLI 依然是一个极为好用的 Habitica 终端工具。

- [x] **3.1 任务展示 (`cli/viewer.py`)**
  - [x] `forge list`：提取缓存渲染任务表格（进度条、优先级、基于 Tags 的称号前缀）。
  - [x] `forge show <ID>`：渲染单任务 Markdown 详情及子任务 Checklist。
- [x] **3.2 任务操作命令 (`cli/commands.py`)**
  - [x] `forge add`：快速添加普通任务。
  - [x] `forge done <ID>`：完成主任务。
  - [x] `forge sub-add / sub-done / sub-del`：子任务快捷操作。
- [x] **3.3 数据同步机制**
  - [x] 实现 `forge sync` 命令：显式清空全部本地缓存并强制拉取 Habitica 最新状态。

### 阶段四：AI 智能拆解引擎 (Smart Forge - 前台阻塞) ✅
**目标**：实现核心价值 1，将模糊焦虑转为清晰步骤。

- [x] **4.1 LLM 适配器 (`ai/llm_client.py`)**
  - [x] 封装 OpenAI 兼容协议，支持 JSON 结构化输出 (`response_format`)。
- [x] **4.2 智能拆解流 (`cli/smart.py`)**
  - [x] 编写 System Prompt：注入用户选择的 `FORGE_STYLE` (如赛博朋克)。
  - [x] 实现 `forge smart-task "<任务ID或者编号>"` 命令。把用户现有的任务拆解，更新
  - [x] 实现 `forge smart-add "<任务描述>"` 命令，新增任务
  - [x] **UX 优化**：使用 `rich.status("🔥 锻造炉运转中...")` 包装阻塞等待时间。
  - [x] 获取 AI 的 JSON 输出后，自动拆解组装为 Habitica Payload 并推送到云端。

### 阶段五：称号收割、同步与全局展示 (The Identity System) ✅

- [x] **5.1 掉落算法判定器 (`core/bounty.py`)**
  - [x] 逻辑：`Drop_Score = (难度权重 × 类型权重) + RNG`。
- [x] **5.2 后台悬赏锻造 (`ai/bounty_agent.py`)**
  - [x] 异步启动后台进程，生成 `【WALL待激活】` 标签并挂载。
- [x] **5.3 集成化同步收割 (Integrated Harvest Hook)**
  - [x] **触发**：仅在执行网络请求（缓存失效/Sync/Add/Done）后触发。
  - [x] **动作**：扫描云端 `已完成任务` + `待激活标签` → 自动 `PUT` 重命名为 `【WALL】` → 自动 `DELETE` 旧级标签 → 更新本地缓存。

- [x] **5.4 身份标识注入与展示 (Identity Header - 核心视觉)**
  - [x] **身份解析逻辑**：编写 `get_current_identity()`，从本地 `cache/tags.json` 中提取带有 `【WALL No.1】` 前缀的标签名。
  - [x] **全局 Header 组件**：
    - [x] 使用 `Rich.Panel` 或 `Rich.Columns` 渲染一个固定的页眉。
    - [x] **内容包含**：`[当前佩戴称号]` + `[用户账号名/等级]` + `[系统状态(如：离线/同步中)]`。
    - [x] **动态前缀**：支持根据"任务腐烂系统"动态修改称号前缀（如 `[走火入魔的] 【WALL No.1】代码猎人`）。
  - [x] **自动注入**：修改 `cli/main.py` 的入口，确保**每一个命令在输出结果前，都先调用该 Header 组件进行打印**。
  - [x] **切换反馈**：实现 `forge switch <编号>` 命令（使用编号方式，与任务操作一致）。
    - [x] 流程：更新云端 Tag → **立即刷新本地缓存** → 输出"佩戴成功"提示（此时 Header 已显示为新称号）。
    - [x] 支持：先执行 `forge wall` 查看称号编号，再用 `forge switch 1` 佩戴。

- [x] **5.5 ASCII 称号墙渲染 (`cli/wall.py`)**
  - [x] 实现 `forge wall`：拉取云端所有 `【WALL】` 标签，渲染出美观的成就展示界面（带编号）。

---

### 设计效果示例：

当用户执行 `forge list` 时，终端的输出将如下所示：

```text
/====================================================================\
|  [ID] 480ac1e2...   [称号] 【WALL No.1】深渊代码猎人 Lv.3           |
\====================================================================/

[ID]   [分类]      [任务标题]                [进度]    [难度]
a1b2   (Coding)   修复登录逻辑              [====>  ] 50%  (Hard)
...
```

当用户执行 `forge wall` 后：

```text
═══════════════════════════════════════
        🏆 成 就 墙 🏆
═══════════════════════════════════════

  1. ★ 深渊代码猎人 (佩戴中)
  2. ○ 星尘征服者
  3. ○ 筑基期修士

已解锁 3 个称号

使用 forge switch <编号> 来佩戴称号
```

当用户执行 `forge switch 2` 后：

```text
/====================================================================\
|  [ID] 480ac1e2...   [称号] 【WALL No.1】星尘征服者                  |
\====================================================================/

[系统] 身份切换成功！你已佩戴称号：【星尘征服者】
```

### 为什么这样做是高效的？
1.  **极速渲染**：Header 默认只读本地 `cache/tags.json`，没有网络开销。
2.  **强制一致**：只有当缓存失效或用户手动 `sync` 时，Header 才会因为缓存更新而产生变化，保证了多端同步。
3.  **即时反馈**：`forge switch` 后立即刷新缓存，确保下一条命令的 Header 瞬间改变。
4.  **统一交互**：使用编号方式切换称号，与任务操作保持一致的交互体验。

### 阶段六：深渊腐烂批量系统 (Corruption - 独立后台) ✅
**目标**：实现核心价值 3，静默、批量、省 Token 的负面反馈驱动。

- [x] **6.1 腐烂扫描器本体 (`schedule/scanner.py`)**
  - [x] 编写独立可执行脚本。
  - [x] 拉取 `todos`，对比 `updatedAt` 提取过期任务。
  - [x] 剔除 `notes` 中已标记为最高腐烂等级（如 `<!-- CORRUPTED_LVL: 3 -->`）的任务。
- [x] **6.2 批量黑化引擎 (Batch Rewriting)**
  - [x] 将提取出的 5-10 个任务打包为 JSON List 发送给 LLM。
  - [x] 解析 LLM 返回的批量黑化文案。
- [x] **6.3 并发更新限制**
  - [x] 使用 `asyncio.Semaphore(3)` 限制并发。
  - [x] 异步发送 `PUT` 请求更新 Habitica 任务描述，并注入隐式标记。
- [x] **6.4 双模触发控制器**
  - [x] 维护 `~/.config/habitica-forge/last_scan_time.json`。
  - [x] 每次执行 `forge list` 前检查该文件。
  - [x] 若超 12h 未扫描，通过 `subprocess` 在**后台完全剥离运行** `scanner.py`（方案 B 兜底）。

### 阶段七：游戏化风格切换 (Style Switching) ✅
**目标**：支持在默认”正常”风格与其他游戏化风格之间切换，统一影响 AI 文案与 CLI 展示。

- [x] **7.1 风格配置默认值收敛**
  - [x] 明确”正常风格”为默认游戏化风格，未配置时回退到 `normal`。
  - [x] 统一 `FORGE_STYLE` 的合法枚举与显示名称映射，兼容已有风格值。
- [x] **7.2 风格切换命令**
  - [x] 新增 `forge style` 查询当前风格。
  - [x] 新增 `forge style switch <name>` 或等价命令，支持切换到 `normal`、`cyberpunk`、`wuxia`、`fantasy` 等风格。
  - [x] 切换后立即给出确认反馈，并确保后续命令读取到最新风格。
- [x] **7.3 风格影响范围统一**
  - [x] 让 `smart-add`、`smart-task`、称号生成、腐烂文案读取同一套风格解析逻辑。
  - [x] 正常风格下输出回归克制、直接、低装饰的文案，不附加明显游戏化措辞。
  - [x] 为 CLI Header / Wall / 提示文案预留风格化开关，避免展示层与 AI 层割裂。
- [x] **7.4 测试与文档补充**
  - [x] 为风格解析、默认回退、切换命令添加测试。
  - [x] 在 README.md 中补充风格列表、默认行为和切换示例。
- [x] **7.5 风格模板系统重构**
  - [x] 创建 `base_template.yaml` 基础提示词模板（Few-shot Prompting）。
  - [x] 重构各风格 YAML 为变量结构，只需填写风格变量即可。
  - [x] 实现 `loader.py` 模板渲染逻辑，自动将变量应用到基础模板。
  - [x] 移除 `config.py` 中的硬编码风格常量，实现动态风格发现。
  - [x] 添加新风格只需创建一个 YAML 文件，无需修改代码。

### 阶段八：体验打磨与交付 (Polish)
**目标**：确保软件的强健性，准备分发。

- [ ] **8.1 异常处理降级**
  - [ ] 处理 LLM JSON 解析失败的情况（正则回退或兜底文案）。
  - [ ] 处理离线状态：网络异常时允许 `forge list` 读取过期缓存并加上 `(离线)` 警告，禁用写操作。
- [ ] **8.2 纯净模式 (Zen Mode)**
  - [ ] 提供全局参数 `--zen` 或配置项，一键隐藏所有称号前缀和 ASCII 装饰，回归纯粹的 Todo 列表。
- [ ] **8.3 测试与文档**
  - [ ] 编写针对 Cache 策略和 Bounty 分数计算的单元测试。
  - [ ] 编写 README.md，包含配置示例和架构说明图。
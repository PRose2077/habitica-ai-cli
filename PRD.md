# Habitica-Forge 产品需求文档 (PRD)

## 一、 项目概述

### 1.1 项目名称
**Habitica-Forge (生命锻造炉)**

### 1.2 项目定位
一个基于 Habitica API 的高效、极简、智能的命令行 (CLI) 增强工具。它不维护本地业务数据库，将 Habitica 云端作为唯一事实来源，通过 AI 赋予任务“智能拆解”、“悬赏掉落”与“动态腐烂”的游戏化体验。

### 1.3 核心设计原则
*   **云端原生 (Cloud-Native)**：所有状态（任务、称号、腐烂等级）存储在 Habitica。
*   **极致响应 (Async First)**：非交互式 LLM 调用（称号生成、腐烂重写）必须在后台执行，不得阻塞 CLI 主流程。
*   **智能节省 (Token Efficiency)**：腐烂任务重写采用批量处理（Batch），降低 Token 消耗。

---

## 二、 核心功能模块

### 2.1 智能任务拆解 (Smart Forge)
*   **功能**：将模糊的描述转化为具体的 Checklist。
*   **动作**：用户执行 `forge smart "任务内容"`。
*   **AI 逻辑**：根据当前“游戏化风格”拆解子任务，并根据复杂度自动建议难度。
*   **交互**：展示炫酷加载动画（Spinner），此为前台阻塞操作。

### 2.2 称号与悬赏掉落系统 (Loot & Title System)
取代传统的经验槽模式，采用随机悬赏掉落机制。

#### 2.2.1 掉落算法
*   **触发条件**：创建或更新任务时，计算 `Drop_Score = (难度权重 × 类型权重) + RNG(随机数)`。
*   **权重控制**：通过 `.env` 设置（如 `WEIGHT_TODO=1.0`, `WEIGHT_DAILY=0.3`, `DAILY_STREAK_BONUS=0.05`）。
*   **阈值判定**：若 `Drop_Score >= TITLE_THRESHOLD`，则触发称号生成。

#### 2.2.2 称号生成（异步后台）
*   **流程**：CLI 立即返回任务创建成功的提示，后台启动子进程调用 LLM。
*   **LLM 逻辑**：根据任务内容与用户现有称号墙（Tags），生成进阶或新系列称号名。
*   **云端标记**：调用 API 在该任务挂载标签 `【WALL待激活】称号名`。

#### 2.2.3 称号激活与佩戴
*   **激活**：当 CLI 扫描到带有 `【WALL待激活】` 标签的任务已完成（`completed: true`），自动将标签重命名为 `【WALL】称号名`（正式解锁）。
*   **佩戴**：用户执行 `forge switch`，将目标标签改为 `【WALL No.1】称号名`。CLI 启动时读取带 `No.1` 的标签作为命令行前缀展示。

### 2.3 任务腐烂系统 (Corruption System)
对过期未完成的任务进行黑化重写。

#### 2.3.1 腐烂判定
*   **扫描逻辑**：对比任务 `updatedAt` 时间。
*   **标记**：在任务 `notes` 字段记录 `<!-- CORRUPTED_LVL: x -->`。

#### 2.3.2 批量黑化 (Batch Rewriting)
*   **优化**：单次调用 LLM 传入 5-10 个任务列表进行批量重写，极大地节省 Token。
*   **表现**：由积极描述变为压抑、嘲讽或深渊感的文案。

#### 2.3.3 触发机制（双模运行）
*   **方式 A (Server Mode)**：服务器部署 `scanner.py` 通过 `cron` 每 X 小时运行。
*   **方式 B (Local Mode - 默认)**：CLI 启动时检测 `last_scan_time`。若超时（如 > 12h），**静默唤起后台子进程**执行 `scanner.py`，不干扰用户当前命令。

---

## 三、 系统架构设计

### 3.1 数据存储架构 (Zero Local DB)
*   **唯一真理 (SSOT)**：Habitica API。
*   **本地缓存 (Cache)**：`~/.config/habitica-forge/cache/` 存储任务列表、Tags 映射。TTL 设为 5 分钟。
*   **本地配置 (Config)**：`.env` 存储 API Keys、权重参数、风格选择。

### 3.2 异步并发模型
*   **前台任务**：`list`, `show`, `done`, `smart`（带动画）。
*   **后台静默任务**：称号生成子进程、`scanner.py` 腐烂扫描进程。
*   **并发限速**：针对 Habitica 429 限制，后台更新使用 `asyncio.Semaphore` 限制并发数（建议为 3）。

---

## 四、 关键交互设计

### 4.1 CLI 命令设计
*   `forge list`：秒开列表，前缀显示当前佩戴称号。
*   `forge smart <desc>`：启动拆解，同步等待。
*   `forge sync`：强制刷新缓存，从云端全量同步任务与标签。
*   `forge wall`：解析云端 `【WALL】` 标签并渲染 ASCII 成就墙。
*   `forge switch <name>`：更换佩戴称号。

### 4.2 性能目标
*   **冷启动响应**：有缓存时 `< 500ms`。
*   **API 交互**：由网络环境决定，但后台进程不得占用 CPU 资源影响前台渲染。

---

## 五、 环境配置 (.env)

```bash
# 核心凭证
HABITICA_USER_ID=xxx
HABITICA_API_TOKEN=xxx
LLM_API_KEY=xxx
LLM_BASE_URL=xxx

# 权重与算法
WEIGHT_TODO=1.0
WEIGHT_DAILY=0.3
TITLE_THRESHOLD=8.5   # 触发掉落的阈值
SCAN_INTERVAL_HOURS=12 # 腐烂扫描间隔

# 游戏化风格
FORGE_STYLE=Cyberpunk # 赛博朋克, Wuxia, Fantasy...
```

---

## 六、 安全与隐私
1.  **脱敏日志**：所有后台日志不得记录用户的 API Token。
2.  **内容安全**：批量黑化 Prompt 需包含安全边界，禁止生成真实人身攻击文案。
3.  **原子更新**：即使后台进程中途崩溃，也不得损坏远端任务的完整性。

---

## 七、 验收标准
1.  **无状态验证**：删除本地 `~/.config/` 目录后执行 `forge sync`，能完美恢复称号墙与任务状态。
2.  **异步验证**：后台生成称号时，用户仍能流畅执行 `forge list`。
3.  **批量验证**：通过日志确认 5 个任务腐烂重写仅消耗了 1 次大模型请求。
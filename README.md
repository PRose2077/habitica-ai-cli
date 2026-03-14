# Habitica-Forge (生命锻造炉)

一个基于 Habitica API 的高效、极简、智能的命令行 (CLI) 增强工具。通过 AI 赋予任务"智能拆解"的游戏化体验。

## 功能特性

- **智能任务拆解**: 使用 AI 将模糊的任务描述转化为清晰可执行的子任务步骤
- **多种游戏风格**: 支持赛博朋克、武侠、奇幻等多种风格，让任务更有趣味性
- **云端原生**: 所有状态存储在 Habitica 云端，无需本地数据库
- **本地缓存**: 5 分钟 TTL 缓存，提升响应速度
- **脱敏日志**: 所有日志自动过滤敏感信息

## 安装

### 环境要求

- Python 3.11+
- uv (推荐) 或 pip

### 使用 uv 安装

```bash
# 克隆仓库
git clone https://github.com/your-repo/habitica-forge.git
cd habitica-forge

# 安装依赖
uv sync
```

### 使用 pip 安装

```bash
pip install -e .
```

## 配置

### 1. 创建配置文件

复制示例配置文件：

```bash
cp .env.example .env
```

### 2. 编辑配置文件

```bash
# Habitica 认证（必填）
# 在 https://habitica.com/user/settings/api 获取
HABITICA_USER_ID=your-uuid-here
HABITICA_API_TOKEN=your-api-token-here

# LLM 引擎认证（必填）
# 支持 OpenAI 兼容的 API
LLM_API_KEY=your-llm-api-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# 游戏化风格（可选）
# 可选值: Cyberpunk, Wuxia, Fantasy
FORGE_STYLE=Cyberpunk

# 日志级别（可选）
LOG_LEVEL=WARNING
```

### 3. 验证配置

```bash
forge init
```

---

## 命令详解

### 基础命令

#### `forge version`

显示版本信息。

```bash
forge version
```

#### `forge init`

验证配置文件是否正确。

```bash
forge init
```

#### `forge sync`

清空本地缓存并从 Habitica 拉取最新数据。

```bash
forge sync
```

---

### 任务查看

#### `forge list`

显示任务列表。

```bash
# 显示所有待办 Todo
forge list

# 只显示 Todo
forge list -t todos

# 只显示习惯
forge list -t habits

# 只显示每日任务
forge list -t dailys

# 只显示奖励
forge list -t rewards

# 显示所有类型的任务
forge list --all
```

**选项:**
| 选项 | 说明 |
|------|------|
| `-t, --type` | 任务类型: todos, dailys, habits, rewards |
| `-a, --all` | 显示所有类型所有状态的任务 |

#### `forge show`

显示任务详情，包含子任务列表。

```bash
# 通过编号查看
forge show 1

# 通过完整或部分 ID 查看
forge show abc12345
```

---

### 任务操作

#### `forge add`

添加新任务。

```bash
# 基本添加
forge add "完成项目报告"

# 添加带备注的任务
forge add "写代码" -n "重要项目"

# 指定难度
forge add "读书" -p hard

# 指定截止日期
forge add "提交报告" -d 2024-12-31

# 添加标签
forge add "学习英语" -t "学习,重要"
```

**选项:**
| 选项 | 说明 |
|------|------|
| `-n, --notes` | 任务备注 |
| `-p, --priority` | 难度: trivial, easy, medium, hard |
| `-d, --due` | 截止日期 (YYYY-MM-DD) |
| `-t, --tags` | 标签，逗号分隔 |

#### `forge done`

完成任务。

```bash
# 通过编号完成
forge done 1

# 通过 ID 完成
forge done abc12345
```

#### `forge undone`

取消完成任务（将任务标记为未完成）。

```bash
forge undone 1
```

#### `forge update`

更新任务。

```bash
# 更新任务内容
forge update 1 -t "新任务内容"

# 更新备注
forge update 1 -n "新备注"

# 更新难度
forge update 1 -p hard

# 同时更新多个字段
forge update 1 -t "新内容" -n "新备注" -p medium
```

**选项:**
| 选项 | 说明 |
|------|------|
| `-t, --text` | 更新任务内容 |
| `-n, --notes` | 更新备注 |
| `-p, --priority` | 更新难度: trivial, easy, medium, hard |

#### `forge delete`

删除任务。

```bash
# 删除（需要确认）
forge delete 1

# 强制删除（不需要确认）
forge delete 1 -f
```

---

### 子任务操作

#### `forge sub-add`

添加子任务。

```bash
# 通过编号添加
forge sub-add 1 "阅读文档"

# 通过 ID 添加
forge sub-add abc12345 "编写测试"
```

#### `forge sub-done`

完成子任务。

```bash
# 通过编号完成子任务
forge sub-done 1 1

# 通过 ID 完成
forge sub-done abc12345 xyz789
```

#### `forge sub-del`

删除子任务。

```bash
# 通过编号删除
forge sub-del 1 1

# 通过 ID 删除
forge sub-del abc12345 xyz789
```

---

### AI 智能拆解

#### `forge smart-add`

智能添加任务，AI 自动分析任务描述并拆解为子任务。

```bash
# 基本使用 - AI 自动拆解
forge smart-add "完成项目报告"

# 添加备注
forge smart-add "学习新技术" -n "重要技能"

# 不拆解，只让 AI 优化标题
forge smart-add "简单任务" --no-decompose
```

**选项:**
| 选项 | 说明 |
|------|------|
| `-n, --notes` | 任务备注 |
| `--no-decompose` | 不拆解，只让 AI 优化标题 |

**AI 输出示例:**

```
✓ 任务已智能创建: abc12345

 完成项目报告
分析当前项目进度并制定详细的执行计划

建议难度: medium

拆解的子任务 (5):
  1. 接入神经网络 - 收集项目相关资料
  2. 破解数据节点 - 分析项目需求文档
  3. 上传意识备份 - 制定项目时间表
  4. 启动核心程序 - 执行第一阶段开发
  5. 同步虚拟实境 - 进行项目测试
```

#### `forge smart-task`

智能拆解现有任务，将模糊的任务转化为清晰的子任务步骤。

```bash
# 拆解编号为 1 的任务
forge smart-task 1

# 拆解指定 ID 的任务
forge smart-task abc12345

# 保留现有子任务并在基础上优化
forge smart-task 1 --keep
```

**选项:**
| 选项 | 说明 |
|------|------|
| `-k, --keep` | 保留现有子任务并在基础上优化 |

#### `forge smart refine`

优化现有任务的子任务，重新组织和改进。

```bash
# 优化任务的子任务
forge smart refine 1

# 通过 ID 优化
forge smart refine abc12345
```

---

### 命令速查表

| 命令 | 说明 |
|------|------|
| `forge version` | 显示版本信息 |
| `forge init` | 验证配置 |
| `forge sync` | 同步数据 |
| `forge list` | 显示任务列表 |
| `forge show <ID>` | 显示任务详情 |
| `forge add <text>` | 添加任务 |
| `forge done <ID>` | 完成任务 |
| `forge undone <ID>` | 取消完成 |
| `forge update <ID>` | 更新任务 |
| `forge delete <ID>` | 删除任务 |
| `forge sub-add <ID> <text>` | 添加子任务 |
| `forge sub-done <ID> <itemID>` | 完成子任务 |
| `forge sub-del <ID> <itemID>` | 删除子任务 |
| `forge smart-add <text>` | 智能添加任务 |
| `forge smart-task <ID>` | 智能拆解任务 |
| `forge smart refine <ID>` | 优化子任务 |

---

## 游戏化风格

支持三种风格，通过 `.env` 文件的 `FORGE_STYLE` 配置：

### Cyberpunk (赛博朋克)

```bash
FORGE_STYLE=Cyberpunk
```

子任务描述带有霓虹灯、数据流、黑客、神经网络等赛博朋克元素。

### Wuxia (武侠)

```bash
FORGE_STYLE=Wuxia
```

子任务描述带有武功、门派、江湖、修炼等武侠元素。

### Fantasy (奇幻)

```bash
FORGE_STYLE=Fantasy
```

子任务描述带有魔法、龙、精灵、地下城等奇幻元素。

---

## 项目结构

```
habitica-forge/
├── src/habitica_forge/
│   ├── ai/                    # AI 模块
│   │   ├── __init__.py
│   │   └── llm_client.py      # LLM 客户端
│   ├── cli/                   # CLI 命令模块
│   │   ├── __init__.py
│   │   ├── commands.py        # 任务命令
│   │   ├── main.py            # CLI 主入口
│   │   ├── smart.py           # 智能拆解命令
│   │   └── viewer.py          # 任务展示
│   ├── clients/               # API 客户端
│   │   ├── __init__.py
│   │   └── habitica.py        # Habitica API 客户端
│   ├── core/                  # 核心模块
│   │   ├── __init__.py
│   │   ├── cache.py           # 本地缓存
│   │   └── config.py          # 配置管理
│   ├── models.py              # 数据模型
│   └── __init__.py
├── tests/                     # 测试文件
├── .env.example               # 配置示例
├── pyproject.toml             # 项目配置
└── README.md
```

---

## 开发指南

### 运行测试

```bash
# 运行所有测试
uv run python -m pytest

# 运行指定测试文件
uv run python -m pytest tests/test_llm_client.py -v
```

### 代码风格

项目使用 Python 3.11+ 特性，包括：
- Type hints
- Pydantic v2 数据验证
- Async/await 异步编程

---

## 许可证

MIT License
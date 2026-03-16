# Habitica-Forge (生命锻造炉)

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Habitica](https://img.shields.io/badge/Habitica-API-purple.svg)](https://habitica.com/)

一个基于 Habitica API 的**高效、极简、智能**的命令行 (CLI) 增强工具。通过 AI 赋予任务"智能拆解"的游戏化体验，让待办事项管理变成一场冒险。

## 核心特性

- **智能任务拆解**: 使用 AI 将模糊的任务描述转化为清晰可执行的子任务步骤
- **称号系统**: 完成任务有机会获得独特称号，打造专属身份标识
- **腐烂系统**: 长期未处理的任务会"腐化"，产生紧迫感驱动行动
- **多种游戏风格**: 支持赛博朋克、武侠、奇幻等多种风格
- **云端原生**: 所有状态存储在 Habitica 云端，无需本地数据库
- **本地缓存**: 5 分钟 TTL 缓存，极速响应
- **脱敏日志**: 所有日志自动过滤敏感信息

## 安装

### 环境要求

- Python 3.11+
- uv (推荐) 或 pip

### 使用 uv 安装

```bash
# 克隆仓库
git clone https://github.com/your-username/habitica-forge.git
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

```bash
cp .env.example .env
```

### 2. 获取 API 凭证

- **Habitica**: 访问 https://habitica.com/user/settings/api 获取 `User ID` 和 `API Token`
- **LLM**: 支持 OpenAI 兼容的 API（如 OpenAI、DeepSeek、Moonshot 等）

### 3. 编辑配置文件

```bash
# Habitica 认证（必填）
HABITICA_USER_ID=your-uuid-here
HABITICA_API_TOKEN=your-api-token-here

# LLM 引擎认证（必填）
LLM_API_KEY=your-llm-api-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# 游戏化风格（可选）
FORGE_STYLE=normal

# 日志级别（可选）
LOG_LEVEL=WARNING
```

### 4. 验证配置

```bash
forge init
```

---

## 快速开始

```
ID: 480ac1e2...  |  称号: 【数据猎手】  |  状态: 就绪

 No.  状态  任务                        难度      进度       日期
  1   ○    完成项目报告               medium    ====-    50%   今天
  2   ○    学习新技术                 easy      --          明天
  3   ○    整理文档                   trivial   --          3天后
```

---

## 命令详解

### 基础命令

| 命令 | 说明 |
|------|------|
| `forge version` | 显示版本信息 |
| `forge init` | 验证配置文件 |
| `forge sync` | 清空缓存并从 Habitica 拉取最新数据 |

### 任务查看

#### `forge list` - 显示任务列表

```bash
forge list              # 显示待办 Todo
forge list -t habits    # 只显示习惯
forge list -t dailys    # 只显示每日任务
forge list --all        # 显示所有类型的任务
```

#### `forge show` - 显示任务详情

```bash
forge show 1          # 通过编号查看
forge show abc12345   # 通过 ID 查看
```

### 任务操作

| 命令 | 说明 |
|------|------|
| `forge add <text>` | 添加任务 |
| `forge done <ID>` | 完成任务 |
| `forge undone <ID>` | 取消完成 |
| `forge update <ID>` | 更新任务 |
| `forge delete <ID>` | 删除任务 |

```bash
# 添加任务示例
forge add "完成项目报告" -n "重要项目" -p hard -d 2024-12-31 -t "工作,重要"
```

**选项:**
| 选项 | 说明 |
|------|------|
| `-n, --notes` | 任务备注 |
| `-p, --priority` | 难度: trivial, easy, medium, hard |
| `-d, --due` | 截止日期 (YYYY-MM-DD) |
| `-t, --tags` | 标签，逗号分隔 |

### 子任务操作

| 命令 | 说明 |
|------|------|
| `forge sub-add <ID> <text>` | 添加子任务 |
| `forge sub-done <ID> <itemID>` | 完成子任务 |
| `forge sub-del <ID> <itemID>` | 删除子任务 |

```bash
forge sub-add 1 "阅读文档"
forge sub-done 1 1
```

---

### AI 智能拆解

#### `forge smart-add` - 智能添加任务

AI 自动分析任务描述并拆解为子任务。

```bash
forge smart-add "完成项目报告"
```

**输出示例:**

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

#### `forge smart-task` - 智能拆解现有任务

```bash
forge smart-task 1           # 拆解任务
forge smart-task 1 --keep    # 保留现有子任务
```

#### `forge edit` - 针对性修改任务字段

根据提供的额外上下文信息，让 AI 针对性修改任务的标题、备注或子任务。

```bash
forge edit 2 -f title -c "周报是在飞书上写的"
forge edit 1 -f notes -c "这是给客户演示用的"
forge edit 3 -f checklist -c "需要在下午 5 点前完成"
```

**选项:**
| 选项 | 说明 |
|------|------|
| `-f, --field` | 要修改的字段: `title`(标题)、`notes`(备注)、`checklist`(子任务)，默认 `title` |
| `-c, --context` | 提供给 AI 的额外上下文信息（必需） |

**输出示例:**

```
✓ 任务title已优化: beb2e887

AI 说明: 根据用户提供的额外信息，周报是在飞书上写的，因此将标题优化为更具体地指明平台。

原内容: 生成工作周报数据流
新内容: 生成飞书工作周报数据流
```

---

### 称号系统

完成任务有机会获得独特称号！

#### `forge wall` - 显示成就墙

```
═══════════════════════════════════════
        🏆 成 就 墙 🏆
═══════════════════════════════════════

  1. ★ 数据猎手 (佩戴中)
  2. ○ 星尘征服者
  3. ○ 筑基期修士

已解锁 3 个称号

使用 forge switch <编号> 来佩戴称号
```

#### `forge switch` - 佩戴称号

```bash
forge switch 1           # 通过编号佩戴
forge switch 星尘征服者   # 通过名称佩戴
```

**称号掉落机制:**

```
Drop_Score = (难度权重 × 类型权重) + RNG + 连击奖励
```

- 高难度任务更容易掉落称号
- Daily 任务有连击加成
- 掉落概率可配置

---

### 风格管理

#### `forge style` - 查看当前风格

```bash
forge style        # 显示当前风格
forge style list   # 列出所有可用风格
```

#### `forge style switch` - 切换风格

```bash
forge style switch cyberpunk   # 切换到赛博朋克风格
forge style switch normal      # 切换到正常风格
```

---

### 腐烂系统

长期未处理的任务会逐渐"腐化"，标题会被 AI 黑化为带有紧迫感的风格：

```
原始: 完成项目报告
腐化: 【数据腐蚀】修复崩溃的项目报告系统
```

- **自动扫描**: 每次执行 `forge list` 时自动检查
- **扫描间隔**: 默认 12 小时
- **腐烂等级**: 最多 3 级，已满级的任务不再腐化
- **后台运行**: 扫描在后台静默进行，不阻塞主流程

---

## 游戏化风格

支持多种风格，通过 `.env` 文件的 `FORGE_STYLE` 配置，或使用 CLI 命令动态切换。

### 可用风格

| 风格 | 描述 | 示例子任务 |
|------|------|------------|
| `normal` | 克制、直接、低装饰的文案（默认） | "收集资料"、"分析需求" |
| `cyberpunk` | 霓虹灯、数据流、神经网络等科技感元素 | "接入神经网络收集资料" |
| `wuxia` | 武功、门派、江湖、修炼等武侠元素 | "修炼内功打牢基础" |
| `fantasy` | 魔法、龙、精灵、地下城等奇幻元素 | "探索地牢收集材料" |

### 切换风格

```bash
# 查看当前风格
forge style

# 列出所有可用风格
forge style list

# 切换风格
forge style switch cyberpunk   # 切换到赛博朋克风格
forge style switch normal      # 切换到正常风格
forge style switch wuxia       # 切换到武侠风格
forge style switch fantasy     # 切换到奇幻风格
```

### 风格影响范围

风格影响以下功能的 AI 文案：
- 智能任务拆解 (`forge smart-add`, `forge smart-task`)
- 称号生成
- 任务腐烂文案

### 添加新风格

只需在 `src/habitica_forge/styles/` 目录下创建新的 YAML 文件即可：

```yaml
# my_style.yaml
name: my_style
display_name: 我的风格
description: 风格描述

variables:
  # 风格基本信息
  style_name: "我的风格"
  style_description: "风格特点"
  style_elements: "关键元素1、关键元素2"

  # 黑化主题
  corruption_theme: "腐化主题描述"
  corruption_elements: "腐化元素"

  # Few-shot 示例（用于任务拆解、称号生成、黑化等）
  example_decompose_1: "示例1"
  example_decompose_2: "示例2"
  # ... 更多示例变量
```

**风格系统架构：**

```
src/habitica_forge/styles/
├── __init__.py           # 公开接口
├── loader.py             # 配置加载和模板渲染
├── base_template.yaml    # 基础提示词模板（Few-shot）
├── normal.yaml           # 正常风格变量
├── cyberpunk.yaml        # 赛博朋克风格变量
├── wuxia.yaml            # 武侠风格变量
└── fantasy.yaml          # 奇幻风格变量
```

- `base_template.yaml`: 定义所有提示词的通用结构（Few-shot 格式）
- 各风格 YAML: 只需填写变量（风格名称、示例等）
- 修改提示词结构只需改 `base_template.yaml`，所有风格自动生效

---

## 项目结构

```
habitica-forge/
├── src/habitica_forge/
│   ├── ai/                    # AI 模块
│   │   └── llm_client.py      # LLM 客户端
│   ├── cli/                   # CLI 命令模块
│   │   ├── commands.py        # 任务命令
│   │   ├── header.py          # 身份标识 Header
│   │   ├── main.py            # CLI 主入口
│   │   ├── smart.py           # 智能拆解命令
│   │   ├── style.py           # 风格管理命令
│   │   └── viewer.py          # 任务展示
│   ├── clients/               # API 客户端
│   │   └── habitica.py        # Habitica API 客户端
│   ├── core/                  # 核心模块
│   │   ├── bounty.py          # 称号掉落算法
│   │   ├── cache.py           # 本地缓存
│   │   ├── config.py          # 配置管理
│   │   └── style.py           # 风格管理
│   ├── schedule/              # 后台任务
│   │   └── scanner.py         # 腐烂扫描器
│   ├── scripts/               # 独立脚本
│   │   └── title_generator.py # 称号生成器
│   ├── styles/                # 风格配置
│   │   ├── __init__.py        # 公开接口
│   │   ├── loader.py          # 配置加载和模板渲染
│   │   ├── base_template.yaml # 基础提示词模板
│   │   ├── normal.yaml        # 正常风格
│   │   ├── cyberpunk.yaml     # 赛博朋克风格
│   │   ├── wuxia.yaml         # 武侠风格
│   │   └── fantasy.yaml       # 奇幻风格
│   └── models.py              # 数据模型
├── tests/                     # 测试文件
├── .env.example               # 配置示例
├── pyproject.toml             # 项目配置
└── README.md
```

---

## 配置项说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `HABITICA_USER_ID` | Habitica 用户 ID | (必填) |
| `HABITICA_API_TOKEN` | Habitica API Token | (必填) |
| `LLM_API_KEY` | LLM API Key | (必填) |
| `LLM_BASE_URL` | LLM API 地址 | `https://api.openai.com/v1` |
| `LLM_MODEL` | LLM 模型名称 | `gpt-4o-mini` |
| `FORGE_STYLE` | 游戏化风格 | `normal` |
| `TITLE_THRESHOLD` | 称号掉落阈值 | `8.5` |
| `SCAN_INTERVAL_HOURS` | 腐烂扫描间隔 | `12` |
| `LOG_LEVEL` | 日志级别 | `WARNING` |

---

## 开发指南

### 运行测试

```bash
uv run python -m pytest
```

### 代码风格

- Python 3.11+ 特性
- Type hints
- Pydantic v2 数据验证
- Async/await 异步编程

---

## 许可证

[MIT License](LICENSE)

---

## 致谢

- [Habitica](https://habitica.com/) - 游戏化任务管理平台
- [Rich](https://github.com/Textualize/rich) - 优秀的终端渲染库
- [Typer](https://typer.tiangolo.com/) - 现代化的 CLI 框架
# MCPBench MCP Service 架构分析

## 🏗️ 总体架构概述

MCPBench 项目采用了清晰的分层架构和工厂模式来支持多种 MCP (Model Context Protocol) 服务的集成。该架构设计具有高度的可扩展性和模块化特性。

### 架构核心原则

1. **抽象层分离**: 通过基础抽象类定义通用接口
2. **工厂模式**: 统一的服务创建和管理机制  
3. **配置驱动**: 基于环境变量的灵活配置系统
4. **异步执行**: 支持高性能的异步任务处理

## 🔧 核心组件层次

```
┌─────────────────────────────────────────────────────────────┐
│                    MCPBench Architecture                    │
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │   Factory       │    │   Config        │                │
│  │   Pattern       │    │   Management    │                │
│  └─────────────────┘    └─────────────────┘                │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                Base Abstractions                        ││
│  │  ┌──────────────┐ ┌───────────────┐ ┌────────────────┐ ││
│  │  │ TaskManager  │ │ StateManager  │ │ LoginHelper    │ ││
│  │  │   (ABC)      │ │    (ABC)      │ │    (ABC)       │ ││
│  │  └──────────────┘ └───────────────┘ └────────────────┘ ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │            Service Implementations                       ││
│  │  ┌─────────┐    ┌─────────┐    ┌──────────────┐        ││
│  │  │ Notion  │    │ GitHub  │    │ PostgreSQL   │        ││
│  │  │Service  │    │Service  │    │  Service     │        ││
│  │  └─────────┘    └─────────┘    └──────────────┘        ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## 📁 目录结构

```
src/mcp_services/
├── notion/              # Notion MCP 服务实现 (参考实现)
│   ├── notion_task_manager.py
│   ├── notion_state_manager.py
│   └── notion_login_helper.py
├── github/              # GitHub MCP 服务实现 (待实现)
└── postgres/            # PostgreSQL MCP 服务实现 (待实现)

src/base/                # 基础抽象类
├── task_manager.py
├── state_manager.py
└── login_helper.py

src/factory.py           # 服务工厂实现
```

## 🎯 设计模式详解

### 1. 工厂模式 (Factory Pattern)

**位置**: `src/factory.py`

工厂模式负责统一创建和管理不同 MCP 服务的组件实例：

```python
class ServiceFactory(ABC):
    @abstractmethod
    def create_task_manager(self, config: ServiceConfig, **kwargs) -> BaseTaskManager:
        pass
    
    @abstractmethod
    def create_state_manager(self, config: ServiceConfig, **kwargs) -> BaseStateManager:
        pass
    
    @abstractmethod
    def create_login_helper(self, config: ServiceConfig, **kwargs) -> BaseLoginHelper:
        pass
```

**优势**:
- 统一的创建接口
- 配置集中管理
- 易于扩展新服务

### 2. 策略模式 (Strategy Pattern)

每个 MCP 服务都实现相同的抽象接口，但具体实现策略不同：

- **Notion**: 基于 Playwright + Notion API
- **GitHub**: 基于 GitHub REST/GraphQL API  
- **PostgreSQL**: 基于 SQL 连接和查询

### 3. 模板方法模式 (Template Method)

基础管理器定义了通用的执行流程，具体服务实现各自的细节。

## 🔌 MCP 服务器集成模式

每个服务都通过 `MCPServerStdio` 来集成对应的 MCP 服务器：

```python
async def _create_mcp_server(self) -> MCPServerStdio:
    return MCPServerStdio(
        params={
            "command": "npx",
            "args": ["-y", "@service/mcp-server"],
            "env": {
                # 服务特定的环境变量配置
            },
        },
        client_session_timeout_seconds=120,
        cache_tools_list=True,
    )
```

## 📊 配置管理

### 环境变量配置

所有服务配置通过 `.mcp_env` 文件管理：

```bash
# Notion 配置
NOTION_SOURCE_API_KEY=secret_...
NOTION_EVAL_API_KEY=secret_...

# GitHub 配置  
GITHUB_TOKEN=ghp_...
GITHUB_WEBHOOK_SECRET=...

# PostgreSQL 配置
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=mcpbench
POSTGRES_USER=admin
POSTGRES_PASSWORD=...
```

### 配置类设计

```python
class ServiceConfig:
    def __init__(self, service_name: str, api_key_var: Optional[str] = None, 
                 additional_vars: Optional[Dict[str, str]] = None):
        # 自动加载环境变量
        # 验证必需配置
        # 提供配置访问接口
```

## 🚀 扩展新服务的步骤

1. **创建服务目录**: `src/mcp_services/{service_name}/`
2. **实现三个核心类**:
   - `{Service}TaskManager(BaseTaskManager)`
   - `{Service}StateManager(BaseStateManager)` 
   - `{Service}LoginHelper(BaseLoginHelper)`
3. **创建服务工厂**: `{Service}ServiceFactory(ServiceFactory)`
4. **注册到工厂注册表**: 在 `MCPServiceFactory` 中注册
5. **配置环境变量**: 在 `.mcp_env` 中添加相关配置

## 📈 架构优势

- ✅ **高度模块化**: 每个服务独立实现
- ✅ **易于测试**: 清晰的接口分离
- ✅ **配置灵活**: 环境变量驱动
- ✅ **异步支持**: 高性能任务执行
- ✅ **错误隔离**: 服务间互不影响
- ✅ **易于扩展**: 标准化的实现模式 
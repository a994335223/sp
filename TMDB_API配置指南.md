# TMDB API 配置指南

## 什么是 TMDB？

TMDB（The Movie Database）是全球最大的电影/电视剧数据库，提供：
- 详细的剧情简介
- 演员表和角色信息
- 分集剧情（电视剧）
- 海报和剧照
- **完全免费的API**

## 注册步骤（5分钟完成）

### 1. 注册账号

访问：https://www.themoviedb.org/signup

填写：
- 用户名
- 邮箱
- 密码

### 2. 验证邮箱

查收邮件，点击验证链接。

### 3. 申请 API Key

1. 登录后，点击右上角头像 → **设置**
2. 左侧菜单选择 **API**
3. 点击 **申请API密钥**
4. 选择 **Developer** （开发者）
5. 填写申请表：
   - 应用名称：`SmartVideoClipper`
   - 应用URL：`http://localhost`
   - 应用简介：`Video narration generation tool`
   - 接受条款

6. 提交后立即获得 **API Key (v3 auth)**

### 4. 配置到项目

#### 方式一：环境变量（推荐）

Windows PowerShell:
```powershell
$env:TMDB_API_KEY="你的API密钥"
```

Windows CMD:
```cmd
set TMDB_API_KEY=你的API密钥
```

永久配置（系统环境变量）:
1. 右键"此电脑" → 属性 → 高级系统设置
2. 环境变量 → 新建用户变量
3. 变量名：`TMDB_API_KEY`
4. 变量值：你的API密钥

#### 方式二：配置文件

编辑 `.env` 文件：
```
TMDB_API_KEY=你的API密钥
```

## 验证配置

运行以下命令验证：

```python
import os
print(os.environ.get("TMDB_API_KEY", "未配置"))
```

## API 使用限制

- 免费版：无限制请求
- 每秒最多40次请求（足够使用）

## 支持的功能

配置 TMDB API 后，系统将自动获取：

| 功能 | 说明 |
|------|------|
| 剧情简介 | 电影/电视剧的完整剧情 |
| 分集剧情 | 每一集的详细剧情 |
| 演员表 | 演员和角色对应关系 |
| 类型标签 | 犯罪、剧情、动作等 |
| 关键词 | 用于生成更精准的解说 |

## 常见问题

### Q: API Key 申请被拒绝？
A: 确保应用简介填写完整，通常会立即批准。

### Q: 中文剧情获取不到？
A: TMDB 对热门中国影视有中文数据，冷门作品可能只有英文。

### Q: 请求失败？
A: 检查网络连接，TMDB 在中国大陆可正常访问。

## 不想注册？

如果不配置 TMDB API，系统会：
1. 尝试从豆瓣获取（可能被封）
2. 使用 AI 分析字幕生成剧情（推荐）

但配置 TMDB 后，剧情信息更准确、更详细。


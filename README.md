# Docker 镜像导出工具

这是一个用于下载 Docker 镜像并导出为 tar 文件的 OOMOL 工作流工具，支持指定架构，可用于离线部署。

## ✨ 主要功能

- **多架构支持**：支持下载不同平台的 Docker 镜像（linux/amd64, linux/arm64 等）
- **灵活导出**：可以直接导出为 tar 文件，也可以自动按镜像名组织目录
- **离线部署**：导出的 tar 文件可在无网络环境中使用

## 📋 环境要求

- oomol

## 🚀 快速开始

### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `image_name` | 字符串 | 是 | Docker 镜像名称（如：`nginx:latest`） |
| `platform` | 字符串 | 是 | 目标平台（默认：`linux/amd64`） |
| `output_path` | 字符串 | 是 | 导出路径（自动识别模式） |

### 智能路径识别

工具会根据您输入的路径自动判断导出方式：

#### 直接导出为 tar 文件
如果路径以 `.tar` 结尾：
```
output_path: "nginx.tar"
# 输出：nginx.tar

output_path: "/path/to/my-image.tar"
# 输出：/path/to/my-image.tar
```

#### 目录模式自动命名
如果路径没有文件扩展名：
```
output_path: "./exports"
# 输出：./exports/nginx_latest.tar （对于 nginx:latest 镜像）

output_path: "backup"
# 输出：backup/nginx_latest.tar
```

## 💡 使用示例

### 示例 1：直接导出
```
image_name: nginx:latest
platform: linux/amd64
output_path: nginx.tar
```
**结果**：直接生成 `nginx.tar` 文件

### 示例 2：目录导出
```
image_name: ubuntu:20.04
platform: linux/amd64
output_path: ./docker-images
```
**结果**：在 `./docker-images/` 目录下生成 `ubuntu_20.04.tar`

### 示例 3：ARM64 架构导出
```
image_name: redis:alpine
platform: linux/arm64
output_path: ./backup
```
**结果**：在 `./backup/` 目录下生成 `redis_alpine.tar`

## 📋 支持的平台

- **Linux**: amd64, arm64, arm/v7, arm/v6, 386, ppc64le, s390x, riscv64
- **Windows**: amd64, arm64

## 📤 输出结果

任务执行后会返回：
- `export_path`: 导出的 tar 文件路径
- `image_id`: 下载的镜像 ID
- `image_size`: 文件大小（字节）
- `export_format`: 导出格式（"tar"）

## 📄 许可证

本工具仅供教育和开发用途使用。

如有问题或建议，请查看 OOMOL 文档或联系项目维护者。
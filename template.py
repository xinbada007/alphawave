# template.py
from e2b import Template, wait_for_timeout

# 定义你的量化环境
template = (
    Template()
    # 1. 使用 Ubuntu 22.04 基础镜像（最稳定）
    .from_template("hixuxin/alphawave-quant")
    
    # 2. 设置工作目录
    .set_workdir("/home/user")
    
    # 3. 安装系统依赖 (apt_install)
    .apt_install(["git", "build-essential", "libpq-dev"])
    
    # 4. 拷贝你的整个项目到沙箱
    # 第一个参数是本地路径，第二个是沙箱内路径
    .copy(".", "/home/user")
    
    # 5. 安装 Python 依赖
    # 这里我们直接运行 shell 命令来安装 requirements.txt 里的所有库
    .run_cmd("pip install --no-cache-dir -r requirements.txt")
    
    # 6. 设置环境变量，确保 Python 能找到 alphaflow 文件夹
    .set_envs({
        "PYTHONPATH": "/home/user",
        "PYTHONUNBUFFERED": "1"
    })
)

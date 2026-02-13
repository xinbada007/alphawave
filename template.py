from e2b import Template

template = (
    Template()
    # 1. 使用基础镜像
    .from_template("hixuxin/openbb-box")

    # 第一步：删除可能存在的旧目录（确保环境干净）
    .run_cmd("rm -rf /home/user/alpha")

    # 第二步：将本地当前目录内容拷贝到沙箱的 /home/user/alpha
    # E2B 会自动创建不存在的父目录
    .copy(".", "/home/user/alpha")

    # 第三步：将默认工作目录设置为该目录
    # 这样沙箱启动时，命令都会在这个目录下执行
    .set_workdir("/home/user/alpha")

    # 4. 安装系统依赖
    .apt_install(["git", "build-essential", "libpq-dev"])

    # 5. 安装 Python 依赖（在新的工作目录下执行）
    .run_cmd("pip install --no-cache-dir -r requirements.txt")

    # 6. 更新环境变量
    # 确保 PYTHONPATH 指向新的 alpha 目录
    .set_envs({
        "PYTHONPATH": "/home/user/alpha",
        "PYTHONUNBUFFERED": "1"
    })
)

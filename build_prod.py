# build_prod.py
import os
from dotenv import load_dotenv
from e2b import Template, default_build_logger
from template import template  # 导入刚才定义的 template

load_dotenv()

if __name__ == '__main__':
    print("🚀 正在通过最新 SDK 启动云端构建...")
    
    # 确保环境变量中有 E2B_API_KEY
    if not os.getenv("E2B_API_KEY"):
        print("❌ 错误：请在 .env 文件中设置 E2B_API_KEY")
        exit(1)

    Template.build(
        template,
        'alphawave-quant',      # 模板名称（Tag）
        cpu_count=2,            # 核心数
        memory_mb=2048,         # 内存
        on_build_logs=default_build_logger(), # 实时打印云端构建进度
    )
    print("\n✅ 构建成功！现在你可以使用 'alphawave-quant' 启动沙箱了。")

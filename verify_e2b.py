from e2b import Sandbox
from dotenv import load_dotenv

load_dotenv()

TEMPLATE_ID = "alphawave-quant"

def verify():
    # 既然 Sandbox(TEMPLATE_ID) 能启动并打印 ID，说明初始化没问题
    with Sandbox.create(TEMPLATE_ID) as sbx:
        print(f"✅ 沙箱已启动 (ID: {sbx.sandbox_id})")

        # 最新 SDK 语法：使用 sbx.commands.run()
        
        # 1. 检查文件列表
        print("\n--- 1. 检查文件列表 ---")
        # 注意这里是 .commands.run
        ls_result = sbx.commands.run("ls -F /home/user")
        print(ls_result.stdout)
        
        # 2. 检查 Python 环境与 Import
        print("\n--- 2. 检查 Python 环境与 Import ---")
        import_cmd = "python3 -c 'import alphaflow; print(\"Import alphaflow success!\")'"
        check_import = sbx.commands.run(import_cmd)
        
        print(check_import.stdout)
        if check_import.stderr:
            print("Import 错误日志:", check_import.stderr)

        # 3. 运行你的 main.py 测试
        print("\n--- 3. 运行 main.py 测试 ---")
        run_main = sbx.commands.run("python3 main.py")
        
        print("--- [stdout] ---")
        print(run_main.stdout)
        
        if run_main.stderr:
            print("--- [stderr] ---")
            print(run_main.stderr)

if __name__ == "__main__":
    verify()

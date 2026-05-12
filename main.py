import sys

from cli import main as cli_main


def serve():
    """启动 HTTP 服务（llmbox serve）。"""
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)


def cli_entry():
    """llmbox 命令行入口，支持子命令 serve。"""
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        # 移除 "serve" 子命令，让 uvicorn 正常解析剩余参数
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        serve()
    else:
        cli_main()


if __name__ == "__main__":
    cli_entry()

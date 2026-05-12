import argparse
import sys

from cli import main as cli_main


def serve(host: str = "0.0.0.0", port: int = 8000):
    """启动 HTTP 服务（llmbox serve）。"""
    import uvicorn
    uvicorn.run("server:app", host=host, port=port, reload=False)


def cli_entry():
    """llmbox 命令行入口，支持子命令 serve。"""
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        parser = argparse.ArgumentParser(prog="llmbox serve", description="启动 HTTP 服务")
        parser.add_argument("--host", default="0.0.0.0", help="监听地址（默认 0.0.0.0）")
        parser.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
        args = parser.parse_args(sys.argv[2:])
        serve(host=args.host, port=args.port)
    else:
        cli_main()


if __name__ == "__main__":
    cli_entry()

import argparse
import sys
from pathlib import Path

from cli import main as cli_main


def serve(host: str = "0.0.0.0", port: int = 8000):
    """启动 HTTP 服务（llmbox serve）。"""
    import uvicorn
    uvicorn.run("server:app", host=host, port=port, reload=False)


def init_config(path: str = "llmbox.toml"):
    """创建默认配置文件。"""
    from core.config import create_default_config
    p = Path(path)
    if p.exists():
        print(f"配置文件已存在: {p}")
        return
    create_default_config(p)
    print(f"已创建配置文件: {p}")


def cli_entry():
    """llmbox 命令行入口，支持子命令。"""
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        parser = argparse.ArgumentParser(prog="llmbox serve", description="启动 HTTP 服务")
        parser.add_argument("--host", default="0.0.0.0", help="监听地址（默认 0.0.0.0）")
        parser.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
        args = parser.parse_args(sys.argv[2:])
        serve(host=args.host, port=args.port)
    elif len(sys.argv) > 1 and sys.argv[1] == "init":
        parser = argparse.ArgumentParser(prog="llmbox init", description="创建默认配置文件")
        parser.add_argument("--path", default="llmbox.toml", help="配置文件路径（默认 llmbox.toml）")
        args = parser.parse_args(sys.argv[2:])
        init_config(args.path)
    else:
        cli_main()


if __name__ == "__main__":
    cli_entry()

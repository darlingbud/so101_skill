"""Typer CLI commands for RobotAgent."""

import logging
import sys
from pathlib import Path

import typer
from rich import print

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from robot_agent.core import RobotAgent
from robot_agent.config import DEFAULT_HOST, DEFAULT_PORT

app = typer.Typer(
    help="Robot Agent 命令行管理工具",
    add_completion=False,
    rich_markup_mode="rich",
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)


@app.callback()
def main(
    ctx: typer.Context,
    host: str = typer.Option(DEFAULT_HOST, "--host", "-H", help="服务器 IP 地址"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-P", help="服务器通信端口"),
    debug: bool = typer.Option(False, "--debug", "-d", help="开启 debug 日志"),
):
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Debug logging enabled")
    ctx.obj = RobotAgent(host=host, port=port)


@app.command()
def connect(
    ctx: typer.Context,
    port_name: str = typer.Option("/dev/ttyACM0", "--port-name", "-p", help="机械臂串口路径"),
    robot_id: str = typer.Option("my_awesome_follower_arm", "--id", help="机器人唯一标识"),
):
    """启动并连接机器人服务器"""
    agent: RobotAgent = ctx.obj
    agent.port_name = port_name
    agent.robot_id = robot_id
    agent.connect()


@app.command()
def disconnect(ctx: typer.Context):
    """停止机器人服务器并断开连接"""
    agent: RobotAgent = ctx.obj
    agent.disconnect()


@app.command()
def status(ctx: typer.Context):
    """查看机器人当前状态"""
    print(ctx.obj.status())


@app.command()
def get(ctx: typer.Context):
    """获取当前关节数据 (Observations)"""
    try:
        print(ctx.obj.get_observation())
    except ConnectionError as e:
        print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command(name="set")
def set_pos(
    ctx: typer.Context,
    args: list[str] = typer.Argument(..., help="关节参数，如 shoulder_pan.pos=1.1"),
):
    """设置关节位置 (格式: key=value)"""
    kwargs = {}
    for arg in args:
        if "=" in arg:
            k, v = arg.split("=", 1)
            kwargs[k] = float(v)
    try:
        print(ctx.obj.set_positions(**kwargs))
    except ConnectionError as e:
        print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def home(ctx: typer.Context):
    """机械臂各轴回零"""
    try:
        print(ctx.obj.home())
    except ConnectionError as e:
        print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def safe(ctx: typer.Context):
    """移动到安全位置"""
    try:
        print(ctx.obj.safe_pos())
    except ConnectionError as e:
        print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def free(ctx: typer.Context):
    """解锁扭矩 (先移动到安全位置)"""
    try:
        print(ctx.obj.free())
    except ConnectionError as e:
        print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def lock(ctx: typer.Context):
    """锁定扭矩"""
    try:
        print(ctx.obj.lock())
    except ConnectionError as e:
        print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def record(
    ctx: typer.Context,
    frequency: int = typer.Option(10, "--freq", "-f", help="采集频率 (Hz)"),
    filename: str = typer.Option(None, "--out", "-o", help="保存文件名"),
):
    """录制示教动作 (按 Enter 停止)"""
    try:
        ctx.obj.record(frequency, filename)
    except ConnectionError as e:
        print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def replay(
    ctx: typer.Context,
    speed: float = typer.Option(1.0, "--speed", "-s", help="回放倍速"),
    filename: str = typer.Option(None, "--file", "-r", help="指定回放文件"),
):
    """回放已录制的动作数据"""
    try:
        result = ctx.obj.replay(speed, filename)
        print("Replay complete" if result else "Replay failed")
    except ConnectionError as e:
        print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def test():
    """硬件自检 (端口与相机)"""
    from robot_agent.robot_utils import test_arm_port, test_camera
    print("[bold]开始硬件测试...[/bold]")
    test_arm_port()
    test_camera()
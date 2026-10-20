"""Entry point for the student package.

    python launch.py              -> the dashboard
    python launch.py play A B ...  -> a game
    python launch.py validate F    -> check your snake
    python launch.py new NAME      -> scaffold another snake to play your own against
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "new":
        name = args[1] if len(args) > 1 else "snake2"
        folder = HERE / name
        folder.mkdir(exist_ok=True)
        (folder / "Snake.java").write_text((HERE / "my-snake" / "Snake.java").read_text())
        print(f"created {folder / 'Snake.java'}")
        return 0
    if not args:
        from tools_launcher import server
        return server.main() or 0
    from snake.cli import main as cli_main
    return cli_main(args)


if __name__ == "__main__":
    sys.exit(main())

from src.scanner.config import load_output_dir
from src.logger import set_log_dir
from src.gui import DBFWApp


def main():
    # Apply the user's configured output directory before any logger is created,
    # so logs go to the right place from the very first line.
    output_dir = load_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    set_log_dir(output_dir)

    app = DBFWApp()
    app.mainloop()


if __name__ == "__main__":
    main()

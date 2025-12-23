import json
import logging
import os
import pathlib
import pyperclip
import socket
import sys
import time
import toml
import traceback
import typing
from datetime import datetime

logger = logging.getLogger(__name__)

"""
Python Script Template

Template includes:
- Configurable logging via config file
- Script run time at the end of execution
- Error handling and cleanup
- Total folder size log retention
"""

__version__ = "1.0.0"  # Major.Minor.Patch


def read_toml(file_path: typing.Union[str, pathlib.Path]) -> dict:
    """
    Read configuration settings from the TOML file.
    """
    file_path = pathlib.Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f'File not found: "{file_path}"')
    config = toml.load(file_path)
    return config


import pyperclip


def find_chunk_data_in_json(obj, found=None):
    if found is None:
        found = []

    if isinstance(obj, dict):
        if obj.get("plugin_path", "").endswith("reafir_standalone.dll"):
            chunk = obj.get("chunk_data")
            if chunk is not None:
                found.append(chunk)

        for v in obj.values():
            find_chunk_data_in_json(v, found)

    elif isinstance(obj, list):
        for v in obj:
            find_chunk_data_in_json(v, found)

    return found


def read_json_file(file_path: typing.Union[str, pathlib.Path]) -> typing.Union[dict, list]:
    """
    Reads a json file as a dictionary or list. Includes error checking and logging.

    Args:
    file_path (typing.Union[str, pathlib.Path]): The file path of the json file to read.

    Returns:
    typing.Union[dict, list]: The contents of the json file as a dictionary or list.
    """
    try:
        file_path = pathlib.Path(file_path)
        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created folder: '{file_path.parent}'")
        with open(file_path, "r") as file:
            data = json.load(file)
            logger.debug(f"Successfully read json file: '{file_path}'")
            return data
    except FileNotFoundError:
        logger.error(f"File not found: '{file_path}'")
        raise
    except json.JSONDecodeError:
        logger.error(f"Error decoding json file: '{file_path}'")
        raise


def main() -> None:
    username = pathlib.Path.home().name
    logger.debug(f'Detected username: "{username}"')
    scenes_folder = pathlib.Path(f'C:/Users/{username}/AppData/Roaming/obs-studio/basic/scenes')
    logger.debug(f'Searching for scenes folder: "{scenes_folder}"')
    if not os.path.exists(scenes_folder):
        logger.error(f'Scenes folder not found: "{scenes_folder}"')
        raise FileNotFoundError

    json_files = [f for f in scenes_folder.glob('*.json') if f.is_file()]
    if not json_files:
        logger.error(f'No JSON files found in "{scenes_folder}"')
        raise FileNotFoundError

    logger.info(f'Found {len(json_files)} JSON files in "{scenes_folder}"')
    for i, f in enumerate(json_files, 1):
        logger.info(f'{i}: {f.name}')

    if len(json_files) == 1:
        selected_file = json_files[0]
        logger.debug(f'Automatically selected the only JSON file: "{selected_file}"')
    else:
        while True:
            try:
                selection = int(input('Please select a JSON file by number: '))
                if 1 <= selection <= len(json_files):
                    selected_file = json_files[selection - 1]
                    break
                else:
                    logger.error('Invalid selection. Please try again.')
            except ValueError:
                logger.error('Invalid input. Please try again.')
    logger.debug(f'{selected_file=}')

    # Read the json data
    data = read_json_file(selected_file)
    # logger.debug(f'{data=}')

    # Print the json data
    chunk_datas = find_chunk_data_in_json(data)
    logger.debug(f'{chunk_datas=}')
    if not chunk_datas:
        logger.warning("ReaFIR not found")

    if len(chunk_datas) == 1:
        pyperclip.copy(chunk_datas[0])
        logger.info("chunk_data copied to clipboard")
    elif len(chunk_datas) == 0:
        logger.warning("No chunk_data found")
    else:
        logger.warning("Multiple chunk_data entries found; not copying")


def format_duration_long(duration_seconds: float) -> str:
    """
    Format duration in a human-friendly way, showing only the two largest non-zero units.
    For durations >= 1s, do not show microseconds or nanoseconds.
    For durations >= 1m, do not show milliseconds.
    """
    ns = int(duration_seconds * 1_000_000_000)
    units = [
        ('y', 365 * 24 * 60 * 60 * 1_000_000_000),
        ('mo', 30 * 24 * 60 * 60 * 1_000_000_000),
        ('d', 24 * 60 * 60 * 1_000_000_000),
        ('h', 60 * 60 * 1_000_000_000),
        ('m', 60 * 1_000_000_000),
        ('s', 1_000_000_000),
        ('ms', 1_000_000),
        ('us', 1_000),
        ('ns', 1),
    ]
    parts = []
    for name, factor in units:
        value, ns = divmod(ns, factor)
        if value:
            parts.append(f'{value}{name}')
        if len(parts) == 2:
            break
    if not parts:
        return "0s"
    return "".join(parts)


def enforce_max_folder_size(log_dir: pathlib.Path, max_bytes: int) -> None:
    """
    Enforce a maximum total size for all logs in the folder.
    Deletes oldest logs until below limit.
    """
    if max_bytes is None:
        return

    files = sorted(
        [f for f in log_dir.glob("*.log*") if f.is_file()],
        key=lambda f: f.stat().st_mtime
    )

    total_size = sum(f.stat().st_size for f in files)

    while total_size > max_bytes and files:
        oldest = files.pop(0)
        try:
            size = oldest.stat().st_size
            oldest.unlink()
            logger.debug(f'Deleted "{oldest}"')
            total_size -= size
        except Exception:
            logger.error(f'Failed to delete "{oldest}"', exc_info=True)
            continue


def setup_logging(
        logger: logging.Logger,
        log_file_path: typing.Union[str, pathlib.Path],
        max_folder_size_bytes: typing.Union[int, None] = None,
        console_logging_level: int = logging.DEBUG,
        file_logging_level: int = logging.DEBUG,
        log_message_format: str = "%(asctime)s.%(msecs)03d %(levelname)s [%(funcName)s]: %(message)s",
        date_format: str = "%Y-%m-%d %H:%M:%S"
) -> None:

    log_file_path = pathlib.Path(log_file_path)
    log_dir = log_file_path.parent
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.handlers.clear()
    logger.setLevel(file_logging_level)

    formatter = logging.Formatter(log_message_format, datefmt=date_format)

    # File Handler
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(file_logging_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_logging_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if max_folder_size_bytes is not None:
        enforce_max_folder_size(log_dir, max_folder_size_bytes)


def load_config(file_path: typing.Union[str, pathlib.Path]) -> dict:
    file_path = pathlib.Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f'File not found: "{file_path}"')
    config = read_toml(file_path)
    return config


if __name__ == "__main__":
    error = 0
    try:
        script_name = pathlib.Path(__file__).stem
        config_path = pathlib.Path(f'{script_name}_config.toml')
        # config_path = pathlib.Path("config.toml")
        config = load_config(config_path)

        logging_config = config.get("logging", {})
        console_logging_level = getattr(logging, logging_config.get("console_logging_level", "INFO").upper(), logging.DEBUG)
        file_logging_level = getattr(logging, logging_config.get("file_logging_level", "INFO").upper(), logging.DEBUG)
        log_message_format = logging_config.get("log_message_format", "%(asctime)s.%(msecs)03d %(levelname)s [%(funcName)s]: %(message)s")
        logs_folder_name = logging_config.get("logs_folder_name", "logs")
        max_folder_size_bytes = logging_config.get("max_folder_size", None)

        pc_name = socket.gethostname()
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_dir = pathlib.Path(logs_folder_name) / script_name
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_name = f'{timestamp}_{script_name}_{pc_name}.log'
        log_file_path = log_dir / log_file_name

        setup_logging(
            logger,
            log_file_path,
            max_folder_size_bytes=max_folder_size_bytes,
            console_logging_level=console_logging_level,
            file_logging_level=file_logging_level,
            log_message_format=log_message_format
        )
        start_time = time.perf_counter_ns()
        logger.info(f'Script: "{script_name}" | Version: {__version__} | Host: "{pc_name}"')
        main()
        end_time = time.perf_counter_ns()
        duration = end_time - start_time
        duration = format_duration_long(duration / 1e9)
        logger.info(f'Execution completed in {duration}.')
    except KeyboardInterrupt:
        logger.warning("Operation interrupted by user.")
        error = 130
    except Exception as e:
        logger.warning(f'A fatal error has occurred: {repr(e)}\n{traceback.format_exc()}')
        error = 1
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers.clear()
        input("Press Enter to exit...")
        sys.exit(error)

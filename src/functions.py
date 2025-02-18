import os
import glob
import json
import datetime
from urllib.parse import quote, urlencode
from pathlib import Path
from typing import List, Literal
import logging
from ulauncher.utils.fuzzy_search import get_score

from .moment import convert_moment_to_strptime_format

logger = logging.getLogger(__name__)


def fuzzyfinder(search: str, items: List[str]) -> List[str]:
    """
    >>> fuzzyfinder("hallo", ["hi", "hu", "hallo", "false"])
    ['hallo', 'false', 'hi', 'hu']
    """
    scores = []
    for i in items:
        score = get_score(search, get_name_from_path(i))
        scores.append((score, i))

    scores = sorted(scores, key=lambda score: score[0], reverse=True)

    return list(map(lambda score: score[1], scores))


class Note:
    def __init__(self, name: str, path: str, description: str):
        self.name = name
        self.path = path
        self.description = description

    def __repr__(self):
        return f"Note<{self.path}>"


def generate_url(vault: str, file: str, mode: Literal["open", "new"] = "open") -> str:
    """
    >>> generate_url("~/vault", "test.md")
    'obsidian://open?vault=vault&file=test.md'

    >>> generate_url("~/vault", "test")
    'obsidian://open?vault=vault&file=test.md'

    >>> generate_url("~/vault", "~/vault/test")
    'obsidian://open?vault=vault&file=test.md'

    >>> generate_url("~/vault", "~/vault/test")
    'obsidian://open?vault=vault&file=test.md'

    >>> generate_url("~/vault", "Java - Programming Language")
    'obsidian://open?vault=vault&file=Java%20-%20Programming%20Language.md'

    >>> generate_url("/home/kira/Documents/main_notes/", "Ulauncher Test", mode="new")
    'obsidian://new?vault=main_notes&file=Ulauncher%20Test.md'

    >>> generate_url("/home/[me]/Development/ObsidianVaults/", "Ulauncher Test", mode="new")
    'obsidian://new?vault=ObsidianVaults&file=Ulauncher%20Test.md'

    """
    if vault.endswith("/"):
        vault = vault[:-1]

    vault_name = get_name_from_path(vault, exclude_ext=False)
    if not file.endswith(".md"):
        file = file + ".md"

    try:
        relative_file = Path(file).relative_to(vault)
        return (
            "obsidian://"
            + mode
            + "?"
            + urlencode({"vault": vault_name,
                        "file": relative_file}, quote_via=quote)
        )
    except ValueError:
        if not file.endswith(".md"):
            file = file + ".md"
        return (
            "obsidian://"
            + mode
            + "?"
            + urlencode({"vault": vault_name, "file": file}, quote_via=quote)
        )


class DailyPath:
    path: str
    date: str
    folder: str
    exists: bool

    def __init__(self, path, date, folder, exists) -> None:
        self.path = path
        self.date = date
        self.folder = folder
        self.exists = exists


class DailySettings:
    format: str
    folder: str

    def __init__(self, format, folder) -> None:
        self.folder = folder
        self.format = format


class JsonPath:
    path: str
    exists: bool

    def __init__(self, path, exists) -> None:
        self.path = path
        self.exists = exists


class ExtractorSettings:
    tag_config: str

    def __init__(self, tag_config) -> None:
        self.tag_config = tag_config


def get_daily_settings(vault: str) -> DailySettings:
    daily_notes_path = os.path.join(vault, ".obsidian", "daily-notes.json")
    try:
        f = open(daily_notes_path, "r")
        daily_notes_config = json.load(f)
        f.close()
    except:
        daily_notes_config = {}
    format = daily_notes_config.get("format", "YYYY-MM-DD")
    folder = daily_notes_config.get("folder", "")

    if format == "":
        format = "YYYY-MM-DD"

    return DailySettings(format, folder)


def get_periodic_settings(vault: str) -> DailySettings:
    periodic_path = os.path.join(
        vault, ".obsidian", "plugins", "periodic-notes", "data.json"
    )
    try:
        f = open(periodic_path)
        config = json.load(f)
        f.close()
    except:
        config = {}

    daily_config = config.get("daily", {})
    format = daily_config.get("format", "YYYY-MM-DD")
    folder = daily_config.get("folder", "")

    if format == "":
        format = "YYYY-MM-DD"

    return DailySettings(format, folder)


def get_extractor_settings(vault: str) -> ExtractorSettings:
    metadata_path = os.path.join(
        vault, ".obsidian", "plugins", "metadata-extractor", "data.json"
    )
    tag_config = ""

    try:
        f = open(metadata_path)
        config = json.load(f)
        f.close()
        tag_path = config.get("tagPath", "")
        tag_file = config.get("tagFile", "")

        if tag_path == "":
            tag_config = tag_file
        elif tag_file == "":
            tag_config = tag_path

    except:
        tag_config = os.path.join(
            vault, ".obsidian", "plugins", "metadata-extractor", "tags.json"
        )

    return ExtractorSettings(tag_config)


def is_obsidian_plugin_enabled(vault: str, name: str) -> bool:
    core = os.path.join(vault, ".obsidian", "core-plugins.json")
    community = os.path.join(vault, ".obsidian", "community-plugins.json")
    plugins = []
    try:
        with open(core) as f:
            core = json.load(f)
            plugins += core
    except:
        pass

    try:
        with open(community) as f:
            community = json.load(f)
            plugins += community
    except:
        pass

    return name in plugins


def get_daily_path(vault: str) -> DailyPath:
    if is_obsidian_plugin_enabled(vault, "periodic-notes"):
        settings = get_periodic_settings(vault)
    else:
        settings = get_daily_settings(vault)

    date = datetime.datetime.now().strftime(
        convert_moment_to_strptime_format(settings.format)
    )
    path = os.path.join(vault, settings.folder, date + ".md")
    exists = os.path.exists(path)

    return DailyPath(path, date, settings.folder, exists)


def generate_daily_url(vault: str) -> str:
    """
    >>> generate_daily_url("test-vault")
    'obsidian://new?vault=test-vault&file=16-07-2021.md'
    """
    daily_path = get_daily_path(vault)
    mode = "new"
    if daily_path.exists:
        mode = "open"

    return generate_url(
        vault, os.path.join(daily_path.folder, daily_path.date), mode=mode
    )


def get_json_path(vault: str) -> JsonPath:
    if is_obsidian_plugin_enabled(vault, "metadata-extractor"):
        settings = get_extractor_settings(vault)
    else:
        # TODO Prompt to install plugin? The return statement will error...
        pass

    path = settings.tag_config
    exists = os.path.exists(path)

    return JsonPath(path, exists)


def get_name_from_path(path: str, exclude_ext=True) -> str:
    """
    >>> get_name_from_path("~/home/test/bla/hallo.md")
    'hallo'

    >>> get_name_from_path("~/home/Google Drive/Brain 1.0", False)
    'Brain 1.0'
    """
    base = os.path.basename(path)
    if exclude_ext:
        split = os.path.splitext(base)
        return split[0]
    return base


def find_note_in_vault(vault: str, search: str) -> List[Note]:
    """
    >>> find_note_in_vault("test-vault", "Test")
    [Note<test-vault/Test.md>, Note<test-vault/Test2.md>, Note<test-vault/subdir/Test.md>, Note<test-vault/subdir/Hallo.md>]
    """
    search_pattern = os.path.join(vault, "**", "*.md")
    logger.info(search_pattern)
    files = glob.glob(search_pattern, recursive=True)
    suggestions = fuzzyfinder(search, files)
    return [
        Note(name=get_name_from_path(s), path=s, description=s) for s in suggestions
    ]


def find_string_in_vault(vault: str, search: str) -> List[Note]:
    """
    >>> find_string_in_vault("test-vault", "Test")
    [Note<test-vault/Test.md>, Note<test-vault/subdir/Test.md>]
    """
    files = glob.glob(os.path.join(vault, "**", "*.md"), recursive=True)

    suggestions = []

    CONTEXT_SIZE = 10

    search = search.lower()
    for file in files:
        if os.path.isfile(file) and search is not None:
            with open(file, "r") as f:
                for line in f:
                    left, sep, right = line.lower().partition(search)
                    if sep:
                        context = left[CONTEXT_SIZE:] + \
                            sep + right[:CONTEXT_SIZE]
                        suggestions.append(
                            Note(
                                name=get_name_from_path(file),
                                path=file,
                                description=context,
                            )
                        )
                        break

    return suggestions


def find_tag_in_vault(vault: str, search: str) -> str:
    """
    >>> find_tag_in_vault("test-vault", "todo")
    [Note<test-vault/Test.md>, Note<test-vault/subdir/Test.md>]
    """
    tag_config = get_json_path(vault).path
    suggestions = []

    CONTEXT_SIZE = 10

    if search[0] == "#":
        search = search.replace("#", "")
    search = search.lower()

    with open(tag_config, "r") as file:
        tag_json = json.load(file)
        files = [item["relativePaths"]
                 for item in tag_json if item["tag"].lower() == search]

    # TODO unnest list with itertools?
    for file in files[0]:
        file = os.path.join(vault, file)
        if os.path.isfile(file):
            with open(file, "r") as f:
                for line in f:
                    left, sep, right = line.lower().partition(search)
                    if sep:
                        context = left[CONTEXT_SIZE:] + \
                            sep + right[:CONTEXT_SIZE]
                        suggestions.append(
                            Note(
                                name=get_name_from_path(file),
                                path=file,
                                # TODO output actual context...
                                description=context,
                            )
                        )
                        break

    return suggestions


def create_note_in_vault(vault: str, name: str) -> str:
    path = os.path.join(vault, name + ".md")
    if not os.path.isfile(path):
        with open(path, "w") as f:
            f.write(f"# {name}")
    return path


def append_to_note_in_vault(vault: str, file: str, content: str):
    if file == "":
        file = get_daily_path(vault).path
    elif not file.endswith(".md"):
        file = file + ".md"
    path = os.path.join(vault, file)

    with open(path, "a") as f:
        f.write(os.linesep)
        f.write(content)


if __name__ == "__main__":
    import doctest
    import time_machine

    traveller = time_machine.travel(datetime.datetime(2021, 7, 16))
    traveller.start()

    doctest.testmod()

    traveller.stop()

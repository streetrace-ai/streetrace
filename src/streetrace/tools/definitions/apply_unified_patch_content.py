"""A tool that applies a unified diff (e.g., git diff).

Having the model to patch instead of writing full files would be awesome, but you
know how it is to force a model to follow a specific format. I wasn't able to
get this to work reliably.
one idea is to bake in a small model that can apply losely formatted patches,
allowing the model some freedom of expression.
alternatively implement structured output, but it's easier to stick to write_file
vs. loosing quality.
"""

import subprocess
from pathlib import Path

from streetrace.tools.definitions.result import CliResult, OpResultCode


def apply_unified_patch_content(patch_content: str, work_dir: Path) -> CliResult:
    r"""Apply a unified diff patch to local files in the working directory.

    Start all local paths with the current directory (./), e.g.:

    ```
    --- /dev/null
    +++ ./answer.txt
    @@ -0,0 +1 @@
    +42
    ```

    You should provide at least three context lines before and after each
    change hunk, e.g.:

    ```
    --- ./answer.txt
    +++ ./answer.txt
    @@ -3,7 +3,7 @@ to life,
    the universe,
    and everything:

    -42
    +43

    From The
    Hitchhiker's
    ```

    This is a preferred way of applying changes to project files. It allows
    changing several files at once. All changes to all files can be applied
    at once following the GNU patch unified diff format.

    Never run bash scripts with apply_unified_patch_content. Use this function
    only to create or modify files in the working directory.

    Args:
        patch_content (str): The unified diff patch content.
        work_dir (Path): The directory where the patch should be applied.

    Returns:
        dict[str,str]:
            "tool_name": "apply_unified_patch_content"
            "result": "success" or "failure"
            "stderr": stderr output of the GNU patch command
            "stdout": stdout output of the GNU patch command

    """
    try:
        result = subprocess.run(
            ["patch", "-p1"],
            input=patch_content + "\n",
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        return CliResult(
            tool_name="apply_unified_patch_content",
            result=OpResultCode.SUCCESS,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
        )
    except subprocess.CalledProcessError as e:
        return CliResult(
            tool_name="apply_unified_patch_content",
            result=OpResultCode.FAILURE,
            stdout=e.stdout.strip(),
            stderr=e.stderr.strip(),
        )

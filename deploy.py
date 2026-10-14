import subprocess
import logging
from result import Result

logger = logging.getLogger(__name__)


def deploy_server_config() -> Result:
    try:
        completed = subprocess.run(
            ["bash", "scripts/deploy_awg_config.sh"],
            capture_output=True,
            text=True,
            check=False,
        )

        if completed.returncode != 0:
            logger.error("Deploy failed: %s", completed.stderr.strip())
            return Result(False, error=f"Deploy failed: {completed.stderr.strip()}")

        logger.info("Deploy success: %s", completed.stdout.strip())
        return Result(True, data={"deploy_output": completed.stdout.strip()})

    except Exception:
        logger.exception("Deploy gone wrong")
        return Result(False, error="Deploy gone wrong")

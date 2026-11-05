"""The arq worker run inside the API process, for local development.

Uploads are only processed by a worker; started separately, it is easy to forget, and then
documents wait in the queue indefinitely. In development the API runs one in its own event
loop instead (see `Settings.run_embedded_worker`). Production runs the worker as its own
process (render.yaml), since serverless functions can't host a long-running poller.
"""

import asyncio
import contextlib
import logging

logger = logging.getLogger(__name__)

RESTART_DELAY_SECONDS = 15


async def supervise_worker() -> None:
    """Run the worker until cancelled, restarting it after it stops (e.g. Redis was lost or
    MongoDB was unreachable at startup). Cancelling the task shuts the worker down."""
    # Imported here: the worker settings build their own clients from the environment.
    from arq.worker import create_worker

    from app.workers.settings import WorkerSettings

    while True:
        worker = create_worker(WorkerSettings, handle_signals=False)  # type: ignore[arg-type]
        try:
            logger.info("embedded_worker_started")
            await worker.async_run()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "embedded_worker_stopped",
                extra={"error": type(exc).__name__, "restart_in_seconds": RESTART_DELAY_SECONDS},
            )
        finally:
            with contextlib.suppress(Exception):
                await worker.close()
        await asyncio.sleep(RESTART_DELAY_SECONDS)

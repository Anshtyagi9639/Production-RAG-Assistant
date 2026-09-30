import logging
from typing import Any

from pydantic import ValidationError

from app.services.document_processing import DocumentProcessor, Outcome
from app.services.queue import ProcessDocumentJob

logger = logging.getLogger(__name__)


async def process_document(ctx: dict[str, Any], payload: Any) -> str:
    """arq task. A malformed payload is dropped (retrying can't fix it); anything else is
    handled by the processor, which records COMPLETED or FAILED on the document."""
    try:
        job = ProcessDocumentJob.model_validate(payload)
    except ValidationError as exc:
        logger.error(
            "invalid_job_payload",
            extra={"job_id": ctx.get("job_id"), "errors": [e["type"] for e in exc.errors()]},
        )
        return "rejected"
    processor: DocumentProcessor = ctx["processor"]
    outcome: Outcome = await processor.process(job)
    return outcome.value

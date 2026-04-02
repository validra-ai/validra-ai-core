from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["Execution"])


@router.post("/cancel/{run_id}", summary="Cancel an active test run")
def cancel_run(run_id: str, req: Request):
    """
    Cancel a running test execution by its run ID.

    The `run_id` is returned in the `warming_up` SSE event at the start of each
    `/generateAndRun` call. Sending a cancel request sets a stop flag that causes
    the execution loop to halt after the current in-flight test completes.

    Returns 404 if the run ID is not found or the run has already finished.
    """
    stop_event = req.app.state.active_runs.get(run_id)
    if stop_event is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found or already completed")
    stop_event.set()
    return {"cancelled": True, "run_id": run_id}

# TV Manager v17.3.5

## Import Progress Job Startup Fix

This patch fixes the asynchronous SickChill import progress endpoint failing at job creation with:

```text
_set_import_job() got multiple values for argument 'job_id'
```

The queued import job now stores the generated job ID in the job payload without passing the same argument twice to the helper.

## Validation

- Full Python unit test suite passes.
- Python compile check passes.
- JavaScript syntax check passes.

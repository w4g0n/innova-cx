-- Allow ticket priority to remain NULL until the prioritization model assigns it.
ALTER TABLE tickets
  ALTER COLUMN priority DROP DEFAULT,
  ALTER COLUMN priority DROP NOT NULL;


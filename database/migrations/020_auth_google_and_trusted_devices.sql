BEGIN;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS google_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id
ON users(google_id)
WHERE google_id IS NOT NULL;

ALTER TABLE users
ALTER COLUMN password_hash DROP NOT NULL;

CREATE TABLE IF NOT EXISTS trusted_devices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  user_agent TEXT,
  created_ip TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ
);

ALTER TABLE trusted_devices
ADD COLUMN IF NOT EXISTS user_agent TEXT;

ALTER TABLE trusted_devices
ADD COLUMN IF NOT EXISTS created_ip TEXT;

ALTER TABLE trusted_devices
ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE trusted_devices
ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMPTZ;

ALTER TABLE trusted_devices
ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

ALTER TABLE trusted_devices
ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_trusted_devices_token_hash
ON trusted_devices(token_hash);

CREATE INDEX IF NOT EXISTS idx_trusted_devices_user_id
ON trusted_devices(user_id);

CREATE INDEX IF NOT EXISTS idx_trusted_devices_active
ON trusted_devices(user_id, expires_at)
WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS mfa_reset_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE mfa_reset_tokens
ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE mfa_reset_tokens
ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

ALTER TABLE mfa_reset_tokens
ADD COLUMN IF NOT EXISTS used_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_mfa_reset_tokens_user_id
ON mfa_reset_tokens(user_id);

COMMIT;

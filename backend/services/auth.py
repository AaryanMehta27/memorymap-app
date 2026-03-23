# JWT validation middleware for Supabase auth

# TODO: Implement require_auth dependency that:
# - Extracts Bearer token from Authorization header
# - Validates JWT using SUPABASE_JWT_SECRET
# - Returns decoded user payload on success
# - Raises HTTP 401 if token is missing or invalid

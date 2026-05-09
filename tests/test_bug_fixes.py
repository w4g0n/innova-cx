"""
Regression tests for:
  Bug 1 — Department routing always landing on Facilities Management
  Bug 2 — Recurrence check matching tickets across different users
"""

import re
import sys
import os
import importlib
import urllib.parse

# ---------------------------------------------------------------------------
# Bug 1 — Department routing system prompt bias
# ---------------------------------------------------------------------------

def _load_router():
    router_path = os.path.join(
        os.path.dirname(__file__),
        "..", "ai-models", "MultiAgentPipeline", "Orchestrator",
        "agents", "step10_router",
    )
    sys.path.insert(0, os.path.abspath(router_path))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "step10_router",
        os.path.join(router_path, "step.py"),
    )
    # We only need to read the source, not fully import (avoids httpx/torch deps)
    with open(os.path.join(router_path, "step.py")) as f:
        return f.read()


def test_routing_no_longer_uses_qwen_prompt():
    """Router must not use a Qwen numbered-list prompt — switched to DeBERTa NLI."""
    source = _load_router()
    assert "_ROUTING_SYSTEM" not in source, (
        "_ROUTING_SYSTEM still present — router should use DeBERTa NLI, not Qwen generation"
    )
    assert "_build_qwen_routing_prompt" not in source, (
        "_build_qwen_routing_prompt still present — Qwen prompt code should be removed"
    )


def test_routing_uses_deberta_nli():
    """Router must use DeBERTa NLI scoring via _predict_department_via_deberta."""
    source = _load_router()
    assert "_predict_department_via_deberta" in source, (
        "DeBERTa inference function missing from step10_router/step.py"
    )
    assert "_HYPOTHESIS_TEMPLATE" in source, (
        "_HYPOTHESIS_TEMPLATE missing — NLI hypothesis string must be defined"
    )
    assert "get_shared_deberta" in source, (
        "Router must import get_shared_deberta from shared_model_service"
    )


def test_department_index_parsing_all_seven():
    """
    Qwen replies with digits 1-7. dept_index = digit - 1 must map each reply
    to the correct DEPARTMENT_LABELS entry (0-based).
    """
    source = _load_router()

    # Extract DEPARTMENT_LABELS list order from DEPARTMENT_CANDIDATES keys
    candidates_block = re.search(
        r'DEPARTMENT_CANDIDATES\s*=\s*\{(.*?)\}', source, re.DOTALL
    )
    assert candidates_block, "DEPARTMENT_CANDIDATES not found"
    keys = re.findall(r'"([^"]+)"\s*:', candidates_block.group(1))
    assert len(keys) == 7, f"Expected 7 departments, got {len(keys)}: {keys}"

    for digit in range(1, 8):
        dept_index = digit - 1          # same formula as step.py
        chosen = keys[dept_index]
        assert chosen == keys[digit - 1], (
            f"Digit '{digit}' should map to '{keys[digit-1]}', got '{chosen}'"
        )


def test_facilities_management_is_first_in_list():
    """FM being #1 is fine as long as the prompt doesn't bias toward it."""
    source = _load_router()
    candidates_block = re.search(
        r'DEPARTMENT_CANDIDATES\s*=\s*\{(.*?)\}', source, re.DOTALL
    )
    keys = re.findall(r'"([^"]+)"\s*:', candidates_block.group(1))
    assert keys[0] == "Facilities Management"
    # Verify IT and Maintenance are NOT first (common correct answers)
    assert keys[0] != "IT"
    assert keys[0] != "Maintenance"


def test_digit_regex_finds_first_digit_only():
    """re.search(r'[1-7]', response) must pick the first digit in the response."""
    cases = [
        ("2", "2"),
        ("3. Maintenance", "3"),
        ("The answer is 5", "5"),
        ("  7  ", "7"),
        ("department 4 handles this", "4"),
    ]
    for response, expected in cases:
        m = re.search(r"[1-7]", response)
        assert m and m.group(0) == expected, (
            f"Expected digit '{expected}' from response '{response}', got '{m.group(0) if m else None}'"
        )


def test_digit_regex_returns_none_for_invalid_responses():
    """Unparseable responses (no digit 1-7) should fall back to heuristic."""
    bad_responses = ["", "eight", "0", "8", "department unknown"]
    for response in bad_responses:
        m = re.search(r"[1-7]", response)
        assert m is None, f"Expected no match for '{response}', got '{m.group(0)}'"


# ---------------------------------------------------------------------------
# Bug 2 — Recurrence cross-user ticket matching
# ---------------------------------------------------------------------------

def _load_dispatch_source():
    gate_path = os.path.join(
        os.path.dirname(__file__),
        "..", "backend", "api", "ticket_creation_gate.py",
    )
    with open(os.path.abspath(gate_path)) as f:
        return f.read()


def test_dispatch_function_accepts_created_by_user_id():
    """dispatch_ticket_to_orchestrator must declare created_by_user_id parameter."""
    source = _load_dispatch_source()
    sig_block = re.search(
        r'def dispatch_ticket_to_orchestrator\s*\((.*?)\)\s*->', source, re.DOTALL
    )
    assert sig_block, "dispatch_ticket_to_orchestrator not found"
    assert "created_by_user_id" in sig_block.group(1), (
        "created_by_user_id missing from dispatch_ticket_to_orchestrator signature — "
        "pipeline will never receive it and user filter will be bypassed"
    )


def test_dispatch_payload_includes_user_id_when_provided():
    """
    When created_by_user_id is given, it must appear in the URL-encoded payload
    sent to the orchestrator.
    """
    source = _load_dispatch_source()
    # Verify the payload assignment exists
    assert 'payload["created_by_user_id"]' in source or "created_by_user_id" in source


def test_dispatch_payload_excludes_user_id_when_none():
    """
    When created_by_user_id is None the payload key must be absent
    (the pipeline treats missing key as None, not the string 'None').
    """
    source = _load_dispatch_source()
    # The guard should be: if created_by_user_id and str(...).strip(): payload[...] = ...
    assert re.search(
        r'if\s+created_by_user_id\b.*payload\[.created_by_user_id.\]',
        source, re.DOTALL
    ), "Missing conditional guard before adding created_by_user_id to payload"


def _extract_call_block(source: str, start_pattern: str) -> str:
    """
    Find start_pattern then return everything up to the matching closing paren,
    handling nested parentheses correctly.
    """
    m = re.search(start_pattern, source, re.DOTALL)
    assert m, f"Pattern not found: {start_pattern}"
    pos = m.end() - 1  # position of the opening '('
    depth = 0
    for i in range(pos, len(source)):
        if source[i] == '(':
            depth += 1
        elif source[i] == ')':
            depth -= 1
            if depth == 0:
                return source[m.start():i + 1]
    raise AssertionError("Unmatched parenthesis in source")


def test_main_customer_ticket_passes_user_id_to_dispatcher():
    """_dispatch_orchestrator_after_submit call must forward user['id'] as created_by_user_id."""
    main_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "backend", "api", "main.py")
    )
    with open(main_path) as f:
        source = f.read()

    block = _extract_call_block(
        source,
        r'background_tasks\.add_task\s*\(',
    )
    assert "_dispatch_orchestrator_after_submit" in block, \
        "add_task block does not call _dispatch_orchestrator_after_submit"
    assert "created_by_user_id" in block, (
        "created_by_user_id not forwarded in add_task call — "
        "pipeline state will have None and bypass the user filter"
    )


def test_main_internal_ticket_passes_user_id_to_dispatcher():
    """Internal ticket creation endpoint must also forward created_by_user_id."""
    main_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "backend", "api", "main.py")
    )
    with open(main_path) as f:
        source = f.read()

    # Find all dispatch_ticket_to_orchestrator calls with proper paren matching
    calls = []
    for m in re.finditer(r'dispatch_ticket_to_orchestrator\s*\(', source):
        pos = m.end() - 1
        depth = 0
        for i in range(pos, len(source)):
            if source[i] == '(':
                depth += 1
            elif source[i] == ')':
                depth -= 1
                if depth == 0:
                    calls.append(source[m.start():i + 1])
                    break

    assert len(calls) >= 2, f"Expected at least 2 calls to dispatch_ticket_to_orchestrator, found {len(calls)}"
    internal_call = calls[1]
    assert "created_by_user_id" in internal_call, (
        "Internal ticket endpoint does not pass created_by_user_id to dispatcher"
    )


def test_dispatch_wrapper_signature_includes_user_id():
    """_dispatch_orchestrator_after_submit itself must declare the parameter."""
    main_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "backend", "api", "main.py")
    )
    with open(main_path) as f:
        source = f.read()

    wrapper_sig = re.search(
        r'def _dispatch_orchestrator_after_submit\s*\((.*?)\)\s*->', source, re.DOTALL
    )
    assert wrapper_sig, "_dispatch_orchestrator_after_submit definition not found"
    assert "created_by_user_id" in wrapper_sig.group(1)


# ---------------------------------------------------------------------------
# Bug 2 — SQL subject guard
# ---------------------------------------------------------------------------

def test_sql_subject_guard_present():
    """
    compute_is_recurring_ticket must skip the empty-subject match to prevent
    tickets with NULL subjects (not yet processed by the pipeline) from
    triggering false recurring flags.
    """
    sql_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "database", "init.sql")
    )
    with open(sql_path) as f:
        source = f.read()

    func_block = re.search(
        r'CREATE OR REPLACE FUNCTION compute_is_recurring_ticket(.*?)END;',
        source, re.DOTALL,
    )
    assert func_block, "compute_is_recurring_ticket not found in init.sql"
    body = func_block.group(0)

    assert "normalized_subject <> ''" in body, (
        "Subject equality check must be guarded by normalized_subject <> '' — "
        "without it, subject='' matches all tickets with NULL/empty subject"
    )


def test_sql_user_filter_present():
    """created_by_user_id filter must exist in compute_is_recurring_ticket."""
    sql_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "database", "init.sql")
    )
    with open(sql_path) as f:
        source = f.read()

    func_block = re.search(
        r'CREATE OR REPLACE FUNCTION compute_is_recurring_ticket(.*?)END;',
        source, re.DOTALL,
    )
    body = func_block.group(0)
    assert "created_by_user_id = p_user_id" in body, (
        "User ID filter missing from compute_is_recurring_ticket"
    )


def test_recurrence_encoder_user_filter_in_sql():
    """_fetch_candidates query in recurrence_encoder must filter by created_by_user_id."""
    enc_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..", "ai-models", "MultiAgentPipeline", "Orchestrator",
            "recurrence_encoder.py",
        )
    )
    with open(enc_path) as f:
        source = f.read()

    assert "created_by_user_id = %s::uuid" in source, (
        "recurrence_encoder._fetch_candidates missing user_id filter in SQL"
    )
